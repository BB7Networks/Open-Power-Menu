#include "storage.hpp"
#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QTextStream>
#include <unistd.h>
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    QStringList args = app.arguments().mid(1);
    QString target = "open-power-menu-standalone";
    if (args.removeOne("--service")) {
        target = "open-power-menu-native";
        args << "--service" << "--bus-name" << "org.openpowermenu.Service";
    } else if (args.removeOne("--edit"))
        target = "open-power-menu-editor";
    else if (args.contains("--widget-menu-json"))
        target = "open-power-menu-native";
    else if (args.contains("--uninstall") || args.contains("--rollback") ||
             args.contains("--recover") || args.contains("--review-dependencies") ||
             args.contains("--dismiss-dependency-review"))
        target = "open-power-menu-install";
    else if (args == QStringList{"--show-launcher-button"}) {
        try {
            Opm::Storage storage;
            auto revision = storage.revision();
            auto cfg = Opm::decode(revision.content);
            cfg["hide_original_launcher"] = false;
            storage.save(cfg, revision);
            return 0;
        } catch (const Opm::Error &e) {
            QTextStream(stderr) << e.what() << '\n';
            return 2;
        }
    }
    auto path = qEnvironmentVariable("XDG_DATA_HOME", QDir::homePath() + "/.local/share") +
                "/open-power-menu/bin/" + target;
    QList<QByteArray> encoded{QFile::encodeName(path)};
    for (const auto &a : args)
        encoded << a.toLocal8Bit();
    QList<char *> pointers;
    for (auto &a : encoded)
        pointers << a.data();
    pointers << nullptr;
    execv(encoded[0], pointers.data());
    QTextStream(stderr) << "Could not start " << path
                        << "; reinstall the complete native package.\n";
    return 2;
}
