#include "applications.hpp"
#include <QDir>
#include <QFileInfo>
#include <QJsonArray>
#include <QProcess>
#include <QStandardPaths>
#include <QSysInfo>
#ifdef OPM_HAVE_KSERVICE
#include <KApplicationTrader>
#include <KConfig>
#include <KConfigGroup>
#include <KDesktopFile>
#include <KService>
#include <KServiceAction>
#endif

namespace Opm {
#ifdef OPM_HAVE_KSERVICE
namespace {
QString launcher() {
    for (const auto &name : {"kioclient6", "kioclient"}) {
        auto path = QStandardPaths::findExecutable(name);
        if (!path.isEmpty()) return path;
    }
    return {};
}
QStringList desktopCommand(const KService::Ptr &service) {
    if (!service || !service->isValid() || service->isDeleted() || !service->isApplication() ||
        service->noDisplay() || !service->showInCurrentDesktop() || !QFileInfo::exists(service->entryPath())) return {};
    // Re-read the actual file, rather than treating a stale sycoca entry as
    // permission to launch a removed/hidden executable.
    KDesktopFile file(service->entryPath());
    const auto group = file.desktopGroup();
    if (group.readEntry("Hidden", false) || !file.tryExec()) return {};
    const auto executable = QProcess::splitCommand(service->exec());
    if (executable.isEmpty() || QStandardPaths::findExecutable(executable.first()).isEmpty()) return {};
    const auto program = launcher();
    if (program.isEmpty()) return {};
    return {program, "exec", service->entryPath()};
}
DesktopApplication byId(const QString &id) {
    // Locate first to retain a Hidden=true override that KService deliberately
    // omits from its application list. Do not bypass it via an executable.
    QString path = id.startsWith('/') ? id : QStandardPaths::locate(QStandardPaths::ApplicationsLocation, id);
    auto service = path.isEmpty() ? KService::serviceByStorageId(id) : KService::Ptr(new KService(path));
    return {!path.isEmpty() || bool(service), desktopCommand(service)};
}
}
#endif
DesktopApplication desktopApplication(const QJsonObject &candidate) {
    DesktopApplication result;
#ifdef OPM_HAVE_KSERVICE
    for (const auto &id : candidate["desktop_ids"].toArray()) {
        const auto found = byId(id.toString());
        result.registered |= found.registered;
        if (!found.command.isEmpty()) return found;
    }
#else
    Q_UNUSED(candidate)
#endif
    return result;
}
bool terminalSelectionAvailable(const QString &id) {
#ifdef OPM_HAVE_KSERVICE
    const auto parts = id.split(':');
    if (parts.isEmpty() || parts.size() > 2 || parts[0].isEmpty()) return false;
    const auto selected = byId(parts[0]);
    if (selected.command.isEmpty()) return false;
    if (parts.size() == 1) return true;
    KService service(selected.command.last());
    for (const auto &action : service.actions())
        if (action.name() == parts[1] && !action.exec().isEmpty()) return true;
#else
    Q_UNUSED(id)
#endif
    return false;
}
QStringList preferredApplication(const QString &action) {
#ifdef OPM_HAVE_KSERVICE
    if (action == "files")
        return desktopCommand(KApplicationTrader::preferredService(QStringLiteral("inode/directory")));
    if (action == "applications") {
        const auto app = KApplicationTrader::preferredService(QStringLiteral("x-scheme-handler/appstream"));
        // A browser registered for arbitrary URLs is not a software manager.
        if (app && QStringList{"org.kde.discover.desktop", "org.manjaro.pamac.manager.desktop", "pamac-manager.desktop",
                               "org.gnome.Software.desktop", "gnome-software.desktop", "octopi.desktop",
                               "snap-store_snap-store.desktop", "snap-store_ubuntu-software.desktop", "snap-store_app-center.desktop",
                               "org.ubuntu.AppCenter.desktop", "io.snapcraft.Store.desktop"}.contains(app->storageId()))
            return desktopCommand(app);
    }
    if (action == "remote") {
        const auto app = KApplicationTrader::preferredService(QStringLiteral("application/x-rdp"));
        if (app && QStringList{"org.kde.krdc.desktop", "org.remmina.Remmina.desktop", "remmina.desktop"}.contains(app->storageId()))
            return desktopCommand(app);
    }
    if (action == "terminal") {
        KConfig config(QStringLiteral("kdeglobals"));
        const KConfigGroup general(&config, "General");
        const auto service = general.readEntry("TerminalService", QString());
        if (!service.isEmpty()) {
            const auto chosen = byId(service);
            if (!chosen.command.isEmpty()) return chosen.command;
        }
        const auto command = QProcess::splitCommand(general.readEntry("TerminalApplication", QString()));
        if (!command.isEmpty() && !QStandardPaths::findExecutable(command.first()).isEmpty()) return command;
    }
#else
    Q_UNUSED(action)
#endif
    return {};
}
int applicationPreference(const QJsonObject &candidate) {
    int score = 0;
    const auto desktop = qEnvironmentVariable("XDG_CURRENT_DESKTOP").toUpper().replace(';', ':').split(':');
    for (const auto &name : candidate["preferred_desktops"].toArray())
        if (desktop.contains(name.toString().toUpper())) score = 1;
    for (const auto &name : candidate["preferred_distros"].toArray())
        if (name.toString() == QSysInfo::productType()) score = 2;
    return score;
}
}
