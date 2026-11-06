#include "storage.hpp"
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
static void put(const QString &name, const QByteArray &bytes) {
    QFile file(name);
    if (!file.open(QIODevice::WriteOnly) || file.write(bytes) != bytes.size())
        qFatal("Fixture write failed");
}
static QByteArray bytes(const QJsonObject &config) {
    return QJsonDocument(config).toJson();
}
static QJsonObject config(int retention = 0) {
    auto value = defaults();
    value["menu"] = QJsonArray{};
    value["backup_retention"] = retention;
    value["future"] = QJsonObject{{"preserved", QJsonArray{1, "two", false}}};
    return value;
}
class RecoveryTests : public QObject {
    Q_OBJECT
  private slots:
    void missingAndPassivePreview() {
        QTemporaryDir dir;
        Storage store(dir.filePath("menu.json"));
        QVERIFY(store.backups().isEmpty());
        QVERIFY(!store.revision().content);
        const auto marker = dir.filePath("must-not-exist");
        auto value = config();
        value["menu"] = QJsonArray{QJsonObject{{"command", QJsonArray{"touch", marker}}}};
        put(dir.filePath("menu.json.bak-manual"), bytes(value));
        const auto preview = store.preview("menu.json.bak-manual");
        QVERIFY(preview.config);
        QCOMPARE(*preview.config, value);
        QVERIFY(preview.snapshot);
        QVERIFY(!QFile::exists(marker));
        QVERIFY(!store.revision().content);
        QCOMPARE(store.backups().size(), 1);
    }
    void restoreWithAutomaticBackupsDisabled() {
        QTemporaryDir dir;
        Storage store(dir.filePath("menu.json"));
        auto current = config();
        current["appearance"] = "aero";
        const auto revision = store.save(current, {});
        auto previous = config();
        put(dir.filePath("menu.json.bak-legacy"), bytes(previous));
        const auto selected = store.preview("menu.json.bak-legacy");
        const auto saved = store.restore(*selected.snapshot, revision);
        QCOMPARE(store.load(), previous);
        QCOMPARE(store.revision(), saved);
        const auto copies = QDir(dir.path()).entryList({"menu.json.pre-restore-*"}, QDir::Files);
        QCOMPARE(copies.size(), 1);
        QFile copy(dir.filePath(copies.first()));
        QVERIFY(copy.open(QIODevice::ReadOnly));
        QCOMPARE(copy.readAll(), *revision.content);
        QVERIFY(QFile::exists(dir.filePath("menu.json.bak-legacy")));
    }
    void restoreOverMalformedActiveConfiguration() {
        QTemporaryDir dir;
        Storage store(dir.filePath("menu.json"));
        put(store.path(), "{broken original");
        const auto revision = store.revision();
        put(dir.filePath("menu.json.bak-good"), bytes(config()));
        store.restore(*store.preview("menu.json.bak-good").snapshot, revision);
        QCOMPARE(store.load(), config());
        auto copies = QDir(dir.path()).entryList({"menu.json.pre-restore-*"}, QDir::Files);
        QFile copy(dir.filePath(copies.first()));
        QVERIFY(copy.open(QIODevice::ReadOnly));
        QCOMPARE(copy.readAll(), QByteArray("{broken original"));
    }
    void explicitOverwritePreservesCurrentRevision() {
        QTemporaryDir dir;
        Storage store(dir.filePath("menu.json"));
        put(store.path(), "{broken");
        const auto current = store.revision();
        store.save(config(), current, SaveReason::Overwrite);
        QCOMPARE(QDir(dir.path()).entryList({"menu.json.pre-overwrite-*"}, QDir::Files).size(), 1);
        QVERIFY_EXCEPTION_THROWN(store.save(config(), current, SaveReason::Overwrite), Error);
    }
    void changedSourceOrActiveFileCannotRestore() {
        QTemporaryDir dir;
        Storage store(dir.filePath("menu.json"));
        const auto current = store.save(config(), {});
        const auto name = QString("menu.json.bak-old");
        put(dir.filePath(name), bytes(config()));
        const auto first = store.preview(name);
        put(dir.filePath(name), bytes(config(1)));
        QVERIFY_EXCEPTION_THROWN(store.restore(*first.snapshot, current), Error);
        QCOMPARE(store.revision(), current);
        const auto second = store.preview(name);
        store.save(config(2), current);
        const auto changed = store.revision();
        QVERIFY_EXCEPTION_THROWN(store.restore(*second.snapshot, current), Error);
        QCOMPARE(store.revision(), changed);
        QVERIFY(QDir(dir.path()).entryList({"menu.json.pre-restore-*"}).isEmpty());
    }
    void selectedSourceSurvivesRetention() {
        QTemporaryDir dir;
        Storage store(dir.filePath("menu.json"));
        const auto current = store.save(config(), {});
        const auto old = QString("menu.json.bak-20000101T000000000000Z");
        const auto recent = QString("menu.json.bak-20010101T000000000000Z");
        put(dir.filePath(old), bytes(config(1)));
        put(dir.filePath(recent), bytes(config(1)));
        put(dir.filePath("menu.json.bak-user-note"), "manual history");
        store.restore(*store.preview(old).snapshot, current);
        QVERIFY(QFile::exists(dir.filePath(old)));
        QVERIFY(QFile::exists(dir.filePath(recent)));
        QVERIFY(QFile::exists(dir.filePath("menu.json.bak-user-note")));
    }
    void corruptAndOversizedBackupsCanOnlyBeDeleted() {
        QTemporaryDir dir;
        Storage store(dir.filePath("menu.json"));
        const auto current = store.save(config(), {});
        for (const auto &name : {"menu.json.bak-broken", "menu.json.bak-large"}) {
            put(dir.filePath(name), QString(name).endsWith("large")
                                        ? QByteArray(MaxConfigBytes + 1, ' ')
                                        : QByteArray("{broken"));
            const auto preview = store.preview(name);
            QVERIFY(!preview.config);
            QVERIFY(preview.snapshot);
            QVERIFY(!preview.error.isEmpty());
            QVERIFY_EXCEPTION_THROWN(store.restore(*preview.snapshot, current), Error);
            QCOMPARE(store.revision(), current);
            store.removeBackup(*preview.snapshot);
            QVERIFY(!QFile::exists(dir.filePath(name)));
        }
    }
    void protectedDeletionRequiresExplicitConfirmation() {
        QTemporaryDir dir;
        Storage store(dir.filePath("menu.json"));
        const auto name = QString("menu.json.pre-restore-old");
        put(dir.filePath(name), "invalid but precious");
        const auto preview = store.preview(name);
        QVERIFY(preview.protectedCopy);
        QVERIFY_EXCEPTION_THROWN(store.removeBackup(*preview.snapshot), Error);
        QVERIFY(QFile::exists(dir.filePath(name)));
        store.removeBackup(*preview.snapshot, true);
        QVERIFY(!QFile::exists(dir.filePath(name)));
    }
    void changedDeletedOrReplacedBackupCannotBeRemoved() {
        QTemporaryDir dir;
        Storage store(dir.filePath("menu.json"));
        const auto name = QString("menu.json.bak-selected");
        put(dir.filePath(name), "old");
        const auto original = store.preview(name);
        put(dir.filePath(name), "new");
        QVERIFY_EXCEPTION_THROWN(store.removeBackup(*original.snapshot), Error);
        const auto next = store.preview(name);
        put(dir.filePath("replacement"), "new");
        QVERIFY(!::rename(QFile::encodeName(dir.filePath("replacement")).constData(),
                          QFile::encodeName(dir.filePath(name)).constData()));
        QVERIFY_EXCEPTION_THROWN(store.removeBackup(*next.snapshot), Error);
        const auto last = store.preview(name);
        QFile::remove(dir.filePath(name));
        QVERIFY_EXCEPTION_THROWN(store.removeBackup(*last.snapshot), Error);
    }
    void unsafeFilesAndNamesAreRefused() {
        QTemporaryDir dir;
        Storage store(dir.filePath("menu.json"));
        const auto current = store.save(config(), {});
        QVERIFY(QFile::link(store.path(), dir.filePath("menu.json.bak-link")));
        QVERIFY(!::link(QFile::encodeName(store.path()).constData(),
                        QFile::encodeName(dir.filePath("menu.json.bak-hard")).constData()));
        QVERIFY(!::mkfifo(QFile::encodeName(dir.filePath("menu.json.bak-pipe")).constData(), 0600));
        QVERIFY(QDir().mkdir(dir.filePath("menu.json.bak-directory")));
        for (const auto &name : {"menu.json.bak-link", "menu.json.bak-hard", "menu.json.bak-pipe",
                                 "menu.json.bak-directory"}) {
            const auto preview = store.preview(name);
            QVERIFY(!preview.snapshot);
            QVERIFY(!preview.config);
            QVERIFY(!preview.error.isEmpty());
        }
        for (const auto &name :
             {"../menu.json.bak-escape", "menu.json", "/tmp/menu.json.bak-other", "manual-file"}) {
            QVERIFY_EXCEPTION_THROWN(store.preview(name), Error);
            BackupSnapshot fake;
            fake.name = name;
            QVERIFY_EXCEPTION_THROWN(store.removeBackup(fake, true), Error);
            QVERIFY_EXCEPTION_THROWN(store.restore(fake, current), Error);
        }
        QCOMPARE(store.revision(), current);
    }
    void unsafeDirectoryAndCooperativeLock() {
        QTemporaryDir dir;
        Storage store(dir.filePath("menu.json"));
        const auto current = store.save(config(), {});
        const auto name = QString("menu.json.bak-one");
        put(dir.filePath(name), bytes(config()));
        const auto selected = store.preview(name);
        const int lock = ::open(QFile::encodeName(dir.filePath(".menu.lock")).constData(), O_RDWR);
        QVERIFY(lock >= 0);
        QVERIFY(!::flock(lock, LOCK_EX | LOCK_NB));
        QVERIFY_EXCEPTION_THROWN(store.removeBackup(*selected.snapshot), Error);
        QVERIFY_EXCEPTION_THROWN(store.restore(*selected.snapshot, current), Error);
        ::close(lock);
        QVERIFY(!::chmod(QFile::encodeName(dir.path()).constData(), 0770));
        QVERIFY(!store.preview(name).snapshot);
        QVERIFY_EXCEPTION_THROWN(store.removeBackup(*selected.snapshot), Error);
        QVERIFY(!::chmod(QFile::encodeName(dir.path()).constData(), 0700));
        QCOMPARE(store.revision(), current);
    }
};
QTEST_GUILESS_MAIN(RecoveryTests)
#include "recovery_test.moc"
