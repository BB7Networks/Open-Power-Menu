#include "editor_catalog.hpp"
#include "model.hpp"
#include <KConfig>
#include <KConfigGroup>
#include <KService>
#include <QClipboard>
#include <QDir>
#include <QFile>
#include <QGuiApplication>
#include <QJsonDocument>
#include <QRegularExpression>
#include <QStandardPaths>
#include <algorithm>

namespace Opm {
QVariantList EditorCatalog::actions() const {
    QVariantList result;
    const auto catalog = Opm::actions();
    for (auto it = catalog.begin(); it != catalog.end(); ++it) {
        const auto value = it.value().toObject();
        result.append(QVariantMap{{"id", it.key()},
                                  {"title", value["title"].toString()},
                                  {"icon", value["icon"].toString()}});
    }
    std::sort(result.begin(), result.end(), [](const QVariant &a, const QVariant &b) {
        return QString::localeAwareCompare(a.toMap()["title"].toString(),
                                           b.toMap()["title"].toString()) < 0;
    });
    return result;
}
void EditorCatalog::refresh() {
    applicationRows.clear();
    for (const auto &app : KService::allServices()) {
        if (!app->isApplication() || app->noDisplay() || !app->showInCurrentDesktop() ||
            app->name().isEmpty())
            continue;
        applicationRows.append(QVariantMap{{"id", app->storageId()},
                                           {"name", app->name()},
                                           {"icon", app->icon()},
                                           {"description", app->comment()},
                                           {"genericName", app->genericName()}});
    }
    std::sort(applicationRows.begin(), applicationRows.end(),
              [](const QVariant &a, const QVariant &b) {
                  return QString::localeAwareCompare(a.toMap()["name"].toString(),
                                                     b.toMap()["name"].toString()) < 0;
              });
    launcherRows = {
        QVariantMap{{"id", 0}, {"title", "Automatically find a launcher on this panel"}}};
    const auto path = QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) +
                      "/plasma-org.kde.plasma.desktop-appletsrc";
    // KConfig is used strictly for discovery; no writeEntry/sync operation.
    KConfig config(path, KConfig::SimpleConfig);
    const KConfigGroup containments(&config, "Containments");
    QSet<int> seen;
    for (const auto &panelId : containments.groupList()) {
        const auto panel = containments.group(panelId);
        const auto plugin = panel.readEntry("plugin", QString());
        if (plugin != "org.kde.panel" && plugin != "org.kde.plasma.panel")
            continue;
        const auto applets = panel.group("Applets");
        for (const auto &appletId : applets.groupList()) {
            bool valid = false;
            const int id = appletId.toInt(&valid);
            const auto applet = applets.group(appletId);
            const auto appletPlugin = applet.readEntry("plugin", QString());
            if (!valid || id <= 0 || seen.contains(id) || appletPlugin.isEmpty() ||
                appletPlugin == "org.openpowermenu.start")
                continue;
            seen.insert(id);
            QString title = appletPlugin;
            for (const auto &root :
                 QStandardPaths::standardLocations(QStandardPaths::GenericDataLocation)) {
                QFile metadata(root + "/plasma/plasmoids/" + appletPlugin + "/metadata.json");
                if (!metadata.open(QIODevice::ReadOnly) || metadata.size() > MaxConfigBytes)
                    continue;
                const auto name = QJsonDocument::fromJson(metadata.readAll())
                                      .object()["KPlugin"]
                                      .toObject()["Name"]
                                      .toString();
                if (!name.isEmpty()) {
                    title = name;
                    break;
                }
            }
            launcherRows.append(QVariantMap{
                {"id", id},
                {"title", QString("Panel %1: %2 (widget %3)").arg(panelId, title, appletId)},
                {"plugin", appletPlugin}});
        }
    }
    emit refreshed();
}
QString EditorCatalog::applicationItem(const QString &storageId) const {
    const auto app = KService::serviceByStorageId(storageId);
    if (!app || !app->isApplication() || app->noDisplay() || !app->showInCurrentDesktop())
        return {};
    // KDE owns Desktop Entry semantics: Terminal, DBusActivatable, Path and field
    // codes. Do not reinterpret Exec or synthesize a shell command in the picker.
    const QString launcher = !QStandardPaths::findExecutable("kioclient6").isEmpty()  ? "kioclient6"
                             : !QStandardPaths::findExecutable("kioclient").isEmpty() ? "kioclient"
                                                                                      : "";
    if (launcher.isEmpty())
        return {};
    return QString::fromUtf8(
        QJsonDocument(
            QJsonObject{
                {"label", app->name()},
                {"icon", app->icon().isEmpty() ? QString("application-x-executable") : app->icon()},
                {"desktop_file", app->entryPath()},
                {"command", QJsonArray{launcher, "exec", app->entryPath()}}})
            .toJson(QJsonDocument::Compact));
}
QVariantMap EditorCatalog::builtinDetails(const QString &actionId) const {
    const auto spec = Opm::actions().value(actionId).toObject();
    if (spec.isEmpty())
        return {};
    const auto display = [](const QStringList &argv) {
        QStringList words;
        for (const auto &word : argv) {
            if (word.contains(QRegularExpression("[\\s\\\"\\\\']")) || word.isEmpty()) {
                const auto quoted = QJsonDocument(QJsonArray{word}).toJson(QJsonDocument::Compact);
                words.append(QString::fromUtf8(quoted.mid(1, quoted.size() - 2)));
            } else
                words.append(word);
        }
        return words.join(' ');
    };
    Model model;
    const auto selected = model.normalize(QJsonArray{spec}, true).first().argv;
    QStringList candidates;
    QJsonArray first;
    int number = 0;
    for (const auto &candidate : spec["commands"].toArray()) {
        const auto argv =
            candidate.isObject() ? candidate.toObject()["argv"].toArray() : candidate.toArray();
        if (first.isEmpty())
            first = argv;
        auto single = spec;
        single["commands"] = QJsonArray{candidate};
        const bool available = !model.normalize(QJsonArray{single}, true).first().argv.isEmpty();
        QStringList words;
        for (const auto &word : argv)
            words.append(word.toString());
        candidates.append(QString::number(++number) + ". " + display(words) +
                          (available ? "  [installed]" : "  [not available]"));
    }
    return {{"effective",
             selected.isEmpty() ? QString("Not available on this computer") : display(selected)},
            {"candidates", candidates.join('\n')},
            {"command", selected.isEmpty() ? first.toVariantList()
                                           : QJsonArray::fromStringList(selected).toVariantList()},
            {"title", spec["title"].toString()},
            {"icon", spec["icon"].toString()}};
}
QString EditorCatalog::snapshotStatus() const {
    const auto path = QStandardPaths::writableLocation(QStandardPaths::GenericDataLocation) +
                      "/open-power-menu-recovery/widget-backups";
    QDir directory(path);
    int count = 0;
    const QRegularExpression name("^org\\.openpowermenu\\.start-[0-9]{8}-[0-9]{6}-[0-9]{9}$");
    // Snapshot naming is shared with the stable installer; no snapshots are
    // modified or pruned by the configuration editor.
    for (const auto &entry :
         directory.entryInfoList(QDir::Dirs | QDir::NoDotAndDotDot | QDir::NoSymLinks))
        if (name.match(entry.fileName()).hasMatch())
            ++count;
    return path + QString("\n%1 generated widget snapshots. The installer manages their separate "
                          "retention limit.")
                      .arg(count);
}
void EditorCatalog::copy(const QString &text) const {
    QGuiApplication::clipboard()->setText(text);
}
} // namespace Opm
