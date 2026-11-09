#include "editor_catalog.hpp"
#include "editor_session.hpp"
#include <QCommandLineParser>
#include <QGuiApplication>
#include <QIcon>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickStyle>
#include <QQuickWindow>
#include <QTimer>

int main(int argc, char **argv) {
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
    if (window)
        window->setIcon(editorIcon);
    if (parser.isSet("smoke-test")) {
        if (!window || window->icon().isNull() ||
            QGuiApplication::desktopFileName() != QStringLiteral("org.openpowermenu.configure")) {
            qCritical("Native Configure window icon or desktop identity is missing");
            return 4;
        }
        QTimer::singleShot(250, &app, [&] {
            if (parser.isSet("screenshot")) {
                auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().first());
                if (!window || !window->grabWindow().save(parser.value("screenshot"))) {
                    app.exit(3);
                    return;
                }
            }
            app.quit();
        });
    }
    return app.exec();
}
