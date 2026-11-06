#include "layouts.hpp"
#include <QDir>
#include <QFile>
#include <QJsonDocument>
#include <QTemporaryDir>
#include <QtTest>
#include <fcntl.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>

using namespace Opm;
static void writeFile(const QString &path, const QByteArray &bytes) {
    QFile file(path);
    if (!file.open(QIODevice::WriteOnly) || file.write(bytes) != bytes.size())
        qFatal("Test fixture write failed");
}
static QJsonObject fixture() {
    auto cfg = defaults();
    cfg["menu"] = QJsonArray{
        QJsonObject{{"label", "Literal"},
                    {"command", QJsonArray{"/bin/true", "$literal", "a;b"}},
                    {"desktop_file", "/tmp/application.desktop"},
                    {"future", QJsonObject{{"access_key", "x"}}}},
        QJsonObject{{"submenu", "Group"},
                    {"items", QJsonArray{QJsonObject{
                                  {"label", "Unavailable"},
                                  {"command", QJsonArray{"opm-deliberately-missing"}}}}}}};
    cfg["future_preference"] = QJsonObject{{"nested", QJsonArray{1, 2, 3}}};
    return cfg;
}
static QJsonArray references(const QJsonArray &entries) {
    QJsonArray result;
    for (const auto &value : entries) {
        const auto item = value.toObject();
        QJsonObject node{{"id", item["id"]}};
        if (item["kind"] == "submenu")
            node["items"] = references(item["items"].toArray());
        result.append(node);
    }
    return result;
}
static QString payload(const QJsonArray &nodes) {
    return QString::fromUtf8(QJsonDocument(nodes).toJson(QJsonDocument::Compact));
}

class ModelTests : public QObject {
    Q_OBJECT
  private slots:
    void defaultsAndLegacyMerge() {
        validate(defaults());
        QCOMPARE(defaults()["menu"].toArray().last().toObject()["action"].toString(),
                 "show_desktop");
        const auto cfg = decode(QByteArray("{\"menu\":[],\"unknown\":{\"saved\":true}}"));
        QVERIFY(cfg["menu"].toArray().isEmpty());
        QVERIFY(cfg["unknown"].toObject()["saved"].toBool());
        QCOMPARE(cfg["auto_close_on_pointer_leave"], QJsonValue(false));
    }
    void invalidConfiguration_data() {
        QTest::addColumn<QByteArray>("source");
        for (const auto &value :
             {"[]", "{}", "{broken", "{\"menu\":[],\"auto_close_on_pointer_leave\":1}",
              "{\"menu\":[],\"backup_retention\":1.0}", "{\"menu\":[],\"backup_retention\":true}",
              "{\"menu\":[],\"unknown\":9223372036854775808}",
              "{\"menu\":[],\"launcher_applet_id\":-1}",
              "{\"menu\":[],\"button_icon\":\"https://example.com/a.png\"}",
              "{\"menu\":[{\"command\":\"echo unsafe\"}]}", "{\"menu\":[{\"action\":\"unknown\"}]}",
              "{\"menu\":[{\"command\":[\"true\",\"\"]}]}",
              "{\"menu\":[{\"submenu\":\"x\",\"items\":{}}]}"})
            QTest::newRow(value) << QByteArray(value);
    }
    void invalidConfiguration() {
        QFETCH(QByteArray, source);
        QVERIFY_EXCEPTION_THROWN(decode(source), Error);
    }
    void publicMenuAndKeys() {
        Model model;
        auto cfg = fixture();
        auto menu = model.publicMenu(cfg);
        QCOMPARE(menu.size(), 1);
        QVERIFY(!QJsonDocument(menu).toJson().contains("a;b"));
        QCOMPARE(model.command(cfg, "0"), (QStringList{"/bin/true", "$literal", "a;b"}));
        for (const auto &key : {"", "0.1", "-1", "0;touch", "100000", "0.", "٠"})
            QVERIFY(model.command(cfg, key).isEmpty());
        cfg["show_unavailable"] = true;
        menu = model.publicMenu(cfg);
        QCOMPARE(menu.size(), 2);
        QVERIFY(!menu[1].toObject()["items"].toArray()[0].toObject()["enabled"].toBool());
        QVERIFY(model.command(cfg, "1.0").isEmpty());
    }
    void unknownIntegersAndParserBounds() {
        const QByteArray source(
            "{\"menu\":[],\"large\":9223372036854775807,\"small\":-9223372036854775808}");
        const auto config = decode(source);
        const auto written = QJsonDocument(config).toJson();
        QVERIFY(written.contains("9223372036854775807"));
        QVERIFY(written.contains("-9223372036854775808"));
        QCOMPARE(decode(written), config);
        QCOMPARE(decode(QByteArray::fromHex("efbbbf") + source), config);
        const auto tooDeep = QByteArray("{\"menu\":[],\"metadata\":") + QByteArray(257, '[') + "0" +
                             QByteArray(257, ']') + "}";
        QVERIFY_EXCEPTION_THROWN(decode(tooDeep), Error);
        // Config retains last-wins compatibility; reference payloads cannot
        // hide repeated keys behind Unicode escapes.
        QCOMPARE(
            decode(QByteArray(
                "{\"menu\":[],\"appearance\":\"aero\",\"appearance\":\"native\"}"))["appearance"],
            QJsonValue("native"));
    }
    void sizeAndSpecialFiles() {
        QTemporaryDir temp;
        const auto path = temp.filePath("menu.json");
        Storage store(path);
        QVERIFY(!store.revision().content);
        QCOMPARE(store.load(), defaults());
        QByteArray bytes("{\"menu\":[]}");
        bytes.append(QByteArray(MaxConfigBytes - bytes.size(), ' '));
        writeFile(path, bytes);
        QVERIFY(store.load()["menu"].toArray().isEmpty());
        bytes.append(' ');
        writeFile(path, bytes);
        QVERIFY_EXCEPTION_THROWN(store.load(), Error);
        QFile::remove(path);
        QVERIFY(::mkfifo(QFile::encodeName(path).constData(), 0600) == 0);
        QVERIFY_EXCEPTION_THROWN(store.load(), Error);
        QFile::remove(path);
        QVERIFY(QDir().mkdir(path));
        QVERIFY_EXCEPTION_THROWN(store.load(), Error);
    }
    void refuseSymlinks() {
        QTemporaryDir temp;
        const auto actual = temp.filePath("real");
        QVERIFY(QDir().mkdir(actual));
        writeFile(actual + "/menu.json", "{\"menu\":[]}");
        QVERIFY(QFile::link(actual, temp.filePath("linked")));
        QVERIFY_EXCEPTION_THROWN(Storage(temp.filePath("linked/menu.json")).load(), Error);
        QVERIFY(QFile::link(actual + "/menu.json", temp.filePath("menu.json")));
        QVERIFY_EXCEPTION_THROWN(Storage(temp.filePath("menu.json")).load(), Error);
        QFile::remove(temp.filePath("menu.json"));
        QVERIFY(QFile::link(temp.filePath("missing"), temp.filePath("menu.json")));
        QVERIFY_EXCEPTION_THROWN(Storage(temp.filePath("menu.json")).load(), Error);
    }
    void guardedSaveAndBackups() {
        QTemporaryDir temp;
        Storage store(temp.filePath("menu.json"));
        auto cfg = fixture();
        cfg["backup_retention"] = 1;
        store.save(cfg, {});
        auto first = store.revision();
        cfg["appearance"] = "aero";
        store.save(cfg, first);
        auto backups = QDir(temp.path()).entryList({"menu.json.bak-*"}, QDir::Files);
        QCOMPARE(backups.size(), 1);
        QFile previous(temp.filePath(backups[0]));
        QVERIFY(previous.open(QIODevice::ReadOnly));
        QCOMPARE(previous.readAll(), *first.content);
        QVERIFY_EXCEPTION_THROWN(store.save(cfg, first), Error);
        cfg["appearance"] = "native";
        store.save(cfg, store.revision());
        QCOMPARE(QDir(temp.path()).entryList({"menu.json.bak-*"}, QDir::Files).size(), 1);
        cfg["backup_retention"] = 0;
        store.save(cfg, store.revision());
        QCOMPARE(QDir(temp.path()).entryList({"menu.json.bak-*"}, QDir::Files).size(), 1);
        struct stat info{};
        QVERIFY(!::stat(QFile::encodeName(store.path()).constData(), &info));
        QCOMPARE(info.st_mode & 0777, mode_t(0600));
        QCOMPARE(store.load()["future_preference"], cfg["future_preference"]);
    }
    void inodeAndContentConflicts() {
        QTemporaryDir temp;
        Storage store(temp.filePath("menu.json"));
        store.save(fixture(), {});
        auto before = store.revision();
        writeFile(temp.filePath("replacement"), *before.content);
        QVERIFY(!::rename(QFile::encodeName(temp.filePath("replacement")).constData(),
                          QFile::encodeName(store.path()).constData()));
        QVERIFY_EXCEPTION_THROWN(store.save(fixture(), before), Error);
        before = store.revision();
        writeFile(store.path(), "{\"menu\":[]}");
        QVERIFY_EXCEPTION_THROWN(store.save(fixture(), before), Error);
    }
    void lockAndWriteFailurePreserveOldFile() {
        QTemporaryDir temp;
        Storage store(temp.filePath("menu.json"));
        auto cfg = fixture();
        store.save(cfg, {});
        const auto before = store.revision();
        const auto lockPath = QFile::encodeName(temp.filePath(".menu.lock"));
        int lock = ::open(lockPath.constData(), O_RDWR);
        QVERIFY(lock >= 0);
        QVERIFY(!::flock(lock, LOCK_EX | LOCK_NB));
        QVERIFY_EXCEPTION_THROWN(store.save(cfg, before), Error);
        ::close(lock);
        QCOMPARE(store.revision().content, before.content);
        QFile::remove(QString::fromLocal8Bit(lockPath));
        QVERIFY(QFile::link(store.path(), QString::fromLocal8Bit(lockPath)));
        QVERIFY_EXCEPTION_THROWN(store.save(cfg, before), Error);
        QCOMPARE(store.revision().content, before.content);
        QFile::remove(QString::fromLocal8Bit(lockPath));
        if (::geteuid() != 0) {
            QVERIFY(!::chmod(QFile::encodeName(temp.path()).constData(), 0500));
            QVERIFY_EXCEPTION_THROWN(store.save(cfg, before), Error);
            QVERIFY(!::chmod(QFile::encodeName(temp.path()).constData(), 0700));
            QCOMPARE(store.revision().content, before.content);
        }
    }
    void layoutPreservesDefinitionsAndHiddenItems() {
        QTemporaryDir temp;
        Storage store(temp.filePath("menu.json"));
        const auto original = fixture();
        store.save(original, {});
        Layouts edits(store);
        auto begun = edits.begin();
        const auto token = begun["token"].toString();
        auto nodes = references(begun["entries"].toArray());
        auto first = nodes.takeAt(0);
        nodes.append(first);
        QVERIFY(edits.save(token, payload(nodes))["changed"].toBool());
        const auto saved = store.load();
        auto expected = original["menu"].toArray();
        auto moved = expected.takeAt(0);
        expected.append(moved);
        QCOMPARE(saved["menu"].toArray(), expected);
        QCOMPARE(saved["future_preference"], original["future_preference"]);
        QVERIFY(!edits.cancel(token));
    }
    void invalidLayoutsRetainSession() {
        QTemporaryDir temp;
        Storage store(temp.filePath("menu.json"));
        store.save(fixture(), {});
        const auto before = store.revision();
        Layouts edits(store);
        auto begun = edits.begin();
        const auto token = begun["token"].toString();
        auto nodes = references(begun["entries"].toArray());
        for (const auto &invalid : {QString("[]"), QString("{}"), QString("[null]"),
                                    QString("[{\"id\":\"unknown\"}]"), QString("not json")}) {
            QVERIFY_EXCEPTION_THROWN(edits.save(token, invalid), Error);
            QVERIFY(edits.keep(token));
        }
        auto repeated = nodes;
        repeated.append(nodes[0]);
        QVERIFY_EXCEPTION_THROWN(edits.save(token, payload(repeated)), Error);
        auto forged = nodes;
        auto object = forged[0].toObject();
        object["command"] = QJsonArray{"touch", "/tmp/never"};
        forged[0] = object;
        QVERIFY_EXCEPTION_THROWN(edits.save(token, payload(forged)), Error);
        const auto id = nodes[0].toObject()["id"].toString();
        QVERIFY_EXCEPTION_THROWN(
            edits.save(token, "[{\"id\":\"bad\",\"\\u0069d\":\"" + id + "\"}]"), Error);
        QCOMPARE(store.revision().content, before.content);
        QVERIFY(!edits.save(token, payload(nodes))["changed"].toBool());
        QCOMPARE(store.revision().content, before.content);
    }
    void layoutConflictLimitsAndExpiry() {
        QTemporaryDir temp;
        Storage store(temp.filePath("menu.json"));
        store.save(fixture(), {});
        qint64 now = 0;
        Layouts edits(store, [&] { return now; });
        const auto first = edits.begin();
        for (int i = 0; i < 3; ++i)
            edits.begin();
        QVERIFY_EXCEPTION_THROWN(edits.begin(), Error);
        writeFile(store.path(), "{\"menu\":[]}");
        const auto token = first["token"].toString();
        QVERIFY_EXCEPTION_THROWN(edits.save(token, payload(references(first["entries"].toArray()))),
                                 Error);
        QVERIFY(edits.keep(token));
        now = 30 * 60 * 1000;
        QVERIFY_EXCEPTION_THROWN(edits.keep(token), Error);
        QVERIFY(edits.begin()["ok"].toBool());
    }
};
QTEST_GUILESS_MAIN(ModelTests)
#include "model_test.moc"
