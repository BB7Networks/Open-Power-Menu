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

// One generation shares HasInhibit between the two operations. All five reads
// run concurrently; one unresponsive service cannot accumulate sequential waits.
class CachedPower final : public PowerManager {
    PowerAsyncCall transport;
    std::function<qint64()> now;
    std::unique_ptr<DBusPower> testExecution;
    Completion completion;
    std::function<bool()> selectionValid;
    QTimer executionDeadline;
    quint64 executionEpoch = 0;
    int executionStep = 0, readTimeout, authTimeout;
    bool executing = false, uncertain = false;
    QString operation;
    void complete(QString error, bool unknown = false) {
        executionDeadline.stop();
        executing = false;
        uncertain = unknown;
        auto done = std::move(completion);
        completion = {};
        selectionValid = {};
        if (done) done(std::move(error));
    }
    void advance() {
        const auto epoch = executionEpoch;
        if (selectionValid && !selectionValid()) {
            complete("The selection or client changed. Reopen the menu to refresh it."); return;
        }
        const int step = executionStep;
        const bool system = step >= 2;
        auto request = QDBusMessage::createMethodCall(
            system ? "org.freedesktop.login1" : "org.freedesktop.PowerManagement",
            system ? "/org/freedesktop/login1" : step == 1 ? "/org/freedesktop/PowerManagement/Inhibit" : "/org/freedesktop/PowerManagement",
            system ? "org.freedesktop.login1.Manager" : step == 1 ? "org.freedesktop.PowerManagement.Inhibit" : "org.freedesktop.PowerManagement",
            step == 1 ? "HasInhibit" : step == 3 ? operation + "WithFlags" : "Can" + operation);
        if (step == 3) {
            request.setArguments({QVariant::fromValue(qulonglong(1))});
            request.setInteractiveAuthorizationAllowed(true);
        }
        executionDeadline.start(step == 3 ? authTimeout : readTimeout);
        const QPointer<CachedPower> guard(this);
        transport(system, request, [guard, epoch, step](QDBusMessage reply) {
            if (!guard || guard->executionEpoch != epoch || guard->executionStep != step) return;
            if (!guard->executing) return; // A timeout is never retried or reinterpreted by a late callback.
            guard->executionDeadline.stop();
            if (reply.type() == QDBusMessage::ErrorMessage) {
                const bool unknown = step == 3 && (reply.errorName().endsWith("NoReply") || reply.errorName().endsWith("Timeout") || reply.errorName().endsWith("Disconnected"));
                guard->complete("Power management: " + reply.errorName() + ": " + reply.errorMessage() +
                    (unknown ? ". Completion is uncertain; do not retry." : ""), unknown);
                return;
            }
            if (reply.type() != QDBusMessage::ReplyMessage || reply.arguments().size() != (step == 3 ? 0 : 1)) {
                guard->complete("Invalid power response", step == 3); return;
            }
            if (step == 3) { guard->complete({}); return; }
            const auto value = reply.arguments().first();
            const bool allowed = step == 2 ? value.metaType().id() == QMetaType::QString &&
                (value.toString() == "yes" || value.toString() == "challenge") :
                value.metaType().id() == QMetaType::Bool && value.toBool() == (step == 0);
            if (!allowed) { guard->complete(step == 1 ? "An application is preventing sleep; review KDE power management" : "Power operation is unavailable or denied by system policy"); return; }
            ++guard->executionStep;
            guard->advance();
        });
    }
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
    CachedPower(PowerAsyncCall call, std::function<qint64()> clock, PowerCall dispatch, int checkTimeout, int authorizationTimeout)
        : transport(std::move(call)), now(std::move(clock)), readTimeout(checkTimeout), authTimeout(authorizationTimeout) {
        if (dispatch) testExecution = std::make_unique<DBusPower>(std::move(dispatch));
        executionDeadline.setSingleShot(true);
        executionDeadline.setTimerType(Qt::PreciseTimer);
        connect(&executionDeadline, &QTimer::timeout, this, [this] {
            complete(executionStep == 3 ? "Power authorization timed out. Completion is uncertain; do not retry." : "Power policy check timed out", executionStep == 3);
        });
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
        ++executionEpoch;
        if (executing) complete("Power service changed. Reopen the menu; the operation was not retried.", executionStep == 3);
        // An uncertain dispatched operation stays quarantined for this manager's lifetime.
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
        // Synchronous execution is retained only for explicitly injected test
        // transports. Production frontends must await executeAsync completion.
        if (!testExecution) throw Error("Power activation requires asynchronous completion", "power");
        testExecution->execute(action);
    }
    bool executionPending() const override { return executing || uncertain; }
    void executeAsync(const QString &action, Completion done, std::function<bool()> valid) override {
        if (executionPending()) { done("A power operation is pending or its completion is uncertain; do not retry."); return; }
        if (action != "sleep" && action != "hibernate") { done("Unknown native power action"); return; }
        operation = action == "sleep" ? "Suspend" : "Hibernate";
        completion = std::move(done);
        selectionValid = std::move(valid);
        executing = true;
        executionStep = 0;
        ++executionEpoch;
        advance();
    }
};
}
std::shared_ptr<PowerManager> cachedPowerManager(PowerAsyncCall call,
                                               std::function<qint64()> clock,
                                               PowerCall execution, int checkTimeout, int authorizationTimeout) {
    return std::make_shared<CachedPower>(std::move(call), std::move(clock), std::move(execution), checkTimeout, authorizationTimeout);
}
void PowerManager::executeAsync(const QString &action, Completion done, std::function<bool()> valid) {
    try {
        if (valid && !valid()) throw Error("The selection changed. Reopen the menu to refresh it.");
        execute(action); // Explicitly injected synchronous fixtures only.
        done({});
    } catch (const Error &error) { done(QString::fromUtf8(error.what())); }
}
std::shared_ptr<PowerManager> powerManager(PowerCall call) {
    if (call) return std::make_shared<DBusPower>(std::move(call));
    auto timer = std::make_shared<QElapsedTimer>();
    timer->start();
    return cachedPowerManager([](bool system, const QDBusMessage &request, PowerReply done) {
        auto *watcher = new QDBusPendingCallWatcher(
            (system ? QDBusConnection::systemBus() : QDBusConnection::sessionBus()).asyncCall(request, request.isInteractiveAuthorizationAllowed() ? 120000 : 1500),
            QCoreApplication::instance());
        QObject::connect(watcher, &QDBusPendingCallWatcher::finished, watcher,
                         [done = std::move(done)](QDBusPendingCallWatcher *finished) {
            done(finished->reply());
            finished->deleteLater();
        });
    }, [timer] { return timer->elapsed(); });
}
}
