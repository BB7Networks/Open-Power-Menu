#include "platform_plugins.hpp"
#include "model.hpp"
#include <QDir>
#include <QPluginLoader>
namespace Opm::Install {
void validatePlatformPlugins(const QString &directory) {
    const auto libraries = QDir(directory).entryInfoList({"*.so"}, QDir::Files, QDir::Name);
    for (const auto &required : {QString("xcb"), QString("wayland")}) {
        bool loaded = false;
        QStringList failures;
        for (const auto &library : libraries) {
            QPluginLoader plugin(library.absoluteFilePath());
            const auto metadata = plugin.metaData();
            if (!metadata.value("IID").toString().startsWith(
                    "org.qt-project.Qt.QPA.QPlatformIntegrationFactoryInterface."))
                continue;
            const auto keys = metadata.value("MetaData").toObject().value("Keys").toArray();
            if (!keys.contains(required))
                continue;
            if (plugin.load()) {
                plugin.unload();
                loaded = true;
                break;
            }
            failures.append(library.fileName() + ": " + plugin.errorString());
        }
        if (!loaded)
            throw Error("Required Qt platform backend unavailable: " + required +
                        (failures.isEmpty() ? "; install the matching distribution Qt platform plugins"
                                            : ": " + failures.join("; ")));
    }
}
}
