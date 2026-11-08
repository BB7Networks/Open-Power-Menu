#include "power.hpp"
#include "model.hpp"
#include <QDBusArgument>
#include <QDBusConnection>
#include <QVariant>
#include <QDBusPendingCallWatcher>
#include <QDBusServiceWatcher>
#include <QElapsedTimer>
#include <QPointer>
#include <QTimer>
#include <array>
#include <algorithm>
#include <QCoreApplication>
namespace Opm {
namespace {
class DBusPower final : public PowerManager {
    PowerCall transport;
    QDBusMessage call(bool system, const QString &service, const QString &path,
                      const QString &interface, const QString &method, const QList<QVariant> &args = {}) {
        auto request = QDBusMessage::createMethodCall(service, path, interface, method);
        request.setArguments(args);
        request.setInteractiveAuthorizationAllowed(method.endsWith("WithFlags"));
        const auto reply = transport(system, request);
        if (reply.type() == QDBusMessage::ErrorMessage)
            throw Error("Power management: " + reply.errorName() + ": " + reply.errorMessage(), "power");
        if (reply.type() != QDBusMessage::ReplyMessage)
            throw Error("Power management did not reply", "power");
        return reply;
    }
    QVariant query(bool system, const QString &service, const QString &path,
                   const QString &interface, const QString &method) {
        const auto reply = call(system, service, path, interface, method);
        if (reply.arguments().size() != 1)
            throw Error("Invalid power capability response", "power");
        return reply.arguments().first();
    }
    QString method(const QString &action) {
        if (action == "sleep") return "Suspend";
        if (action == "hibernate") return "Hibernate";
        throw Error("Unknown native power action", "power");
    }
    void check(const QString &action) {
        const auto operation = method(action);
        // PowerDevil owns desktop restrictions. A missing/failed interface is
        // unavailable, never permission to bypass the desktop policy.
        const auto kde = query(false, "org.freedesktop.PowerManagement", "/org/freedesktop/PowerManagement",
                               "org.freedesktop.PowerManagement", "Can" + operation);
        if (kde.metaType().id() != QMetaType::Bool || !kde.toBool())
            throw Error(operation + " is not supported by KDE power management", "power");
        const auto inhibit = query(false, "org.freedesktop.PowerManagement", "/org/freedesktop/PowerManagement/Inhibit",
                                   "org.freedesktop.PowerManagement.Inhibit", "HasInhibit");
        if (inhibit.metaType().id() != QMetaType::Bool || inhibit.toBool())
            throw Error("An application is preventing sleep; review KDE power management", "power");
        const auto permission = query(true, "org.freedesktop.login1", "/org/freedesktop/login1",
                                      "org.freedesktop.login1.Manager", "Can" + operation).toString();
        if (permission != "yes" && permission != "challenge")
            throw Error(operation + " is unavailable or denied by system policy", "power");
    }
  public:
    explicit DBusPower(PowerCall call) : transport(std::move(call)) {}
    PowerAvailability capability(const QString &action) override {
        try { check(action); return {true, {}}; }
        catch (const Error &error) { return {false, QString::fromUtf8(error.what())}; }
    }
    void execute(const QString &action) override {
        check(action); // Recheck permissions and KDE inhibitors at activation.
        // logind enforces block/block-weak inhibitors atomically, including our
        // own user's locks; delay inhibitors still receive PrepareForSleep.
        // Never set SKIP_INHIBITORS, never fall back to an unchecked command.
        // The D-Bus interactive authorization flag lets Polkit ask permission.
        call(true, "org.freedesktop.login1", "/org/freedesktop/login1", "org.freedesktop.login1.Manager",
             method(action) + "WithFlags", {QVariant::fromValue(qulonglong(1))});
    }
};
}
namespace {
PowerCall blockingTransport() {
    return [](bool system, const QDBusMessage &request) {
        return (system ? QDBusConnection::systemBus() : QDBusConnection::sessionBus())
            .call(request, QDBus::Block, request.isInteractiveAuthorizationAllowed() ? 120000 : 1500);
    };
}
// One generation shares HasInhibit between the two operations. All five reads
// run concurrently; one unresponsive service cannot accumulate sequential waits.
class CachedPower final : public PowerManager {
    PowerAsyncCall transport;
    std::function<qint64()> now;
    DBusPower execution;
    std::array<QDBusMessage, 5> replies;
    std::array<bool, 5> received{};
    QHash<QString, PowerAvailability> states;
    quint64 generation = 0;
    qint64 expires = 0;
    bool pending = false;
    QTimer deadline;
    void finish(quint64 epoch) {
        if (!pending || epoch != generation) return;
        deadline.stop();
        pending = false;
        expires = now() + 5000;
        for (int action = 0; action < 2; ++action) {
            const QString name = action ? "hibernate" : "sleep";
            QString error;
            for (const int index : {action, 2, 3 + action}) {
                const auto &reply = replies[index];
                if (!received[index]) error = "Power capability discovery timed out";
                else if (reply.type() == QDBusMessage::ErrorMessage)
                    error = "Power management: " + reply.errorName() + ": " + reply.errorMessage();
                else if (reply.type() != QDBusMessage::ReplyMessage || reply.arguments().size() != 1)
                    error = "Invalid power capability response";
                else {
                    const auto value = reply.arguments().first();
                    if (index < 3) {
                        if (value.metaType().id() != QMetaType::Bool || value.toBool() != (index != 2))
                            error = index == 2 ? "An application is preventing sleep; review KDE power management"
                                               : "Operation is not supported by KDE power management";
                    } else if (value.metaType().id() != QMetaType::QString ||
                               (value.toString() != "yes" && value.toString() != "challenge"))
                        error = "Operation is unavailable or denied by system policy";
                }
                if (!error.isEmpty()) break;
            }
            states[name] = {error.isEmpty(), error};
        }
        emit changed();
    }
    void refresh() {
        pending = true;
        states.clear();
        received.fill(false);
        const auto epoch = ++generation;
        deadline.start(1500);
        const QPointer<CachedPower> guard(this);
        for (int index = 0; index < 5; ++index) {
            const bool system = index >= 3;
            const auto interface = system ? QString("org.freedesktop.login1.Manager")
                : index == 2 ? QString("org.freedesktop.PowerManagement.Inhibit")
                             : QString("org.freedesktop.PowerManagement");
            const auto request = QDBusMessage::createMethodCall(
                system ? "org.freedesktop.login1" : "org.freedesktop.PowerManagement",
                system ? "/org/freedesktop/login1" : index == 2 ? "/org/freedesktop/PowerManagement/Inhibit"
                                                                             : "/org/freedesktop/PowerManagement",
                interface, index == 2 ? "HasInhibit" : (index == 0 || index == 3) ? "CanSuspend" : "CanHibernate");
            transport(system, request, [guard, epoch, index](QDBusMessage reply) {
                if (!guard || !guard->pending || guard->generation != epoch || guard->received[index]) return;
                guard->replies[index] = std::move(reply);
                guard->received[index] = true;
                if (std::all_of(guard->received.begin(), guard->received.end(), [](bool value) { return value; }))
                    guard->finish(epoch);
            });
        }
    }
  public:
    CachedPower(PowerAsyncCall call, std::function<qint64()> clock, PowerCall dispatch)
        : transport(std::move(call)), now(std::move(clock)), execution(std::move(dispatch)) {
        deadline.setSingleShot(true);
        deadline.setTimerType(Qt::PreciseTimer);
        connect(&deadline, &QTimer::timeout, this, [this] { finish(generation); });
        for (bool system : {false, true}) {
            auto *watcher = new QDBusServiceWatcher(system ? "org.freedesktop.login1" : "org.freedesktop.PowerManagement",
                system ? QDBusConnection::systemBus() : QDBusConnection::sessionBus(),
                QDBusServiceWatcher::WatchForOwnerChange, this);
            connect(watcher, &QDBusServiceWatcher::serviceOwnerChanged, this, [this] { invalidate(); });
        }
    }
    PowerAvailability capability(const QString &action) override {
        if (action != "sleep" && action != "hibernate") return {false, "Unknown native power action"};
        if (!pending && (states.isEmpty() || now() >= expires)) refresh();
        if (pending) return {false, "Checking KDE/logind power availability"};
        return states.value(action);
    }
    void invalidate() override {
        ++generation;
        deadline.stop();
        pending = false;
        states.clear();
        emit changed();
    }
    bool discoveryPending() const override { return pending; }
    PowerAvailability presentedCapability(const QString &action) override {
        return states.value(action, {false, "Checking KDE/logind power availability"});
    }
    void execute(const QString &action) override {
        // Never dispatch from cached permission. Keep the original fresh KDE,
        // Polkit and atomic logind inhibitor checks after the menu is dismissed.
        execution.execute(action);
    }
};
}
std::shared_ptr<PowerManager> cachedPowerManager(PowerAsyncCall call,
                                               std::function<qint64()> clock,
                                               PowerCall execution) {
    return std::make_shared<CachedPower>(std::move(call), std::move(clock),
                                         execution ? std::move(execution) : blockingTransport());
}
std::shared_ptr<PowerManager> powerManager(PowerCall call) {
    if (call) return std::make_shared<DBusPower>(std::move(call));
    auto timer = std::make_shared<QElapsedTimer>();
    timer->start();
    return cachedPowerManager([](bool system, const QDBusMessage &request, PowerReply done) {
        auto *watcher = new QDBusPendingCallWatcher(
            (system ? QDBusConnection::systemBus() : QDBusConnection::sessionBus()).asyncCall(request, 1500),
            QCoreApplication::instance());
        QObject::connect(watcher, &QDBusPendingCallWatcher::finished, watcher,
                         [done = std::move(done)](QDBusPendingCallWatcher *finished) {
            done(finished->reply());
            finished->deleteLater();
        });
    }, [timer] { return timer->elapsed(); });
}
}
