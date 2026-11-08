#include "standalone.hpp"
#include "storage.hpp"
#include <QApplication>
#include <QCommandLineParser>
#include <QJsonDocument>
#include <QMessageBox>
#include <QTextStream>
#include <memory>

int main(int argc, char **argv) {
    // Read-only CLI diagnostics must work without a display or platform plugin.
    // Qt's parser still validates every argument after choosing the app type.
    bool gui = true;
    for (int i = 1; i < argc; ++i)
        if (QStringList{"--list", "--check", "--default-config", "--version", "-v", "--help", "-h"}
                .contains(QString::fromLocal8Bit(argv[i])))
            gui = false;
    std::unique_ptr<QCoreApplication> app;
    if (gui)
        app = std::make_unique<QApplication>(argc, argv);
    else
        app = std::make_unique<QCoreApplication>(argc, argv);
    app->setApplicationName("open-power-menu-standalone");
    app->setApplicationVersion(OPM_NATIVE_VERSION);
    if (gui)
        QApplication::setDesktopFileName("org.openpowermenu");
    QCommandLineParser parser;
    parser.setApplicationDescription("Native standalone development menu; production activation is unchanged.");
    parser.addHelpOption();
    parser.addVersionOption();
    parser.addOptions({{"config", "Read local configuration", "file"},
                       {"anchor", "cursor, bottom-left or bottom-right (Wayland placement is compositor controlled)", "anchor"},
                       {"theme", "native or aero", "theme"},
                       {"diagnose-launch", "Report exposure, visibility, focus and dismissal"},
                       {"list", "Print normalized menu JSON without opening a GUI"},
                       {"check", "Validate configuration and print normalized menu JSON"},
                       {"default-config", "Print shared defaults without reading configuration"}});
    parser.process(*app);
    for (const auto &name : {"anchor", "theme"}) {
        const QStringList choices = QString(name) == "anchor"
            ? QStringList{"cursor", "bottom-left", "bottom-right"} : QStringList{"native", "aero"};
        if (parser.isSet(name) && !choices.contains(parser.value(name))) {
            QTextStream(stderr) << "Open Power Menu: Invalid --" << name << '\n';
            return 2;
        }
    }
    if (!parser.positionalArguments().isEmpty())
        parser.showHelp(2);
    try {
        if (parser.isSet("default-config")) {
            QTextStream(stdout) << QJsonDocument(Opm::defaults()).toJson(QJsonDocument::Indented);
            return 0;
        }
        Opm::Storage storage(parser.value("config"));
        const auto config = storage.load();
        if (parser.isSet("check") || parser.isSet("list")) {
            Opm::Model model;
            QTextStream(stdout) << QJsonDocument(model.diagnosticMenu(config)).toJson(QJsonDocument::Indented);
            return 0;
        }
        Opm::Standalone menu(config, parser.value("theme"), parser.isSet("diagnose-launch"));
        const int result = menu.open(parser.value("anchor"));
        if (result == 1) {
            if (menu.actions().isEmpty())
                QMessageBox::information(nullptr, "Open Power Menu",
                    "No configured commands are available on this system.");
            else
                QMessageBox::critical(nullptr, "Open Power Menu",
                    menu.errorMessage().isEmpty() ? "Could not launch the selection. The application may have become unavailable; reopen the menu to refresh it."
                                                  : menu.errorMessage());
        }
        return result;
    } catch (const Opm::Error &error) {
        QTextStream(stderr) << "Open Power Menu: " << error.what() << '\n';
        return 2;
    }
}
