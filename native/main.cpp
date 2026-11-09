#include "service.hpp"
#include <QCommandLineParser>
#include <QCoreApplication>
#include <QDBusConnection>
#include <QDBusError>
#include <QDBusInterface>
#include <QDBusMessage>
#include <QJsonDocument>
#include <QTextStream>

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    app.setApplicationName("open-power-menu-native");
    app.setApplicationVersion(OPM_NATIVE_VERSION);
    QCommandLineParser parser;
    parser.setApplicationDescription(
        "Native backend development preview. The normal 1.0.1 installer and UI remain unchanged.");
    parser.addHelpOption();
    parser.addVersionOption();
    parser.addOptions(
        {{"config", "Read this local configuration (never a D-Bus argument)", "file"},
         {"service", "Run the native preview D-Bus service"},
         {"bus-name", "NativePreview (default) or explicit production Service bus name", "name",
          "org.openpowermenu.NativePreview"},
         {"check", "Validate configuration and print availability"},
         {"widget-menu-json", "Print compatible public menu JSON"},
         {"dump-config", "Print normalized local configuration for development comparison"},
         {"default-config", "Print shared defaults without reading user configuration"},
         {"call", "Call a preview D-Bus method for development diagnostics", "method"}});
    parser.addPositionalArgument("arguments", "String arguments for --call", "[arguments...]");
    parser.process(app);
    const auto busName = parser.value("bus-name");
    if (busName != "org.openpowermenu.NativePreview" && busName != "org.openpowermenu.Service") {
        QTextStream(stderr) << "Use org.openpowermenu.NativePreview or org.openpowermenu.Service\n";
        return 2;
    }
    try {
        if (parser.isSet("call")) {
            QDBusInterface remote(busName, "/OpenPowerMenu", "org.openpowermenu.Service",
                                  QDBusConnection::sessionBus());
            remote.setTimeout(parser.value("call") == "Run" ? 130000 : 10000);
            QList<QVariant> args;
            for (const auto &arg : parser.positionalArguments())
                args.append(arg);
            const auto response =
                remote.callWithArgumentList(QDBus::Block, parser.value("call"), args);
            if (response.type() == QDBusMessage::ErrorMessage) {
                QTextStream(stderr) << response.errorMessage() << '\n';
                return 1;
            }
            if (response.arguments().size() != 1)
                throw Opm::Error("Unexpected D-Bus reply");
            const auto value = response.arguments().first();
            QTextStream(stdout) << (value.typeId() == QMetaType::Bool
                                        ? (value.toBool() ? "true" : "false")
                                        : value.toString())
                                << '\n';
            return 0;
        }
        Opm::Storage storage(parser.value("config"));
        if (parser.isSet("service")) {
            const auto bus = QDBusConnection::sessionBus();
            if (!bus.isConnected())
                throw Opm::Error("No D-Bus user session bus");
            Opm::Service service(storage);
            auto connection = bus;
            if (!connection.registerService(busName))
                throw Opm::Error(
                    "Could not register service (an existing owner is left running): " +
                    connection.lastError().message());
            if (!connection.registerObject("/OpenPowerMenu", &service,
                                           QDBusConnection::ExportAllSlots))
                throw Opm::Error("Could not register native service object");
            return app.exec();
        }
        if (parser.isSet("default-config")) {
            QTextStream(stdout) << QJsonDocument(Opm::defaults()).toJson(QJsonDocument::Indented);
            return 0;
        }
        if (!parser.isSet("check") && !parser.isSet("widget-menu-json") &&
            !parser.isSet("dump-config"))
            parser.showHelp();
        const auto config = storage.load();
        Opm::Model model;
        if (parser.isSet("dump-config"))
            QTextStream(stdout) << QJsonDocument(config).toJson(QJsonDocument::Indented);
        else {
            if (parser.isSet("check"))
                QTextStream(stdout)
                    << "Open Power Menu native " OPM_NATIVE_VERSION "\nConfiguration: "
                    << storage.path() << '\n';
            QTextStream(stdout)
                << QJsonDocument(model.diagnosticMenu(config)).toJson(QJsonDocument::Indented);
        }
        return 0;
    } catch (const Opm::Error &error) {
        QTextStream(stderr) << "Open Power Menu: " << error.what() << '\n';
        return 2;
    }
}
