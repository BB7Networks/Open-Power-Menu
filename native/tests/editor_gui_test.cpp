#include "editor_catalog.hpp"
#include "editor_session.hpp"
#include <QDir>
#include <QFile>
#include <QGuiApplication>
#include <QJsonDocument>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickItem>
#include <QQuickWindow>
#include <QTemporaryDir>
#include <QtTest>
#include <algorithm>

using namespace Opm;
class EditorGuiTests : public QObject {
    Q_OBJECT
    bool clickable(QQuickItem *item) {
        return item && item->isVisible() && item->isEnabled() && item->width() > 0 &&
               item->height() > 0 && item->window();
    }
    QQuickItem *visualItem(QQuickItem *root, const QString &name) {
        if (root->objectName() == name && clickable(root))
            return root;
        for (auto *child : root->childItems())
            if (auto *found = visualItem(child, name))
                return found;
        return nullptr;
    }
    bool click(QQuickWindow *window, const char *name) {
        auto *item = window->findChild<QQuickItem *>(QString::fromLatin1(name));
        // Ignore delegates that are not currently clickable.
        if (!clickable(item))
            item = nullptr;
        if (!item)
            item = visualItem(window->contentItem(), QString::fromLatin1(name));
        // Popup delegates can belong to a separate visual tree/window in Qt 6.8.
        if (!item)
            for (auto *root : window->findChildren<QQuickItem *>()) {
                item = visualItem(root, QString::fromLatin1(name));
                if (item)
                    break;
            }
        if (!clickable(item))
            return false;
        QTest::mouseClick(
            item->window(), Qt::LeftButton, Qt::NoModifier,
            item->mapToScene(QPointF(item->width() / 2, item->height() / 2)).toPoint());
        QCoreApplication::processEvents();
        return true;
    }
  private slots:
    void actualWindowEditsUndoesAndSaves() {
        QTemporaryDir temp;
        Storage store(temp.filePath("menu.json"));
        auto config = defaults();
        config["menu"] = QJsonArray{};
        config["backup_retention"] = 0;
        store.save(config, {});
        QFile backup(temp.filePath("menu.json.bak-manual"));
        QVERIFY(backup.open(QIODevice::WriteOnly));
        backup.write(QJsonDocument(config).toJson());
        backup.close();
        EditorSession session(store);
        EditorCatalog catalog;
        catalog.refresh();
        QQmlApplicationEngine engine;
        QStringList warnings;
        connect(&engine, &QQmlEngine::warnings, this, [&](const QList<QQmlError> &errors) {
            for (const auto &error : errors)
                warnings.append(error.toString());
        });
        engine.rootContext()->setContextProperty("editorSession", &session);
        engine.rootContext()->setContextProperty("editorCatalog", &catalog);
        engine.load(QUrl("qrc:/editor/qml/Main.qml"));
        QVERIFY(!engine.rootObjects().isEmpty());
        auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().first());
        QVERIFY(window);
        QVERIFY(QTest::qWaitForWindowExposed(window));
        QVERIFY(click(window, "layoutTab"));
        auto *dialog = window->findChild<QObject *>("entryDialog");
        QVERIFY(dialog);
        QVERIFY(QMetaObject::invokeMethod(dialog, "begin", Q_ARG(QVariant, "command"),
                                          Q_ARG(QVariant, ""), Q_ARG(QVariant, "")));
        QTRY_VERIFY(dialog->property("opened").toBool());
        auto *name = window->findChild<QObject *>("entryName");
        auto *program = window->findChild<QObject *>("entryProgram");
        QVERIFY(name && program);
        QVERIFY(name->setProperty("text", "Native test command"));
        QVERIFY(click(window, "applyEntry"));
        QVERIFY(dialog->property("opened").toBool());
        QVERIFY(session.configuration()["menu"].toArray().isEmpty());
        QVERIFY(program->setProperty("text", "/bin/true"));
        QVERIFY(click(window, "applyEntry"));
        QTRY_VERIFY(!dialog->property("visible").toBool());
        QCOMPARE(session.configuration()["menu"].toArray().size(), 1);
        QVERIFY(session.dirty());
        QVERIFY(click(window, "duplicateEntry"));
        QCOMPARE(session.configuration()["menu"].toArray().size(), 2);
        QVERIFY(click(window, "undoLayout"));
        QCOMPARE(session.configuration()["menu"].toArray().size(), 1);
        QVERIFY(click(window, "redoLayout"));
        QCOMPARE(session.configuration()["menu"].toArray().size(), 2);
        QVERIFY(click(window, "editEntry"));
        QTRY_VERIFY(dialog->property("opened").toBool());
        QVERIFY(name->setProperty("text", "Renamed native command"));
        QVERIFY(click(window, "applyEntry"));
        QTRY_VERIFY(!dialog->property("visible").toBool());
        QVERIFY(click(window, "saveConfiguration"));
        QVERIFY(!session.dirty());
        QCOMPARE(store.load()["menu"].toArray()[1].toObject()["label"].toString(),
                 QString("Renamed native command"));
        QVERIFY(click(window, "backupsTab"));
        QVERIFY(window->findChild<QObject *>("backupHistory"));
        QTRY_VERIFY(click(window, "backupEntry:menu.json.bak-manual"));
        QVERIFY(session.canRestore());
        QCOMPARE(store.load()["menu"].toArray().size(), 2); // Preview leaves active file alone.
        QVERIFY(click(window, "restoreBackup"));
        auto *confirmation = window->findChild<QObject *>("confirmationDialog");
        QVERIFY(confirmation);
        QTRY_VERIFY(confirmation->property("opened").toBool());
        QVERIFY(QMetaObject::invokeMethod(confirmation, "reject"));
        QTRY_VERIFY(!confirmation->property("visible").toBool());
        QCOMPARE(store.load()["menu"].toArray().size(), 2);
        QVERIFY(click(window, "restoreBackup"));
        QTRY_VERIFY(confirmation->property("opened").toBool());
        QVERIFY(QMetaObject::invokeMethod(confirmation, "accept"));
        QTRY_VERIFY(!confirmation->property("visible").toBool());
        QVERIFY(store.load()["menu"].toArray().isEmpty());
        const auto copies = store.backups();
        const auto protectedCopy = std::find_if(
            copies.begin(), copies.end(), [](const Backup &entry) { return entry.protectedCopy; });
        QVERIFY(protectedCopy !=
                copies.end()); // Restore protects the old file with retention zero.
        const auto protectedRow = ("backupEntry:" + protectedCopy->name).toUtf8();
        QTRY_VERIFY(click(window, protectedRow.constData()));
        QVERIFY(click(window, "deleteBackup"));
        QTRY_VERIFY(confirmation->property("opened").toBool());
        QVERIFY(confirmation->property("title").toString().contains("protected"));
        QVERIFY(QMetaObject::invokeMethod(confirmation, "accept"));
        QTRY_VERIFY(!confirmation->property("visible").toBool());
        QCOMPARE(store.backups().size(), 1);
        QVERIFY(click(window, "layoutTab"));
        QVERIFY(QMetaObject::invokeMethod(dialog, "begin", Q_ARG(QVariant, "builtin"),
                                          Q_ARG(QVariant, ""), Q_ARG(QVariant, "")));
        QTRY_VERIFY(dialog->property("opened").toBool());
        auto *fallbacks = window->findChild<QObject *>("builtinFallbacks");
        QVERIFY(fallbacks && !fallbacks->property("text").toString().isEmpty());
        QVERIFY(QMetaObject::invokeMethod(dialog, "customizeBuiltin"));
        QCOMPARE(dialog->property("entryKind").toString(), QString("command"));
        QVERIFY(!program->property("text").toString().isEmpty());
        QVERIFY(program->setProperty("text", "/bin/true"));
        QVERIFY(click(window, "applyEntry"));
        QTRY_VERIFY(!dialog->property("visible").toBool());
        QCOMPARE(session.configuration()["menu"].toArray().size(), 1);
        QVERIFY(!session.configuration()["menu"].toArray()[0].toObject().contains("action"));
        QVERIFY(click(window, "editEntry"));
        QTRY_VERIFY(dialog->property("opened").toBool());
        QVERIFY(QMetaObject::invokeMethod(dialog, "chooseApplication"));
        auto *picker = window->findChild<QObject *>("applicationPicker");
        QVERIFY(picker);
        QTRY_VERIFY(picker->property("opened").toBool());
        auto *search = window->findChild<QObject *>("applicationSearch");
        QVERIFY(search && search->setProperty("text", "Native fixture"));
        auto *appList = window->findChild<QQuickItem *>("applicationList");
        QVERIFY(appList);
        QTRY_COMPARE(appList->property("count").toInt(), 1);
        QVERIFY(appList->width() > 0 && appList->height() > 0);
        QTRY_VERIFY(visualItem(appList, "applicationEntry:opm-native-fixture.desktop"));
        // QTRY evaluates its condition repeatedly; click exactly once because
        // choosing an application closes this popup.
        QVERIFY(click(window, "applicationEntry:opm-native-fixture.desktop"));
        QTRY_VERIFY(!picker->property("visible").toBool());
        QVERIFY(dialog->property("opened").toBool());
        QVERIFY(click(window, "applyEntry"));
        QTRY_VERIFY(!dialog->property("visible").toBool());
        const auto picked = session.configuration()["menu"].toArray()[0].toObject();
        QVERIFY(picked["desktop_file"].toString().endsWith("opm-native-fixture.desktop"));
        QCOMPARE(picked["command"].toArray()[2], picked["desktop_file"]);
        QVERIFY(click(window, "editEntry"));
        QTRY_VERIFY(dialog->property("opened").toBool());
        QVERIFY(program->setProperty("text", "/bin/true"));
        QVERIFY(click(window, "applyEntry"));
        QTRY_VERIFY(!dialog->property("visible").toBool());
        QVERIFY(!session.configuration()["menu"].toArray()[0].toObject().contains("desktop_file"));
        QCOMPARE(warnings, QStringList{});
        window->setProperty("closingApproved", true);
        window->close();
    }
    void catalogUsesKdeAndLeavesPanelsUntouched() {
        const auto configHome = qEnvironmentVariable("XDG_CONFIG_HOME");
        const auto panelFile = configHome + "/plasma-org.kde.plasma.desktop-appletsrc";
        const QByteArray contents(
            "[Containments][2]\nplugin=org.kde.panel\n[Containments][2][Applets][7]\nplugin=org."
            "kde.plasma.kickoff\n[Containments][2][Applets][8]\nplugin=org.openpowermenu.start\n["
            "Containments][3]\nplugin=org.kde.desktopcontainment\n[Containments][3][Applets][9]"
            "\nplugin=org.kde.plasma.kickoff\n");
        QFile panel(panelFile);
        QVERIFY(panel.open(QIODevice::WriteOnly));
        panel.write(contents);
        panel.close();
        EditorCatalog catalog;
        catalog.refresh();
        QCOMPARE(catalog.launchers().size(), 2);
        QCOMPARE(catalog.launchers()[1].toMap()["id"].toInt(), 7);
        QVERIFY(panel.open(QIODevice::ReadOnly));
        QCOMPARE(panel.readAll(), contents);
        QVERIFY(!catalog.actions().isEmpty());
        QVERIFY(!catalog.builtinDetails("terminal")["candidates"].toString().isEmpty());
        QVERIFY(!catalog.builtinDetails("terminal")["command"].toList().isEmpty());
        QVERIFY(catalog.builtinDetails("opm-no-such-action").isEmpty());
        QCOMPARE(catalog.localFile(QUrl("file:///tmp/program%20with%20spaces")),
                 QString("/tmp/program with spaces"));
        QVERIFY(catalog.applicationItem("opm-nonexistent.desktop").isEmpty());
        const auto applications = catalog.applications();
        QVERIFY(std::any_of(applications.begin(), applications.end(), [](const QVariant &row) {
            return row.toMap()["id"] == "opm-native-fixture.desktop";
        }));
        QVERIFY(std::none_of(applications.begin(), applications.end(), [](const QVariant &row) {
            return row.toMap()["id"] == "opm-hidden-fixture.desktop" ||
                   row.toMap()["id"] == "opm-unavailable-fixture.desktop";
        }));
        const auto definition =
            QJsonDocument::fromJson(catalog.applicationItem("opm-native-fixture.desktop").toUtf8())
                .object();
        const auto command = definition["command"].toArray();
        QCOMPARE(command.size(), 3);
        QVERIFY(command[0] == "kioclient" || command[0] == "kioclient6");
        QCOMPARE(command[1].toString(), QString("exec"));
        QCOMPARE(command[2], definition["desktop_file"]);
        const auto snapshotRoot =
            qEnvironmentVariable("XDG_DATA_HOME") + "/open-power-menu-recovery/widget-backups";
        QVERIFY(QDir().mkpath(snapshotRoot + "/org.openpowermenu.start-20260101-120000-123456789"));
        QVERIFY(QDir().mkpath(snapshotRoot + "/unrelated"));
        QVERIFY(catalog.snapshotStatus().contains("1 generated widget snapshots"));
    }
};
int main(int argc, char **argv) {
    QTemporaryDir paths;
    for (const auto &key :
         {"XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_RUNTIME_DIR"}) {
        const auto platform = qEnvironmentVariable("QT_QPA_PLATFORM");
        if (QString(key) == "XDG_RUNTIME_DIR" && (platform == "wayland" || platform == "xcb") &&
            !qEnvironmentVariableIsEmpty("XDG_RUNTIME_DIR"))
            continue;
        const auto path = paths.filePath(key);
        QDir().mkpath(path);
        QFile::setPermissions(path, QFile::ReadOwner | QFile::WriteOwner | QFile::ExeOwner);
        qputenv(key, path.toUtf8());
    }
    qputenv("XDG_CURRENT_DESKTOP", "KDE");
    qputenv("XDG_MENU_PREFIX", "opm-test-");
    const auto appRoot = qEnvironmentVariable("XDG_DATA_HOME") + "/applications";
    const auto menuRoot = qEnvironmentVariable("XDG_CONFIG_HOME") + "/menus";
    QDir().mkpath(appRoot);
    QDir().mkpath(menuRoot);
    const auto write = [](const QString &name, const QByteArray &bytes) {
        QFile file(name);
        if (!file.open(QIODevice::WriteOnly) || file.write(bytes) != bytes.size())
            qFatal("Cannot write GUI fixture");
    };
    write(menuRoot + "/opm-test-applications.menu",
          "<Menu><Name>Applications</Name><DefaultAppDirs/><Include><All/></Include></Menu>");
    write(appRoot + "/opm-native-fixture.desktop",
          "[Desktop Entry]\nType=Application\nName=Native fixture\nExec=/bin/true "
          "%k\nTerminal=true\nPath=/tmp\nCategories=Utility;\n");
    write(
        appRoot + "/opm-hidden-fixture.desktop",
        "[Desktop Entry]\nType=Application\nName=Hidden fixture\nExec=/bin/true\nNoDisplay=true\n");
    write(appRoot + "/opm-unavailable-fixture.desktop",
          "[Desktop Entry]\nType=Application\nName=Unavailable "
          "fixture\nExec=/bin/true\nTryExec=opm-no-such-program\n");
    QGuiApplication app(argc, argv);
    EditorGuiTests tests;
    return QTest::qExec(&tests, argc, argv);
}
#include "editor_gui_test.moc"
