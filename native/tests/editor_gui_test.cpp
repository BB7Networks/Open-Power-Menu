#include "editor_catalog.hpp"
#include "editor_session.hpp"
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QGuiApplication>
#include <QJsonDocument>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickItem>
#include <QQuickWindow>
#include <QTemporaryDir>
#include <QtTest>
#include <QAccessible>
#include <QCursor>
#include <algorithm>
#if defined(__GLIBC__)
#include <malloc.h>
#endif

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
        QCursor::setPos(item->mapToGlobal(QPointF(item->width()/2,item->height()/2)).toPoint());
        QTest::qWait(10);
        QTest::mouseClick(
            item->window(), Qt::LeftButton, Qt::NoModifier,
            item->mapToScene(QPointF(item->width() / 2, item->height() / 2)).toPoint());
        QCoreApplication::processEvents();
        return true;
    }
    bool clickText(const QString &text, QQuickWindow *scope = nullptr) {
        const auto find = [&](auto &&self, QQuickItem *root) -> QQuickItem * {
            const auto children = root->childItems();
            for (auto it = children.crbegin(); it != children.crend(); ++it)
                if (auto *item = self(self, *it)) return item;
            auto label = root->property("text").toString().remove('&');
            // KDE's standard Open button is "Open..."; Basic uses "Open".
            if (label.endsWith("...")) label.chop(3);
            else if (label.endsWith(QChar(0x2026))) label.chop(1);
            if (clickable(root) && (label == text || root->property("fileName").toString() == text)) return root;
            return nullptr;
        };
        for (auto *top : QGuiApplication::topLevelWindows()) {
            auto *window = qobject_cast<QQuickWindow *>(top);
            if (!window || !window->isVisible() || (scope && window != scope)) continue;
            if (auto *item = find(find, window->contentItem())) {
                const QPointF center(item->width()/2, item->height()/2);
                // Native popup grabs consult the platform pointer position.
                // Synthetic clicks alone can leave it over a closed picker.
                QCursor::setPos(item->mapToGlobal(center).toPoint());
                QTest::qWait(10);
                QTest::mouseClick(item->window(), Qt::LeftButton, Qt::NoModifier,
                    item->mapToScene(center).toPoint());
                QCoreApplication::processEvents();
                return true;
            }
        }
        return false;
    }
  public:
    int profileMemory(const QString &output) {
        // Explicit developer mode, never an ordinary CTest assertion or a
        // threshold claim. The normal GUI suite still verifies correctness.
        QTemporaryDir temp;
        Storage store(temp.filePath("menu.json"));
        auto config = defaults();
        store.save(config, {});
        QFile backup(temp.filePath("menu.json.bak-profile"));
        if (!backup.open(QIODevice::WriteOnly)) qFatal("Cannot write memory fixture");
        backup.write(QJsonDocument(config).toJson()); backup.close();
        EditorSession session(store);
        EditorCatalog catalog; catalog.refresh();
        QQmlApplicationEngine engine;
        engine.rootContext()->setContextProperty("editorSession", &session);
        engine.rootContext()->setContextProperty("editorCatalog", &catalog);
        engine.load(QUrl("qrc:/editor/qml/Main.qml"));
        if (engine.rootObjects().isEmpty()) qFatal("Cannot load memory profile window");
        auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().first());
        if (!window || !QTest::qWaitForWindowExposed(window)) qFatal("Memory profile window not exposed");
        QJsonArray samples;
        const auto sample = [&](const QString &phase) {
            QTest::qWait(300);
            QCoreApplication::sendPostedEvents(nullptr, QEvent::DeferredDelete);
            QFile smaps("/proc/self/smaps_rollup");
            if (!smaps.open(QIODevice::ReadOnly)) qFatal("Cannot read process memory");
            QJsonObject row{{"phase", phase}, {"qml_objects", window->findChildren<QObject *>().size()}};
            const auto bytes = smaps.readAll();
            for (const auto &line : bytes.split('\n')) {
                const auto parts = line.simplified().split(' ');
                if (parts.size() > 1 && (parts[0] == "Pss:" || parts[0] == "Rss:"))
                    row[QString::fromLatin1(parts[0].chopped(1)) + "_KiB"] = parts[1].toInt();
            }
            samples.append(row);
        };
        QTest::qWait(1700); sample("startup_general_2s");
        if (!click(window, "layoutTab")) qFatal("Cannot open Layout"); sample("layout");
        if (!click(window, "backupsTab")) qFatal("Cannot open Backups");
        session.refreshBackups(); session.selectBackup("menu.json.bak-profile"); sample("backups_preview");
        const auto id = QJsonDocument::fromJson(session.layoutJson().toUtf8()).object()["entries"].toArray()[0].toObject()["id"].toString();
        auto *dialog = window->findChild<QObject *>("entryDialog");
        if (!dialog) qFatal("Missing profile entry dialog");
        for (int batch = 0; batch < 5; ++batch) {
            if (!click(window, "layoutTab")) qFatal("Cannot open Layout");
            for (int edit = 0; edit < 100; ++edit) {
                if (!session.editItem(id, QString::fromUtf8(QJsonDocument(QJsonObject{{"label", QString("Edit %1/%2").arg(batch).arg(edit)}}).toJson())))
                    qFatal("Profile edit failed");
                QCoreApplication::processEvents();
            }
            for (int edit = 0; edit < 50; ++edit) session.undo();
            for (int edit = 0; edit < 50; ++edit) session.redo();
            for (int cycle = 0; cycle < 10; ++cycle) {
                if (!QMetaObject::invokeMethod(dialog, "begin", Q_ARG(QVariant, "command"), Q_ARG(QVariant, id), Q_ARG(QVariant, "")))
                    qFatal("Cannot open profile dialog");
                QTest::qWait(170);
                QMetaObject::invokeMethod(dialog, "reject");
                QTest::qWait(170);
            }
            if (!click(window, "backupsTab")) qFatal("Cannot open Backups");
            for (int cycle = 0; cycle < 20; ++cycle) {
                session.refreshBackups(); session.selectBackup("menu.json.bak-profile");
                QCoreApplication::processEvents();
            }
            sample(QString("after_%1_edits_%2_dialog_cycles").arg((batch + 1) * 100).arg((batch + 1) * 10));
        }
        session.reload(true); engine.collectGarbage();
        if (!click(window, "generalTab")) qFatal("Cannot reopen General");
        QTest::qWait(1700); sample("reloaded_idle_2s");
#if defined(__GLIBC__)
        // Diagnostic only: distinguish retained allocator pages from live QML
        // objects. Never trim the production application's allocator.
        malloc_trim(0); sample("diagnostic_allocator_trim");
#endif
        QFile report(output);
        if (!report.open(QIODevice::WriteOnly)) qFatal("Cannot write memory profile");
        report.write(QJsonDocument(QJsonObject{{"qt", qVersion()}, {"samples", samples}}).toJson());
        return 0;
    }
  private slots:
    void customizationControlsPersistThroughKeyboardInput() {
        QTemporaryDir temp;
        Storage store(temp.filePath("menu.json"));
        store.save(defaults(), {});
        EditorCatalog catalog;
        // Recreate both session and real window to check persisted selections.
        for (int pass = 0; pass < 2; ++pass) {
            EditorSession session(store);
            QQmlApplicationEngine engine;
            engine.rootContext()->setContextProperty("editorSession", &session);
            engine.rootContext()->setContextProperty("editorCatalog", &catalog);
            engine.load(QUrl("qrc:/editor/qml/Main.qml"));
            QVERIFY(!engine.rootObjects().isEmpty());
            auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().first());
            QVERIFY(QTest::qWaitForWindowExposed(window));
            window->requestActivate();
            window->contentItem()->forceActiveFocus();
            window->resize(620, 480);
            QTest::qWait(50); // Let layouts settle before coordinate input.
            const auto control = [&](const char *name) {
                return window->findChild<QQuickItem *>(QString::fromLatin1(name));
            };
            const auto chooseLast = [&](QQuickItem *item) {
                const auto focused = [&] { return item->hasActiveFocus() || (window->activeFocusItem() && item->isAncestorOf(window->activeFocusItem())); };
                for (int attempt = 0; attempt < 100 && !focused(); ++attempt)
                    QTest::keyClick(window, Qt::Key_Tab);
                if (!focused()) return false;
                QTest::keyClick(window, Qt::Key_End);
                return true;
            };
            for (const char *name : {"menuTheme", "menu_density", "menu_width", "menu_height_mode", "menu_custom_height", "menu_icon_size", "hoverMode", "hoverDelay"}) {
                auto *item = control(name);
                QVERIFY(item);
                auto *accessible = QAccessible::queryAccessibleInterface(item);
                QVERIFY(accessible);
                QVERIFY(!accessible->text(QAccessible::Name).isEmpty());
            }
            if (pass == 0) {
                for (const char *name : {"menu_density", "menu_width", "menu_height_mode", "menu_icon_size", "hoverMode"})
                {
                    QVERIFY(chooseLast(control(name)));
                    auto *view = control("generalPreferences");
                    QVERIFY(view);
                    const auto visible = [&] {
                        const QRectF viewport(view->mapToScene(QPointF(0,0)), QSizeF(view->width(),view->height()));
                        auto *item=control(name);
                        return viewport.contains(QRectF(item->mapToScene(QPointF(0,0)),QSizeF(item->width(),item->height())));
                    };
                    QTRY_VERIFY(visible());
                }
                auto *height = control("menu_custom_height");
                QVERIFY(height->isEnabled());
                height->forceActiveFocus(); QTest::keyClick(window, Qt::Key_Up);
                QCOMPARE(session.configuration()["menu_custom_height"].toInt(), 610);
                auto *reset = control("resetMenuHeight");
                reset->forceActiveFocus(); QTest::keyClick(window, Qt::Key_Space);
                QVERIFY(!height->isEnabled());
                QCOMPARE(session.configuration()["menu_height_mode"].toString(), "auto");
                QCOMPARE(session.configuration()["menu_custom_height"].toInt(), 610);
                auto *delay = control("hoverDelay");
                QVERIFY(delay->isEnabled());
                delay->forceActiveFocus();
                for (int i = 0; i < 3; ++i) QTest::keyClick(window, Qt::Key_Up);
                QCOMPARE(session.configuration()["submenu_hover_delay_ms"].toInt(), 600);
                auto *icons = control("showMenuIcons");
                icons->forceActiveFocus(); QTest::keyClick(window, Qt::Key_Space);
                QVERIFY(!control("menu_icon_size")->isEnabled());
                QTest::keyClick(window, Qt::Key_Space);
                QVERIFY(control("menu_icon_size")->isEnabled());
                QVERIFY(click(window, "saveConfiguration"));
                QVERIFY(!session.dirty());
            }
            QCOMPARE(control("menu_density")->property("currentIndex").toInt(), 2);
            QCOMPARE(control("menu_width")->property("currentIndex").toInt(), 2);
            QCOMPARE(control("menu_icon_size")->property("currentIndex").toInt(), 2);
            QCOMPARE(control("hoverMode")->property("currentIndex").toInt(), 2);
            QCOMPARE(control("hoverDelay")->property("value").toInt(), 600);
            const auto output=qEnvironmentVariable("OPM_QUALIFICATION_SCREENSHOTS");
            if (!output.isEmpty()) {
                QTest::qWait(50);
                QDir().mkpath(output);
                QVERIFY(window->grabWindow().save(output + QString("/editor-general-narrow-%1.png").arg(pass)));
            }
            QVERIFY(click(window, "layoutTab"));
            QVERIFY(click(window, "backupsTab"));
            QVERIFY(click(window, "generalTab"));
            QCOMPARE(control("hoverDelay")->property("value").toInt(), 600);
            window->close();
        }
    }

    void appearanceMouseAndMinimumGeometry() {
        QTemporaryDir temp;
        Storage store(temp.filePath("menu.json"));
        auto personal = defaults();
        personal["appearance"] = "aero"; // Existing dark-theme value remains valid.
        personal["menu"] = QJsonArray{QJsonObject{{"label", "Personal command"}, {"command", QJsonArray{"/bin/true"}}}};
        store.save(personal, {});
        EditorSession session(store); EditorCatalog catalog;
        QQmlApplicationEngine engine;
        engine.rootContext()->setContextProperty("editorSession", &session);
        engine.rootContext()->setContextProperty("editorCatalog", &catalog);
        engine.load(QUrl("qrc:/editor/qml/Main.qml"));
        QVERIFY(!engine.rootObjects().isEmpty());
        auto *window=qobject_cast<QQuickWindow *>(engine.rootObjects().first());
        QVERIFY(QTest::qWaitForWindowExposed(window));
        const auto control=[&](const char *name){return window->findChild<QQuickItem *>(name);};
        for(const auto size : {QSize(620,480), QSize(960,720), QSize(1280,900)}) {
            window->resize(size); window->requestActivate();
            auto *theme=control("menuTheme"); QVERIFY(theme);
            theme->forceActiveFocus();
            QTest::qWait(50);
            for(const char *name : {"menuTheme", "menu_density", "menu_width", "menu_height_mode",
                    "menu_custom_height", "resetMenuHeight", "menu_icon_size", "hoverMode", "hoverDelay",
                    "saveConfiguration", "closeConfiguration"}) {
                auto *item=control(name); QVERIFY(item);
                const auto left=item->mapToScene(QPointF()).x();
                QVERIFY2(left >= 0 && left+item->width() <= window->width(), name);
                if(item->property("implicitContentWidthPolicy").isValid())
                    QVERIFY2(item->width() >= item->implicitWidth(), name);
            }
            auto *popup=theme->property("popup").value<QObject *>(); QVERIFY(popup);
            QVERIFY(click(window,"menuTheme"));
            QTRY_VERIFY(popup->property("opened").toBool());
            QVERIFY(clickText("Aero Light"));
            QTRY_VERIFY(!popup->property("visible").toBool());
            QCOMPARE(session.configuration()["appearance"].toString(), "aero-light");
            QVERIFY(click(window,"saveConfiguration"));
            QCOMPARE(store.load()["appearance"].toString(), "aero-light");
            QCOMPARE(store.load()["menu"], personal["menu"]);
            theme->forceActiveFocus(); QTest::qWait(50);
            const auto output=qEnvironmentVariable("OPM_QUALIFICATION_SCREENSHOTS");
            if(!output.isEmpty()) {
                QDir().mkpath(output);
                QVERIFY(window->grabWindow().save(output+QString("/editor-theme-%1x%2.png").arg(size.width()).arg(size.height())));
            }
            QVERIFY(click(window,"menuTheme"));
            QTRY_VERIFY(popup->property("opened").toBool());
            QVERIFY(clickText("Use the desktop theme"));
            QTRY_VERIFY(!popup->property("visible").toBool());
            QCOMPARE(session.configuration()["appearance"].toString(), "native");
        }
        window->close();
    }

    void portableDialogsCancelApplyAndRecover() {
        if (QGuiApplication::platformName() == "offscreen")
            QSKIP("Native popup input requires a display seat; install xvfb/xauth to run this case through CTest");
        QTemporaryDir temp;
        Storage store(temp.filePath("menu.json"));
        auto original = defaults(); original["backup_retention"] = 0;
        store.save(original, {});
        EditorSession session(store); EditorCatalog catalog;
        QQmlApplicationEngine engine;
        engine.rootContext()->setContextProperty("editorSession", &session);
        engine.rootContext()->setContextProperty("editorCatalog", &catalog);
        engine.load(QUrl("qrc:/editor/qml/Main.qml"));
        QVERIFY(!engine.rootObjects().isEmpty());
        auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().first());
        QVERIFY(QTest::qWaitForWindowExposed(window));
        window->resize(620,480);
        QTest::qWait(50);
        window->requestActivate();
        QTRY_VERIFY(QGuiApplication::focusWindow());
        QVERIFY(click(window, "backupsTab"));
        auto *exportPicker = window->findChild<QObject *>("exportPicker");
        auto *importPicker = window->findChild<QObject *>("importPicker");
        auto *preview = window->findChild<QObject *>("importPreview");
        QVERIFY(exportPicker && importPicker && preview);
        // Exercise the shipped fallback file picker with keyboard input. The
        // application attribute affects this harness only, not production.
        const auto chooseFile = [&](QObject *picker, const QString &path) {
            picker->setProperty("currentFolder", QUrl::fromLocalFile(temp.path()));
            QTest::qWait(200);
            if (picker == importPicker)
                return clickText(QFileInfo(path).fileName()) && clickText("Open");
            QQuickItem *field = nullptr;
            for (auto *top : QGuiApplication::topLevelWindows())
                if (auto *quick = qobject_cast<QQuickWindow *>(top))
                    if ((field = visualItem(quick->contentItem(), "fileNameTextField"))) break;
            if (!field) return false;
            field->window()->requestActivate();
            field->forceActiveFocus();
            QTest::keyClick(field->window(), Qt::Key_A, Qt::ControlModifier);
            const auto filename = QFileInfo(path).fileName();
            for (const auto character : filename) QTest::keyClick(field->window(), character.toLatin1());
            if (field->property("text").toString() != filename) return false;
            if (!clickText("Save", field->window())) return false;
            QTest::qWait(150);
            return true;
        };
        QVERIFY(click(window, "exportConfiguration"));
        QTRY_VERIFY(exportPicker->property("visible").toBool());
        QTest::qWait(200);
        QTRY_VERIFY(QGuiApplication::focusWindow());
        QVERIFY(clickText("Cancel"));
        QTRY_VERIFY(!exportPicker->property("visible").toBool());
        QCOMPARE(store.load(), original);
        const auto path = temp.filePath("portable.json");
        QVERIFY(click(window, "exportConfiguration"));
        QTRY_VERIFY(exportPicker->property("visible").toBool());
        QVERIFY(chooseFile(exportPicker, path));
        QTRY_VERIFY(QFile::exists(path));
        QFile exported(path); QVERIFY(exported.open(QIODevice::ReadOnly));
        const auto exportedBytes = exported.readAll(); exported.close();
        QVERIFY(click(window, "exportConfiguration"));
        QTRY_VERIFY(exportPicker->property("visible").toBool());
        QVERIFY(chooseFile(exportPicker, path));
        QVERIFY(clickText("Yes")); // Confirm the file picker's overwrite question.
        QTRY_VERIFY(!exportPicker->property("visible").toBool());
        QVERIFY(!session.error().isEmpty());
        QVERIFY(window->findChild<QObject *>("portableStatus")->property("text").toString().isEmpty());
        QVERIFY(exported.open(QIODevice::ReadOnly));
        QCOMPARE(exported.readAll(), exportedBytes); exported.close();
        auto incoming = original; incoming["menu_density"] = "compact";
        incoming["menu"] = QJsonArray{QJsonObject{{"label", "Imported"}, {"command", QJsonArray{"/opm/missing"}}}};
        QFile file(path); QVERIFY(file.open(QIODevice::WriteOnly));
        file.write(QJsonDocument(incoming).toJson()); file.close();
        const auto openImport = [&] {
            if (!click(window, "importConfiguration")) return false;
            QTest::qWait(200);
            return chooseFile(importPicker, path);
        };
        QVERIFY(openImport());
        QTRY_VERIFY(preview->property("opened").toBool());
        QVERIFY(window->findChild<QObject *>("importPreviewText")->property("text").toString().contains("/opm/missing"));
        QVERIFY(clickText("Cancel"));
        QTRY_VERIFY(!preview->property("visible").toBool());
        QCOMPARE(store.load(), original);
        QVERIFY(!session.applyImport()); // Cancel invalidates the preview.
        QVERIFY(openImport());
        QTRY_VERIFY(preview->property("opened").toBool());
        QSignalSpy applied(preview, SIGNAL(applied()));
        // Source changes after the visible preview must fail without data loss.
        incoming["menu_width"] = "wide";
        QVERIFY(file.open(QIODevice::WriteOnly)); file.write(QJsonDocument(incoming).toJson()); file.close();
        QVERIFY(clickText("Apply"));
        QTRY_COMPARE(applied.count(), 1);
        QTRY_VERIFY(!preview->property("visible").toBool());
        QCOMPARE(session.errorCode(), "conflict");
        QCOMPARE(store.load(), original);
        QVERIFY(openImport());
        QTRY_VERIFY(preview->property("opened").toBool());
        QVERIFY(clickText("Apply"));
        QTRY_COMPARE(applied.count(), 2);
        QTRY_VERIFY(!preview->property("visible").toBool());
        QCOMPARE(store.load()["menu"], incoming["menu"]);
        QCOMPARE(store.backups().size(), 1);
        QVERIFY(store.backups().first().protectedCopy);
        const auto backup = ("backupEntry:" + store.backups().first().name).toUtf8();
        QTRY_VERIFY(click(window, backup.constData()));
        QVERIFY(click(window, "restoreBackup"));
        auto *confirm = window->findChild<QObject *>("confirmationDialog");
        QTRY_VERIFY(confirm->property("opened").toBool());
        QVERIFY(clickText("Yes"));
        QTRY_COMPARE(store.load(), original);
        QTRY_VERIFY(!confirm->property("visible").toBool());
        QVERIFY(file.open(QIODevice::WriteOnly)); file.write("{"); file.close();
        QVERIFY(openImport());
        QVERIFY(!preview->property("visible").toBool());
        QVERIFY(!session.error().isEmpty());
        QCOMPARE(store.load(), original);
        QVERIFY(session.preference(R"({"menu_density":"compact"})"));
        QVERIFY(!window->findChild<QQuickItem *>("importConfiguration")->isEnabled());
        QVERIFY(session.reload(true));
        window->close();
    }
    void removedSubmenuViewportStateIsReleased() {
        QTemporaryDir temp;
        Storage store(temp.filePath("menu.json"));
        auto config = defaults();
        config["menu"] = QJsonArray{QJsonObject{{"submenu", "Group"}, {"items", QJsonArray{}}}};
        store.save(config, {});
        EditorSession session(store); EditorCatalog catalog;
        QQmlApplicationEngine engine;
        engine.rootContext()->setContextProperty("editorSession", &session);
        engine.rootContext()->setContextProperty("editorCatalog", &catalog);
        engine.load(QUrl("qrc:/editor/qml/Main.qml"));
        QVERIFY(!engine.rootObjects().isEmpty());
        auto *window = engine.rootObjects().first();
        const auto id = QJsonDocument::fromJson(session.layoutJson().toUtf8()).object()["entries"].toArray()[0].toObject()["id"].toString();
        // Exercise the real QML draft update and the native removal/Undo path.
        engine.globalObject().setProperty("profileWindow", engine.newQObject(window));
        engine.globalObject().setProperty("profileGroup", id);
        auto result = engine.evaluate("profileWindow.syncLayout(); profileWindow.layoutDraft.views = {'': {contentY: 10}}; profileWindow.layoutDraft.views[profileGroup] = {contentY: 20}; Object.keys(profileWindow.layoutDraft.views).length");
        QCOMPARE(result.toInt(), 2);
        QVERIFY(session.removeItem(id));
        QCOMPARE(engine.evaluate("Object.keys(profileWindow.layoutDraft.views).length").toInt(), 1);
        QCOMPARE(engine.evaluate("profileWindow.layoutDraft.views[''].contentY").toInt(), 10);
        session.undo();
        QCOMPARE(engine.evaluate("Object.keys(profileWindow.layoutDraft.views).length").toInt(), 1);
    }

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
    QCoreApplication::setAttribute(Qt::AA_DontUseNativeDialogs);
    QGuiApplication app(argc, argv);
    EditorGuiTests tests;
    if (argc == 3 && QString::fromLocal8Bit(argv[1]) == "--profile-memory")
        return tests.profileMemory(QString::fromLocal8Bit(argv[2]));
    return QTest::qExec(&tests, argc, argv);
}
#include "editor_gui_test.moc"
