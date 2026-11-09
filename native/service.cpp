#include "service.hpp"
#include "launch.hpp"
#include <QCoreApplication>
#include <QDebug>
#include <QFileInfo>
#include <QJsonDocument>
#include <QProcess>
#include <QUuid>
#include <QPointer>
#include <QDBusConnection>

namespace Opm {
static QString json(const QJsonObject &value) {
    return QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
}
static QString reply(const std::function<QJsonObject()> &operation) {
    try {
        return json(operation());
    } catch (const Error &error) {
        const auto message =
            error.code == "configuration"
                ? QString("Could not read or save configuration safely; your draft is retained")
                : QString::fromUtf8(error.what());
        return json({{"ok", false}, {"code", error.code}, {"message", message}});
    }
}
Service::Service(Storage source, QObject *parent, std::shared_ptr<PowerManager> power, std::function<qint64()> clock)
    : QObject(parent), storage(std::move(source)), model(std::move(power)), layouts(storage),
      now(std::move(clock)), clients(this) {
    elapsed.start();
    if (!now) now = [this] { return elapsed.elapsed(); };
    clients.setConnection(QDBusConnection::sessionBus());
    clients.setWatchMode(QDBusServiceWatcher::WatchForUnregistration);
    connect(&clients, &QDBusServiceWatcher::serviceUnregistered, this, [this](const QString &owner) {
        for (const auto &op : operations) if (op->owner == owner) op->alive = false;
        errors.remove(owner);
        clients.removeWatchedService(owner);
    });
    idle.setSingleShot(true);
    idle.setInterval(5 * 60 * 1000);
    connect(&idle, &QTimer::timeout, this, [this] {
        if (model.powerCapabilities()->executionPending()) touch();
        else QCoreApplication::quit();
    });
    touch();
}
void Service::touch() {
    idle.start();
}
QString Service::Ping() {
    touch();
    return "Open Power Menu v" OPM_NATIVE_VERSION;
}
QString Service::GetMenu() {
    touch();
    lastMenuPowerPending = false;
    try {
        prune();
        while (menus.size() >= 16) {
            auto oldest = menus.begin();
            for (auto it = menus.begin(); it != menus.end(); ++it) if (it->expires < oldest->expires) oldest = it;
            menus.erase(oldest);
        }
        const auto revision = storage.revision();
        auto shown = model.capture(decode(revision.content));
        const auto id = QUuid::createUuid().toString(QUuid::Id128);
        auto menu = shown.menu;
        std::function<void(QJsonArray &)> keys = [&](QJsonArray &items) {
            for (qsizetype i = 0; i < items.size(); ++i) {
                auto row = items[i].toObject();
                row["key"] = id + '/' + row["key"].toString();
                if (row.contains("items")) { auto children = row["items"].toArray(); keys(children); row["items"] = children; }
                items[i] = row;
            }
        };
        keys(menu);
        menus.insert(id, {revision, std::move(shown), now() + 120000});
        lastMenuPowerPending = model.powerCapabilities()->discoveryPending();
        return QString::fromUtf8(QJsonDocument(menu).toJson(QJsonDocument::Compact));
    } catch (const Error &error) {
        qWarning() << "Open Power Menu configuration error:" << error.what();
        return QString::fromUtf8(
            QJsonDocument(QJsonArray{QJsonObject{{"kind", "command"},
                                                 {"key", ""},
                                                 {"title", "Invalid menu.json — see README"},
                                                 {"icon", "dialog-error"},
                                                 {"enabled", false}}})
                .toJson(QJsonDocument::Compact));
    }
}
QString Service::GetIntegration() {
    touch();
    try {
        return json(integration(storage.load()));
    } catch (const Error &error) {
        qWarning() << "Integration configuration error:" << error.what();
        return json(integration(defaults()));
    }
}
bool Service::PowerCapabilitiesPending() {
    touch();
    // A fast reply can settle discovery between GetMenu and this call. Still
    // refresh a presentation built while pending, so the widget cannot miss it.
    return lastMenuPowerPending || model.powerCapabilities()->discoveryPending();
}
QString Service::caller() const { return calledFromDBus() ? message().service() : QString(); }
void Service::prune() {
    for (auto it = menus.begin(); it != menus.end();) {
        if (it->expires <= now()) it = menus.erase(it); else ++it;
    }
    for (auto it = operations.begin(); it != operations.end();) {
        if (!it.value()->pending && it.value()->expires <= now()) it = operations.erase(it); else ++it;
    }
    for (const auto &owner : clients.watchedServices()) {
        bool retained = false;
        for (const auto &op : operations) if (op->owner == owner) { retained = true; break; }
        if (!retained) clients.removeWatchedService(owner);
    }
}
void Service::start(const QString &key, std::function<void(QString)> done, std::function<bool()> alive) {
    touch(); prune();
    try {
        const auto slash = key.indexOf('/');
        const auto id = key.left(slash);
        if (slash != 32 || key.size() > 161 || !menus.contains(id))
            throw Error("This menu selection expired or is invalid. Reopen the menu to refresh it.", "stale");
        const auto menu = menus.take(id); // one attempt per presentation, including refusals
        if (storage.revision() != menu.revision)
            throw Error("Configuration changed. Reopen the menu to refresh it.", "stale");
        const auto config = decode(menu.revision.content);
        const auto path = key.mid(slash + 1);
        const auto entry = model.selected(config, path, menu.shown);
        if (storage.revision() != menu.revision)
            throw Error("Configuration changed. Reopen the menu to refresh it.", "stale");
        if (entry.powerAction.isEmpty()) {
            done(launchDetached(entry.argv) ? QString() : "Could not start this item. Reopen the menu to refresh it.");
            return;
        }
        const QPointer<Service> guard(this);
        model.powerCapabilities()->executeAsync(entry.powerAction, std::move(done), [guard, menu, config, path, alive] {
            if (!guard || (alive && !alive())) return false;
            try {
                if (guard->storage.revision() != menu.revision) return false;
                guard->model.selected(config, path, menu.shown);
                return true;
            } catch (const Error &) { return false; }
        });
    } catch (const Error &error) { done(QString::fromUtf8(error.what())); }
}
bool Service::Run(const QString &key) {
    // Legacy boolean completion remains final, never "queued == success".
    const auto owner = caller();
    if (errors.size() >= 64) errors.clear();
    errors[owner].clear();
    const bool remote = calledFromDBus();
    const auto request = remote ? message() : QDBusMessage();
    const auto bus = remote ? connection() : QDBusConnection::sessionBus();
    if (remote) setDelayedReply(true);
    auto result = std::make_shared<bool>(false);
    auto op = std::make_shared<Operation>(); op->owner = owner;
    if (!owner.isEmpty()) clients.addWatchedService(owner);
    prune();
    if (operations.size() >= 64) {
        errors[owner] = "Too many recent operations; wait before trying again.";
        if (remote) bus.send(request.createReply(QVariant(false)));
        return false;
    }
    operations.insert(QUuid::createUuid().toString(QUuid::Id128), op);
    const QPointer<Service> guard(this);
    start(key, [guard, owner, remote, request, bus, result, op](QString error) {
        if (!guard) return;
        *result = error.isEmpty();
        op->pending = false; op->error = error; op->expires = guard->now() + 120000;
        if (op->alive) guard->errors[owner] = error;
        if (remote) bus.send(request.createReply(QVariant(error.isEmpty())));
        guard->touch();
    }, [op] { return op->alive; });
    return *result;
}
QString Service::StartRun(const QString &key) {
    touch(); prune();
    if (operations.size() >= 64) return json({{"state", "finished"}, {"ok", false}, {"error", "Too many recent requests; wait before reopening the menu."}});
    const auto id = QUuid::createUuid().toString(QUuid::Id128);
    auto op = std::make_shared<Operation>();
    op->owner = caller();
    if (!op->owner.isEmpty()) clients.addWatchedService(op->owner);
    operations.insert(id, op);
    const QPointer<Service> guard(this);
    start(key, [guard, op](QString error) {
        if (!guard) return;
        op->pending = false; op->error = error; op->expires = guard->now() + 120000;
        guard->touch();
    }, [op] { return op->alive; });
    auto result = QJsonDocument::fromJson(RunResult(id).toUtf8()).object();
    result["operation"] = id;
    return json(result);
}
QString Service::RunResult(const QString &id) {
    touch(); prune();
    const auto op = operations.value(id);
    if (!op || op->owner != caller()) return json({{"state", "finished"}, {"ok", false}, {"error", "Operation expired or belongs to another client. Reopen the menu; do not automatically retry."}});
    if (op->pending) return json({{"state", "pending"}});
    return json({{"state", "finished"}, {"ok", op->error.isEmpty()}, {"error", op->error}});
}
QString Service::LastError() { touch(); return errors.value(caller()); }
bool Service::Edit() {
    touch();
    const auto editor = QCoreApplication::applicationDirPath() + "/open-power-menu-editor";
    if (!QFileInfo(editor).isExecutable()) {
        qWarning("Native Configure is not installed beside the backend. Build with "
                 "OPM_BUILD_EDITOR=ON or install the complete native developer build.");
        return false;
    }
    QProcess process;
    process.setProgram(editor);
    process.setArguments({"--config", storage.path()});
    process.setStandardInputFile(QProcess::nullDevice());
    process.setStandardOutputFile(QProcess::nullDevice());
    // Keep startup diagnostics in the user service log while GUI migration is
    // being validated; no Python frontend is launched as a fallback.
    return process.startDetached();
}
QString Service::BeginLayoutEdit() {
    touch();
    return reply([this] { return layouts.begin(); });
}
QString Service::SaveLayoutEdit(const QString &token, const QString &references) {
    touch();
    return reply([&] { return layouts.save(token, references); });
}
bool Service::CancelLayoutEdit(const QString &token) {
    touch();
    return layouts.cancel(token);
}
QString Service::KeepLayoutEdit(const QString &token) {
    touch();
    return reply([&] { return QJsonObject{{"ok", layouts.keep(token)}}; });
}
} // namespace Opm
