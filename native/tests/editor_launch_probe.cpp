// Test-only session owner and graphical-child substitute. Never installed.
#include "editor_launch.hpp"
#include <QCoreApplication>
#include <QDBusConnection>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSaveFile>
#include <QTimer>
#include <cstdio>
#include <cstring>
#include <unistd.h>
#include <csignal>

int main(int argc, char **argv) {
    bool owner = false, child = false;
    for (int i = 1; i < argc; ++i) {
        owner |= std::strcmp(argv[i], "--session-owner") == 0;
        child |= std::strcmp(argv[i], "--opm-editor-child") == 0;
    }
    if (!owner && !child) return Opm::coordinateEditor(argc, argv);
    QCoreApplication app(argc, argv);
    if (owner) {
        if (!QDBusConnection::sessionBus().registerService("org.kde.plasmashell")) return 3;
        std::puts("SESSION_READY"); std::fflush(stdout);
        return app.exec();
    }
    const auto args = app.arguments();
    const auto config = args.value(args.indexOf("--config") + 1);
    QJsonObject result{{"pid", qint64(::getpid())}, {"parent", qint64(::getppid())}, {"config", config}};
    for (const auto &key : {"DISPLAY", "XAUTHORITY", "WAYLAND_DISPLAY", "XDG_SESSION_TYPE", "XDG_SESSION_ID",
                            "XDG_RUNTIME_DIR", "QT_QPA_PLATFORM", "XDG_ACTIVATION_TOKEN", "DESKTOP_STARTUP_ID",
                            "OPM_TEST_PRIVATE_VALUE", "OPM_TEST_SHELL_SECRET"})
        if (qEnvironmentVariableIsSet(key)) result[key] = qEnvironmentVariable(key);
    // The parent waits for this path to exist. Publish the completed evidence
    // atomically, otherwise it can parse the empty file between open/write.
    QSaveFile output(config + ".environment.json");
    if (!output.open(QIODevice::WriteOnly)) return 4;
    const auto data = QJsonDocument(result).toJson();
    if (output.write(data) != data.size() || !output.commit()) return 4;
    const auto mode = qEnvironmentVariable("OPM_EDITOR_TEST_MODE");
    if (mode == "exit") { std::fputs("Simulated Qt display initialization failure\n", stderr); return 7; }
    if (mode == "clean-exit") return 0;
    if (mode == "crash") { ::raise(SIGABRT); return 8; }
    if (mode != "timeout" && mode != "hold") { std::puts(Opm::editorReady); std::fflush(stdout); }
    QTimer release;
    QObject::connect(&release, &QTimer::timeout, &app, [&] {
        if (QFile::exists(config + ".release")) app.quit();
        if (mode == "hold" && QFile::exists(config + ".ready")) {
            std::puts(Opm::editorReady); std::fflush(stdout);
            release.stop();
            app.quit();
        }
    });
    release.start(20);
    return app.exec();
}
