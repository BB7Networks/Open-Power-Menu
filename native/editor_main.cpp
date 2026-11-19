#include "editor_catalog.hpp"
#include "editor_session.hpp"
#include "editor_launch.hpp"
#include <QCommandLineParser>
#include <QGuiApplication>
#include <QIcon>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickStyle>
#include <QQuickWindow>
#include <cstdio>
#include <cstring>

int main(int argc, char **argv) {
    // Resolve the live session before QGuiApplication can load a stale display
    // plugin or authentication path. The Core-only parent supervises startup.
    bool child = false;
    for (int i = 1; i < argc; ++i)
        if (std::strcmp(argv[i], "--opm-editor-child") == 0) child = true;
    if (!child) return Opm::coordinateEditor(argc, argv);
    QGuiApplication app(argc, argv);
    app.setApplicationName("Open Power Menu Configure");
    app.setApplicationVersion(OPM_NATIVE_VERSION);
    app.setOrganizationDomain("openpowermenu.org");
    // Bind this process to the Configure desktop entry on Wayland and use the
    // bundled, official OPM artwork (not a desktop theme's generic fallback).
    QGuiApplication::setDesktopFileName(QStringLiteral("org.openpowermenu.configure"));
    const QIcon editorIcon(QStringLiteral(":/editor/open-power-menu.svg"));
    QGuiApplication::setWindowIcon(editorIcon);
    QCommandLineParser parser;
    parser.addHelpOption();
    parser.addVersionOption();
    parser.addOption({"config", "Configuration file", "file"});
    parser.addOption({"smoke-test", "Load the native editor and exit after one event-loop cycle"});
    parser.addOption({"screenshot", "Capture the editor during a developer smoke test", "file"});
    QCommandLineOption childOption("opm-editor-child", "Internal graphical child");
    childOption.setFlags(QCommandLineOption::HiddenFromHelp);
    parser.addOption(childOption);
    parser.process(app);
    Opm::EditorSession session(Opm::Storage(parser.value("config")));
    Opm::EditorCatalog catalog;
    catalog.refresh();
    QQmlApplicationEngine engine;
    engine.rootContext()->setContextProperty("editorSession", &session);
    engine.rootContext()->setContextProperty("editorCatalog", &catalog);
    engine.load(QUrl("qrc:/editor/qml/Main.qml"));
    if (engine.rootObjects().isEmpty()) {
        qCritical("Native Configure could not load. Install Qt Quick/Controls/Dialogs and Kirigami "
                  "QML runtime modules.");
        return 2;
    }
    auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().first());
    if (!window) { qCritical("Native Configure did not create a window"); return 2; }
    window->setIcon(editorIcon);
    bool ready = false;
    QObject::connect(window, &QQuickWindow::frameSwapped, &app, [&] {
        if (ready || !window->isVisible() || !window->isExposed()) return;
        ready = true;
        std::puts(Opm::editorReady);
        std::fflush(stdout);
        if (parser.isSet("smoke-test")) {
            if (parser.isSet("screenshot") && !window->grabWindow().save(parser.value("screenshot"))) {
                app.exit(3);
                return;
            }
            app.quit();
        }
    }, Qt::QueuedConnection);
    if (parser.isSet("smoke-test")) {
        if (window->icon().isNull() ||
            QGuiApplication::desktopFileName() != QStringLiteral("org.openpowermenu.configure")) {
            qCritical("Native Configure window icon or desktop identity is missing");
            return 4;
        }
    }
    return app.exec();
}
