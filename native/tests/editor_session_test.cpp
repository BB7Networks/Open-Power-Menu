#include "editor_session.hpp"
#include <QDir>
#include <QFile>
#include <QJsonDocument>
#include <QTemporaryDir>
#include <QtTest>

using namespace Opm;
static void put(const QString &path, const QByteArray &bytes) {
    QFile file(path);
    QVERIFY(file.open(QIODevice::WriteOnly));
    QCOMPARE(file.write(bytes), bytes.size());
}
static QJsonObject fixture() {
    return decode(QByteArray(
        R"({"menu":[{"label":"Original","commands":[["true","a;b"],["false"]],"desktop_file":"/tmp/app.desktop","future":9223372036854775807},{"submenu":"Group","items":[{"command":["missing-app"],"unknown":{"kept":true}}]}],"unknown":9223372036854775807,"backup_retention":0})"));
}
static QJsonArray entries(const EditorSession &editor) {
    return QJsonDocument::fromJson(editor.layoutJson().toUtf8()).object()["entries"].toArray();
}
static QString id(const QJsonValue &entry) {
    return entry.toObject()["id"].toString();
}
static QJsonArray refs(const QJsonArray &items) {
    QJsonArray result;
    for (const auto &value : items) {
        const auto item = value.toObject();
        QJsonObject node{{"id", item["id"]}};
        if (item["kind"] == "submenu")
            node["items"] = refs(item["items"].toArray());
        result.append(node);
    }
    return result;
}
static QString json(const QJsonArray &items) {
    return QString::fromUtf8(QJsonDocument(items).toJson(QJsonDocument::Compact));
}
class EditorTests : public QObject {
    Q_OBJECT
  private slots:
    void importBoundsParentsAndFreshProfile() {
        QTemporaryDir dir;
        Storage store(dir.filePath("fresh/menu.json"));
        EditorSession editor(store);
        const auto path = dir.filePath("input.json");
        const auto url = QUrl::fromLocalFile(path);
        put(path, QByteArray(MaxConfigBytes + 1, ' '));
        QVERIFY(editor.previewImport(url).isEmpty());
        QCOMPARE(editor.errorCode(), "too-large");
        QVERIFY(!store.revision().content);
        // Both JSON extension depth and menu depth have independent bounds.
        put(path, QByteArray("{\"extension\":") + QByteArray(260, '[') + "0" + QByteArray(260, ']') + "}");
        QVERIFY(editor.previewImport(url).isEmpty());
        auto nested = QJsonArray{QJsonObject{{"command", QJsonArray{"/bin/true"}}}};
        for (int i = 0; i < 10; ++i)
            nested = QJsonArray{QJsonObject{{"submenu", "Nested"}, {"items", nested}}};
        put(path, QJsonDocument(QJsonObject{{"menu", nested}}).toJson());
        QVERIFY(editor.previewImport(url).isEmpty());
        auto config = fixture(); // Legacy schema without a version field.
        put(path, QJsonDocument(config).toJson());
        const auto linked = dir.filePath("linked");
        QVERIFY(QFile::link(dir.path(), linked));
        QVERIFY(editor.previewImport(QUrl::fromLocalFile(linked + "/input.json")).isEmpty());
        QVERIFY(!editor.exportConfiguration(QUrl::fromLocalFile(linked + "/export.json")));
        QVERIFY(!QFile::exists(dir.filePath("export.json")));
        const auto preview = editor.previewImport(url);
        QVERIFY(!preview.isEmpty());
        QVERIFY(preview.contains("No active configuration file"));
        QVERIFY(editor.applyImport());
        QCOMPARE(store.load()["menu"], config["menu"]);
        QCOMPARE(store.load()["unknown"], config["unknown"]);
        QVERIFY(store.backups().isEmpty()); // No previous file to preserve.
        // Replacing the source inode with identical bytes is still stale.
        const auto active = store.revision();
        QVERIFY(!editor.previewImport(url).isEmpty());
        QVERIFY(QFile::rename(path, dir.filePath("old.json")));
        put(path, QJsonDocument(config).toJson());
        QVERIFY(!editor.applyImport());
        QCOMPARE(editor.errorCode(), "conflict");
        QCOMPARE(store.revision(), active);
        editor.cancelImport();
        QVERIFY(!editor.previewImport(url).isEmpty());
        QVERIFY(editor.applyImport()); // A new preview recovers after failure.
    }
    void customHeightSurvivesDensityResetAndReopen() {
        QTemporaryDir dir; Storage store(dir.filePath("menu.json"));
        store.save(fixture(), {});
        EditorSession editor(store);
        QVERIFY(editor.preference(R"({"menu_height_mode":"custom","menu_custom_height":750})"));
        QVERIFY(editor.save());
        QVERIFY(editor.preference(R"({"menu_density":"compact","menu_icon_size":"small"})"));
        QVERIFY(editor.save());
        QCOMPARE(store.load()["menu_custom_height"].toInt(), 750);
        QVERIFY(editor.preference(R"({"menu_height_mode":"auto"})"));
        QVERIFY(editor.save());
        EditorSession reopened(store);
        QCOMPARE(reopened.configuration()["menu_height_mode"].toString(), "auto");
        QCOMPARE(reopened.configuration()["menu_custom_height"].toInt(), 750);
        QVERIFY(reopened.preference(R"({"menu_height_mode":"custom"})"));
        QCOMPARE(reopened.configuration()["menu_custom_height"].toInt(), 750);
    }
    void portableRoundTripAndProtectedImport() {
        QTemporaryDir dir;
        Storage store(dir.filePath("menu.json"));
        auto original = fixture();
        original["launcher_applet_id"] = 987;
        store.save(original, {});
        EditorSession editor(store);
        QVERIFY(editor.preference(R"({"menu_density":"comfortable","menu_width":"wide","menu_height_mode":"custom","menu_custom_height":950,"menu_icon_size":"large","submenu_hover_delay_ms":600})"));
        const auto exported = QUrl::fromLocalFile(dir.filePath("portable.json"));
        QVERIFY(editor.exportConfiguration(exported));
        QFile file(exported.toLocalFile()); QVERIFY(file.open(QIODevice::ReadOnly));
        const auto bytes = file.readAll();
        const auto portable = parseJson(bytes).object();
        QVERIFY(!portable.contains("launcher_applet_id"));
        QVERIFY(!portable.contains("backup_retention"));
        QCOMPARE(portable["menu"], editor.configuration()["menu"]);
        QCOMPARE(portable["unknown"], original["unknown"]);
        QVERIFY(!editor.exportConfiguration(exported)); // exclusive, no overwrite
        QVERIFY(editor.previewImport(exported).isEmpty()); // dirty draft
        QVERIFY(editor.reload(true));
        const auto preview = editor.previewImport(exported);
        QVERIFY(preview.contains("missing-app"));
        QVERIFY(preview.contains("No command has been executed"));
        QVERIFY(editor.applyImport());
        QCOMPARE(store.load()["menu_density"].toString(), "comfortable");
        QCOMPARE(store.load()["menu_height_mode"].toString(), "custom");
        QCOMPARE(store.load()["menu_custom_height"].toInt(), 950);
        QCOMPARE(store.load()["launcher_applet_id"].toInt(), 987);
        QCOMPARE(store.load()["backup_retention"].toInt(), 0);
        QCOMPARE(store.load()["unknown"], original["unknown"]);
        QCOMPARE(store.backups().size(), 1);
        QVERIFY(store.backups()[0].protectedCopy);
        QVERIFY(store.backups()[0].name.contains(".pre-import-"));
        QVERIFY(editor.selectBackup(store.backups()[0].name));
        QVERIFY(editor.restoreBackup());
        QCOMPARE(store.load(), original);
    }
    void importRejectsInvalidStaleAndChangedDraft() {
        QTemporaryDir dir; Storage store(dir.filePath("menu.json"));
        store.save(fixture(), {}); EditorSession editor(store);
        const auto baseline = store.revision();
        const auto path = dir.filePath("input.json"); const auto url = QUrl::fromLocalFile(path);
        for (const QByteArray bytes : {QByteArray("{"), QByteArray("[]"), QByteArray(R"({"version":99,"menu":[]})"),
                QByteArray(R"({"menu":[{"command":"unsafe string"}]})"), QByteArray(R"({"menu_density":"huge"})")}) {
            put(path, bytes); QVERIFY(editor.previewImport(url).isEmpty()); QVERIFY(!editor.applyImport());
            QCOMPARE(store.revision(), baseline);
        }
        put(path, QJsonDocument(defaults()).toJson());
        QVERIFY(!editor.previewImport(url).isEmpty());
        put(path, QJsonDocument(fixture()).toJson());
        QVERIFY(!editor.applyImport()); QCOMPARE(editor.errorCode(), "conflict");
        QCOMPARE(store.revision(), baseline);
        QVERIFY(!editor.previewImport(url).isEmpty());
        QVERIFY(editor.preference(R"({"menu_density":"compact"})"));
        QVERIFY(!editor.applyImport()); QCOMPARE(editor.errorCode(), "unsaved");
        QCOMPARE(store.revision(), baseline); editor.undo();
        QVERIFY(!editor.previewImport(url).isEmpty());
        auto changed = fixture(); changed["menu_width"] = "wide"; store.save(changed, baseline);
        QVERIFY(!editor.applyImport()); QCOMPARE(editor.errorCode(), "conflict");
        QCOMPARE(store.load(), changed);
    }
    void importNeverExecutesAndRefusesLinks() {
        QTemporaryDir dir; Storage store(dir.filePath("menu.json"));
        store.save(fixture(), {}); EditorSession editor(store);
        const auto marker = dir.filePath("executed");
        const auto source = dir.filePath("input.json");
        auto cfg = defaults();
        cfg["menu"] = QJsonArray{QJsonObject{{"command", QJsonArray{"/usr/bin/touch", marker}}}};
        put(source, QJsonDocument(cfg).toJson());
        const auto url = QUrl::fromLocalFile(source);
        QVERIFY(!editor.previewImport(url).isEmpty());
        QVERIFY(editor.applyImport()); QVERIFY(!QFile::exists(marker));
        const auto link = dir.filePath("link.json"); QVERIFY(QFile::link(source, link));
        QVERIFY(editor.previewImport(QUrl::fromLocalFile(link)).isEmpty());
        QVERIFY(!editor.exportConfiguration(QUrl::fromLocalFile(link)));
        QVERIFY(editor.previewImport(QUrl("https://example.org/menu.json")).isEmpty());
        QVERIFY(editor.previewImport(QUrl::fromLocalFile(source)).size() > 0);
        editor.cancelImport(); QVERIFY(!editor.applyImport());
    }
    void metadataAndAlternativeCommandsSurviveEditing() {
        QTemporaryDir dir;
        Storage store(dir.filePath("menu.json"));
        const auto original = fixture();
        store.save(original, {});
        EditorSession editor(store);
        const auto first = id(entries(editor)[0]);
        QVERIFY(editor.editItem(first, R"({"label":"Renamed"})"));
        QVERIFY(editor.preference(R"({"appearance":"aero"})"));
        QVERIFY(editor.save());
        auto expected = original;
        auto menu = expected["menu"].toArray();
        auto item = menu[0].toObject();
        item["label"] = "Renamed";
        menu[0] = item;
        expected["menu"] = menu;
        expected["appearance"] = "aero";
        QCOMPARE(store.load(), expected);
        QVERIFY(store.revision().content->contains("9223372036854775807"));
        QVERIFY(editor.editItem(first, R"({"command":["true","changed argument"]})"));
        const auto changed = editor.configuration()["menu"].toArray()[0].toObject();
        QVERIFY(!changed.contains("commands"));
        QVERIFY(!changed.contains("desktop_file"));
        QCOMPARE(changed["future"], item["future"]);
        QVERIFY(editor.addItem(
            "", "", R"({"action":"terminal","future":{"integer":9223372036854775807}})"));
        const auto builtin = id(entries(editor).last());
        const auto beforeConversion = editor.configuration();
        QVERIFY(!editor.editItem(builtin, R"({"action":"terminal","command":["true"]})"));
        QVERIFY(editor.editItem(
            builtin, R"({"label":"My terminal","command":["true","literal argument"]})"));
        const auto converted = editor.configuration()["menu"].toArray().last().toObject();
        QVERIFY(!converted.contains("action"));
        QCOMPARE(converted["future"],
                 beforeConversion["menu"].toArray().last().toObject()["future"]);
        editor.undo();
        QCOMPARE(editor.configuration(), beforeConversion);
    }
    void undoRedoAddDuplicateRemoveAndReset() {
        QTemporaryDir dir;
        Storage store(dir.filePath("menu.json"));
        store.save(fixture(), {});
        EditorSession editor(store);
        const auto initial = editor.configuration();
        const auto first = id(entries(editor)[0]);
        QVERIFY(editor.duplicateItem(first));
        QCOMPARE(entries(editor).size(), 3);
        QVERIFY(editor.dirty());
        editor.undo();
        QCOMPARE(editor.configuration(), initial);
        QVERIFY(!editor.dirty());
        editor.redo();
        QCOMPARE(entries(editor).size(), 3);
        QVERIFY(id(entries(editor)[0]) != id(entries(editor)[1]));
        QVERIFY(editor.removeItem(id(entries(editor)[1])));
        QCOMPARE(editor.configuration(), initial);
        const auto parent = id(entries(editor)[1]);
        QVERIFY(editor.addItem(parent, "", R"({"submenu":"New","items":[{"separator":true}]})"));
        QCOMPARE(entries(editor)[1].toObject()["items"].toArray().size(), 2);
        QVERIFY(editor.preference(R"({"show_unavailable":true})"));
        const auto beforeReset = editor.configuration();
        QVERIFY(editor.resetLayout());
        QCOMPARE(editor.configuration()["unknown"], initial["unknown"]);
        QCOMPARE(editor.configuration()["show_unavailable"], defaults()["show_unavailable"]);
        editor.undo();
        QCOMPARE(editor.configuration(), beforeReset);
        QVERIFY(editor.preference(R"({"show_menu_icons":false})"));
        QVERIFY(!editor.canRedo());
    }
    void invalidEditsKeepDraftAndUndoState() {
        QTemporaryDir dir;
        Storage store(dir.filePath("menu.json"));
        store.save(fixture(), {});
        EditorSession editor(store);
        const auto original = editor.configuration();
        const auto first = id(entries(editor)[0]);
        QVERIFY(!editor.preference(R"({"backup_retention":1.2})"));
        QVERIFY(!editor.preference(R"({"auto_close_on_pointer_leave":1})"));
        QVERIFY(!editor.editItem(first, R"({"command":"echo unsafe"})"));
        QVERIFY(!editor.editItem(first, R"({"action":"shutdown"})"));
        QVERIFY(!editor.addItem("unknown", "", R"({"separator":true})"));
        QCOMPARE(editor.configuration(), original);
        QVERIFY(!editor.canUndo());
        QVERIFY(!editor.dirty());
        const auto error = editor.error();
        editor.checkExternal();
        QCOMPARE(editor.error(), error);
    }
    void nestedRearrangementPreservesHiddenDefinitions() {
        QTemporaryDir dir;
        Storage store(dir.filePath("menu.json"));
        store.save(fixture(), {});
        EditorSession editor(store);
        auto references = refs(entries(editor));
        auto first = references.takeAt(0);
        auto group = references[0].toObject();
        auto children = group["items"].toArray();
        children.append(first);
        group["items"] = children;
        references[0] = group;
        QVERIFY(editor.rearrange(json(references)));
        QCOMPARE(entries(editor).size(), 1);
        auto menu = fixture()["menu"].toArray();
        auto expectedGroup = menu[1].toObject();
        auto expectedChildren = expectedGroup["items"].toArray();
        expectedChildren.append(menu[0]);
        expectedGroup["items"] = expectedChildren;
        QCOMPARE(editor.configuration()["menu"].toArray(), QJsonArray{expectedGroup});
        editor.undo();
        QCOMPARE(editor.configuration(), fixture());
        QVERIFY(!editor.rearrange("[]"));
        auto injected = refs(entries(editor));
        auto node = injected[0].toObject();
        node["command"] = QJsonArray{"false"};
        injected[0] = node;
        QVERIFY(!editor.rearrange(json(injected)));
        QCOMPARE(editor.configuration(), fixture());
    }
    void twoEditorsCannotSilentlyOverwrite() {
        QTemporaryDir dir;
        Storage store(dir.filePath("menu.json"));
        store.save(fixture(), {});
        EditorSession first(store), second(store);
        QVERIFY(first.preference(R"({"appearance":"aero"})"));
        QVERIFY(first.save());
        QVERIFY(second.preference(R"({"show_menu_icons":false})"));
        const auto draft = second.configuration();
        QVERIFY(!second.save());
        QCOMPARE(second.errorCode(), QString("conflict"));
        QCOMPARE(second.configuration(), draft);
        QVERIFY(second.canUndo());
        QVERIFY(!second.reload());
        QVERIFY(!second.prepareOverwrite().isEmpty());
        QVERIFY(first.preference(R"({"backup_retention":2})"));
        QVERIFY(first.save());
        QVERIFY(!second.confirmOverwrite());
        QCOMPARE(second.errorCode(), QString("conflict"));
        QVERIFY(!second.prepareOverwrite().isEmpty());
        QVERIFY(second.confirmOverwrite());
        QCOMPARE(store.load(), draft);
        QVERIFY(!QDir(dir.path()).entryList({"menu.json.pre-overwrite-*"}).isEmpty());
        first.checkExternal();
        QVERIFY(first.externalChanged());
    }
    void noOpSaveDoesNotCreateBackupsAndSavepointTracksUndo() {
        QTemporaryDir dir;
        Storage store(dir.filePath("menu.json"));
        auto config = fixture();
        config["backup_retention"] = 3;
        const auto original = store.save(config, {});
        EditorSession editor(store);
        QVERIFY(editor.save());
        QCOMPARE(store.revision(), original);
        QVERIFY(store.backups().isEmpty());
        QVERIFY(editor.preference(R"({"appearance":"aero"})"));
        QVERIFY(editor.save());
        QVERIFY(!editor.dirty());
        editor.undo();
        QVERIFY(editor.dirty());
        editor.redo();
        QVERIFY(!editor.dirty());
    }
    void restoreRequiresExplicitDraftDiscard() {
        QTemporaryDir dir;
        Storage store(dir.filePath("menu.json"));
        const auto current = store.save(fixture(), {});
        auto old = defaults();
        old["menu"] = QJsonArray{};
        old["backup_retention"] = 0;
        put(dir.filePath("menu.json.bak-old"), QJsonDocument(old).toJson());
        EditorSession editor(store);
        QVERIFY(editor.preference(R"({"appearance":"aero"})"));
        QVERIFY(editor.selectBackup("menu.json.bak-old"));
        QVERIFY(editor.canRestore());
        QVERIFY(!editor.restoreBackup());
        QCOMPARE(store.revision(), current);
        QVERIFY(editor.restoreBackup(true));
        QCOMPARE(editor.configuration(), old);
        QVERIFY(!editor.dirty());
        QVERIFY(!editor.canUndo());
        QVERIFY(!QDir(dir.path()).entryList({"menu.json.pre-restore-*"}).isEmpty());
    }
    void invalidCurrentConfigurationDoesNotResetIt() {
        QTemporaryDir dir;
        Storage store(dir.filePath("menu.json"));
        put(store.path(), "invalid current file");
        const auto current = store.revision();
        EditorSession editor(store);
        QVERIFY(editor.dirty());
        QVERIFY(!editor.error().isEmpty());
        QVERIFY(!editor.save());
        QCOMPARE(store.revision(), current);
        QVERIFY(!editor.prepareOverwrite().isEmpty());
        QVERIFY(editor.confirmOverwrite());
        QCOMPARE(store.load(), defaults());
        const auto name = QDir(dir.path()).entryList({"menu.json.pre-overwrite-*"}).first();
        QFile preserved(dir.filePath(name));
        QVERIFY(preserved.open(QIODevice::ReadOnly));
        QCOMPARE(preserved.readAll(), QByteArray("invalid current file"));
    }
    void backupSelectionRemainsGuarded() {
        QTemporaryDir dir;
        Storage store(dir.filePath("menu.json"));
        store.save(fixture(), {});
        EditorSession editor(store);
        put(dir.filePath("menu.json.bak-one"), QJsonDocument(fixture()).toJson());
        QVERIFY(editor.selectBackup("menu.json.bak-one"));
        put(dir.filePath("menu.json.bak-one"), "changed corrupt source");
        QVERIFY(!editor.restoreBackup());
        QVERIFY(!editor.deleteBackup());
        QVERIFY(!editor.selectBackup("../outside"));
        QVERIFY(!editor.canDeleteBackup());
        QVERIFY(!editor.canRestore());
        QVERIFY(editor.selectBackup("menu.json.bak-one"));
        QVERIFY(!editor.canRestore());
        QVERIFY(editor.canDeleteBackup());
        QVERIFY(editor.deleteBackup());
    }
};
QTEST_GUILESS_MAIN(EditorTests)
#include "editor_session_test.moc"
