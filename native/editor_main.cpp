#include "editor_catalog.hpp"
#include "editor_session.hpp"
#include <QCommandLineParser>
#include <QGuiApplication>
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
    if (parser.isSet("smoke-test"))
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
    return app.exec();
}
