#include "editor_launch.hpp"
#include <QCommandLineParser>
#include <QCoreApplication>
#include <QDateTime>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusMessage>
#include <QDBusReply>
#include <QDebug>
#include <QFile>
#include <QProcess>
#include <QTimer>
#include <QTextStream>
#include <unistd.h>

namespace Opm {
namespace {
// Keep application configuration and unrelated environment in the caller's
// environment. Only replace graphical-session state, including absent keys.
const QStringList sessionKeys = {
    "DISPLAY", "XAUTHORITY", "WAYLAND_DISPLAY", "XDG_SESSION_TYPE", "XDG_SESSION_ID",
    "XDG_SESSION_CLASS", "XDG_SESSION_DESKTOP", "XDG_CURRENT_DESKTOP", "DESKTOP_SESSION",
    "XDG_SEAT", "XDG_VTNR", "XDG_RUNTIME_DIR", "QT_QPA_PLATFORM", "QT_QPA_PLATFORMTHEME",
    "QT_IM_MODULE", "XMODIFIERS", "XDG_ACTIVATION_TOKEN", "DESKTOP_STARTUP_ID"
};
bool peerEnvironment(const QString &peer, QProcessEnvironment &environment, QString &error) {
    auto *bus = QDBusConnection::sessionBus().interface();
    if (!bus || !peer.startsWith(':')) {
        error = "The graphical session is not available on the user D-Bus.";
        return false;
    }
    const auto uid = bus->serviceUid(peer);
    const auto pid = bus->servicePid(peer);
    if (!uid.isValid() || uid.value() != ::geteuid() || !pid.isValid() || !pid.value()) {
        error = "Could not identify the current graphical-session process.";
        return false;
    }
    QFile file("/proc/" + QString::number(pid.value()) + "/environ");
    if (!file.open(QIODevice::ReadOnly)) {
        error = "Could not read the current graphical-session environment (procfs access denied).";
        return false;
    }
    constexpr int limit = 4 * 1024 * 1024;
    const auto data = file.read(limit + 1);
    if (data.size() > limit || file.error() != QFileDevice::NoError) {
        error = "Could not read the current graphical-session environment safely.";
        return false;
    }
    for (const auto &entry : data.split('\0')) {
        const auto equals = entry.indexOf('=');
        if (equals <= 0) continue;
        const auto key = QString::fromLocal8Bit(entry.first(equals));
        if (sessionKeys.contains(key))
            environment.insert(key, QString::fromLocal8Bit(entry.mid(equals + 1)));
    }
    const auto stillPid = bus->servicePid(peer);
    if (!stillPid.isValid() || stillPid.value() != pid.value()) {
        error = "The graphical session ended during Configure startup. Try Configure in the current session.";
        return false;
    }
    return true;
}
}

EditorEnvironment editorEnvironment(const QProcessEnvironment &base, const QString &requester, bool smokeTest) {
    EditorEnvironment result{base, {}, {}};
    // Explicit developer smoke tests are the only headless bypass. A stale
    // QT_QPA_PLATFORM in an activated service must not hide a real editor.
    if (smokeTest && (base.value("QT_QPA_PLATFORM") == "offscreen" || base.value("QT_QPA_PLATFORM") == "minimal")) {
        result.source = "explicit headless smoke test";
        return result;
    }
    auto *bus = QDBusConnection::sessionBus().interface();
    QDBusReply<QString> owner = bus ? bus->serviceOwner("org.kde.plasmashell") : QDBusReply<QString>();
    QProcessEnvironment session;
    if (owner.isValid() && !owner.value().isEmpty()) {
        result.source = "plasmashell " + owner.value();
        if (!peerEnvironment(owner.value(), session, result.error)) return result;
        const auto current = bus->serviceOwner("org.kde.plasmashell");
        if (!current.isValid() || current.value() != owner.value()) {
            result.error = "Plasma changed sessions during Configure startup. Try Configure again.";
            return result;
        }
    } else if (!requester.isEmpty()) {
        result.source = "requesting client " + requester;
        if (!peerEnvironment(requester, session, result.error)) return result;
    } else {
        result.source = "direct invocation";
        session = base;
    }
    for (const auto &key : sessionKeys) {
        result.environment.remove(key);
        if (session.contains(key)) result.environment.insert(key, session.value(key));
    }
    // Preserve a fresh direct launcher's activation tokens only when its
    // session matches the resolved session. Never borrow Plasma's initial
    // tokens or an activated backend's cached tokens.
    result.environment.remove("XDG_ACTIVATION_TOKEN");
    result.environment.remove("DESKTOP_STARTUP_ID");
    bool currentDirectInvocation = requester.isEmpty();
    for (const auto &key : {"DISPLAY", "XAUTHORITY", "WAYLAND_DISPLAY", "XDG_SESSION_TYPE", "XDG_SESSION_ID", "XDG_RUNTIME_DIR"})
        currentDirectInvocation &= base.value(key) == session.value(key);
    if (currentDirectInvocation)
        for (const auto &key : {"XDG_ACTIVATION_TOKEN", "DESKTOP_STARTUP_ID"})
            if (base.contains(key)) result.environment.insert(key, base.value(key));
    auto type = session.value("XDG_SESSION_TYPE");
    if (type.isEmpty())
        type = !session.value("WAYLAND_DISPLAY").isEmpty() ? "wayland" : "x11";
    if (type == "wayland" && !session.value("WAYLAND_DISPLAY").isEmpty() && !session.value("XDG_RUNTIME_DIR").isEmpty()) {
        result.environment.insert("QT_QPA_PLATFORM", "wayland");
    } else if (type == "x11" && !session.value("DISPLAY").isEmpty()) {
        result.environment.remove("WAYLAND_DISPLAY");
        result.environment.insert("QT_QPA_PLATFORM", "xcb");
    } else {
        result.error = "No usable graphical session was found. Open Configure from the active Plasma session.";
    }
    result.environment.insert("XDG_SESSION_TYPE", type);
    if (base.value("OPM_SESSION_TRACE") == "1") {
        // Deliberately omit cookie contents, environment dumps and startup tokens.
        // An explicitly requested CLI trace must survive distro Qt logging
        // filters/journal routing. Keep this scoped to our opt-in messages.
        QTextStream(stderr) << QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs)
                            << " OPM Configure session: " << result.source << " type=" << type
                            << " DISPLAY=" << result.environment.value("DISPLAY")
                            << " WAYLAND_DISPLAY=" << result.environment.value("WAYLAND_DISPLAY")
                            << " XAUTHORITY=" << result.environment.value("XAUTHORITY") << '\n';
    }
    return result;
}

void reportEditorStartup(const QString &destination, const QString &token, const QString &error) {
    if (destination.isEmpty() || token.isEmpty()) return;
    auto message = QDBusMessage::createMethodCall(destination, "/OpenPowerMenu", "org.openpowermenu.Service", "EditorStarted");
    message.setArguments({token, error});
    const auto reply = QDBusConnection::sessionBus().call(message, QDBus::Block, 3000);
    if (reply.type() == QDBusMessage::ErrorMessage)
        qWarning().noquote() << "Configure startup acknowledgement failed:" << reply.errorMessage();
}

int coordinateEditor(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    app.setApplicationName("Open Power Menu Configure");
    app.setApplicationVersion(OPM_NATIVE_VERSION);
    QCommandLineParser parser;
    parser.addHelpOption();
    parser.addVersionOption();
    parser.addOption({"config", "Configuration file", "file"});
    parser.addOption({"smoke-test", "Load the native editor and exit after one event-loop cycle"});
    parser.addOption({"screenshot", "Capture the editor during a developer smoke test", "file"});
    for (const auto &key : {"opm-reply-to", "opm-request", "opm-session-peer"}) {
        QCommandLineOption option(QString::fromLatin1(key), "Internal startup acknowledgement", "value");
        option.setFlags(QCommandLineOption::HiddenFromHelp);
        parser.addOption(option);
    }
    parser.process(app);
    bool reported = false;
    auto report = [&](const QString &error) {
        if (reported) return;
        reported = true;
        if (!error.isEmpty()) QTextStream(stderr) << "Configure could not open: " << error << '\n';
        if (qEnvironmentVariable("OPM_SESSION_TRACE") == "1")
            QTextStream(stderr) << QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs)
                                << " OPM Configure startup: " << (error.isEmpty() ? "first frame ready" : "failed") << '\n';
        reportEditorStartup(parser.value("opm-reply-to"), parser.value("opm-request"), error);
    };
    const auto session = editorEnvironment(QProcessEnvironment::systemEnvironment(), parser.value("opm-session-peer"), parser.isSet("smoke-test"));
    if (!session.error.isEmpty()) { report(session.error); return 2; }
    QProcess child;
    child.setProcessEnvironment(session.environment);
    child.setProgram(QCoreApplication::applicationFilePath());
    QStringList arguments{"--opm-editor-child"};
    for (const auto &key : {"config", "screenshot"})
        if (parser.isSet(key)) arguments << "--" + QString::fromLatin1(key) << parser.value(key);
    if (parser.isSet("smoke-test")) arguments << "--smoke-test";
    child.setArguments(arguments);
    child.setStandardInputFile(QProcess::nullDevice());
    child.setProcessChannelMode(QProcess::ForwardedErrorChannel);
    QTimer deadline;
    deadline.setSingleShot(true);
    QByteArray output;
    QObject::connect(&child, &QProcess::readyReadStandardOutput, &app, [&] {
        output += child.readAllStandardOutput();
        int newline;
        while ((newline = output.indexOf('\n')) >= 0) {
            const auto line = output.first(newline);
            output.remove(0, newline + 1);
            if (line == editorReady && child.state() == QProcess::Running) {
                deadline.stop();
                report({});
            }
        }
        if (output.size() > 4096) output.clear();
    });
    QObject::connect(&child, &QProcess::errorOccurred, &app, [&](QProcess::ProcessError error) {
        if (error == QProcess::FailedToStart) {
            report("Could not execute the native editor: " + child.errorString());
            app.exit(2);
        }
    });
    QObject::connect(&child, &QProcess::finished, &app, [&](int code, QProcess::ExitStatus status) {
        const bool ready = reported;
        report(QString("The editor exited before displaying its first frame (exit %1%2). Check the user journal or run open-power-menu --edit for Qt display/plugin diagnostics.")
                   .arg(code).arg(status == QProcess::CrashExit ? ", crashed" : ""));
        app.exit(!ready || status == QProcess::CrashExit ? 2 : code);
    });
    QObject::connect(&deadline, &QTimer::timeout, &app, [&] {
        report("The editor did not display its first frame within 15 seconds. Check the current display connection and Qt runtime modules.");
        // This is our own unready child, never an existing backend or editor.
        child.kill();
    });
    child.start();
    deadline.start(15000); // Failure deadline, not a startup delay or retry.
    return app.exec();
}
} // namespace Opm
