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
#ifdef OPM_HAVE_KCONFIG
#include <KAuthorized>
#endif
namespace Opm {
QDBusMessage sessionPowerRequest(const QString &action) {
    const bool confirm = action.endsWith("-confirm");
    const auto name = confirm ? action.chopped(8) : action;
    QString method;
    if (name == "shutdown") method = confirm ? "promptShutDown" : "logoutAndShutdown";
    else if (name == "reboot") method = confirm ? "promptReboot" : "logoutAndReboot";
    else if (name == "logout") method = confirm ? "promptLogout" : "logout";
    else return {};
    const QString service = confirm ? "org.kde.LogoutPrompt" : "org.kde.Shutdown";
    return QDBusMessage::createMethodCall(service, confirm ? "/LogoutPrompt" : "/Shutdown", service, method);
}
namespace {
bool logoutAuthorized() {
#ifdef OPM_HAVE_KCONFIG
    // Match KWorkspace::SessionManagement::canLogout(), including old kiosk keys.
    return KAuthorized::authorizeAction(QStringLiteral("logout")) && KAuthorized::authorize(QStringLiteral("logout"));
#else
    // The Qt-only development preview must fail closed. Complete native builds
    // require KConfigCore; do not hand-parse KDE's layered/locked kiosk policy.
    return false;
#endif
}
QString sessionPermission(const QString &action) {
    if (action.startsWith("shutdown")) return "CanPowerOff";
    if (action.startsWith("reboot")) return "CanReboot";
    return {};
}
QStringList serviceNames(const QDBusMessage &reply) {
    if (reply.type() != QDBusMessage::ReplyMessage || reply.arguments().size() != 1)
        throw Error("Could not discover KDE session services", "power");
    const auto value = reply.arguments().first();
    if (value.metaType().id() == QMetaType::QStringList) return value.toStringList();
    if (value.metaType().id() == qMetaTypeId<QDBusArgument>() && value.value<QDBusArgument>().currentSignature() == "as")
        return qdbus_cast<QStringList>(value);
    throw Error("Invalid KDE session-service discovery response", "power");
}
bool permitted(const QDBusMessage &reply) {
    return reply.type() == QDBusMessage::ReplyMessage && reply.arguments().size() == 1 &&
        reply.arguments().first().metaType().id() == QMetaType::QString &&
        QStringList{"yes", "challenge"}.contains(reply.arguments().first().toString());
}
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
        const auto session = sessionPowerRequest(action);
        if (session.type() == QDBusMessage::MethodCallMessage) {
            if (!logoutAuthorized()) throw Error("KDE policy does not allow signing out", "power");
            const auto names = serviceNames(call(false, "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "ListNames")) +
                serviceNames(call(false, "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "ListActivatableNames"));
            if (!names.contains(session.service())) throw Error("KDE session service is unavailable", "power");
            const auto permission = sessionPermission(action);
            if (!permission.isEmpty() && !permitted(call(true, "org.freedesktop.login1", "/org/freedesktop/login1", "org.freedesktop.login1.Manager", permission)))
                throw Error("Session operation is unavailable or denied by system policy", "power");
            return;
        }
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
        const auto session = sessionPowerRequest(action);
        if (session.type() == QDBusMessage::MethodCallMessage) {
            call(false, session.service(), session.path(), session.interface(), session.member());
            return;
        }
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
    QString sessionOperation;
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
        if (!sessionOperation.isEmpty()) { advanceSession(); return; }
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
    void advanceSession() {
        if (selectionValid && !selectionValid()) {
            complete("The selection or client changed. Reopen the menu to refresh it."); return;
        }
        if (!logoutAuthorized()) { complete("KDE policy does not allow signing out"); return; }
        const auto permission = sessionPermission(sessionOperation);
        const bool final = executionStep == 3 || permission.isEmpty();
        executionStep = final ? 3 : 2;
        auto request = final ? sessionPowerRequest(sessionOperation) : QDBusMessage::createMethodCall(
            "org.freedesktop.login1", "/org/freedesktop/login1", "org.freedesktop.login1.Manager", permission);
        const auto epoch = executionEpoch;
        executionDeadline.start(readTimeout);
        const QPointer<CachedPower> guard(this);
        transport(!final, request, [guard, epoch, final](QDBusMessage reply) {
            if (!guard || !guard->executing || guard->executionEpoch != epoch || guard->executionStep != (final ? 3 : 2)) return;
            guard->executionDeadline.stop();
            if (reply.type() == QDBusMessage::ErrorMessage) {
                const bool unknown = final && (reply.errorName().endsWith("NoReply") || reply.errorName().endsWith("Timeout") || reply.errorName().endsWith("Disconnected"));
                guard->complete("KDE session request: " + reply.errorName() + ": " + reply.errorMessage() +
                    (unknown ? ". Acceptance is uncertain; do not retry." : ""), unknown);
            } else if (final) {
                if (reply.type() != QDBusMessage::ReplyMessage || !reply.arguments().isEmpty())
                    guard->complete("Invalid KDE session reply. Acceptance is uncertain; do not retry.", true);
                else guard->complete({}); // KDE accepted the request; this is not proof of completed shutdown.
            } else if (!permitted(reply)) guard->complete("Session operation is unavailable or denied by system policy");
            else { guard->executionStep = 3; guard->advanceSession(); }
        });
    }
    QHash<QString, PowerAvailability> sessionStates;
    std::array<QDBusMessage, 4> sessionReplies;
    std::array<bool, 4> sessionReceived{};
    QTimer sessionDeadline;
    bool sessionPending = false;
    quint64 sessionGeneration = 0;
    qint64 sessionExpires = 0;
    void finishSession(quint64 epoch) {
        if (!sessionPending || epoch != sessionGeneration) return;
        sessionPending = false;
        sessionDeadline.stop();
        sessionExpires = now() + 5000;
        for (const auto &name : {"shutdown", "reboot", "logout"}) for (bool confirm : {false, true}) {
            const QString action = QString::fromLatin1(name) + (confirm ? "-confirm" : "");
            QString error;
            try {
                const auto names = serviceNames(sessionReplies[0]) + serviceNames(sessionReplies[1]);
                if (!names.contains(sessionPowerRequest(action).service())) error = "KDE session service is unavailable";
                if (QString(name) != "logout" && !permitted(sessionReplies[QString(name) == "shutdown" ? 2 : 3]))
                    error = "Session operation is unavailable or denied by system policy";
            } catch (const Error &e) { error = QString::fromUtf8(e.what()); }
            sessionStates[action] = {error.isEmpty(), error};
        }
        emit changed();
    }
    void refreshSession() {
        sessionPending = true;
        sessionReceived.fill(false);
        sessionReplies.fill({});
        const auto epoch = ++sessionGeneration;
        sessionDeadline.start(readTimeout);
        const QPointer<CachedPower> guard(this);
        for (int i = 0; i < 4; ++i) {
            const bool system = i >= 2;
            auto request = QDBusMessage::createMethodCall(system ? "org.freedesktop.login1" : "org.freedesktop.DBus",
                system ? "/org/freedesktop/login1" : "/org/freedesktop/DBus",
                system ? "org.freedesktop.login1.Manager" : "org.freedesktop.DBus",
                QStringList{"ListNames", "ListActivatableNames", "CanPowerOff", "CanReboot"}[i]);
            // Discovery only consults the bus daemon and read-only logind policy;
            // it never activates plasma-shutdown or the logout greeter.
            request.setAutoStartService(false);
            transport(system, request, [guard, epoch, i](QDBusMessage reply) {
                if (!guard || !guard->sessionPending || guard->sessionGeneration != epoch || guard->sessionReceived[i]) return;
                guard->sessionReplies[i] = std::move(reply);
                guard->sessionReceived[i] = true;
                if (std::all_of(guard->sessionReceived.begin(), guard->sessionReceived.end(), [](bool value) { return value; }))
                    guard->finishSession(epoch);
            });
        }
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
            if (!sessionOperation.isEmpty()) {
                complete(executionStep == 3 ? "KDE session request timed out. Acceptance is uncertain; do not retry." : "Session policy check timed out", executionStep == 3);
                return;
            }
            complete(executionStep == 3 ? "Power authorization timed out. Completion is uncertain; do not retry." : "Power policy check timed out", executionStep == 3);
        });
        deadline.setSingleShot(true);
        deadline.setTimerType(Qt::PreciseTimer);
        connect(&deadline, &QTimer::timeout, this, [this] { finish(generation); });
        sessionDeadline.setSingleShot(true);
        connect(&sessionDeadline, &QTimer::timeout, this, [this] { finishSession(sessionGeneration); });
        for (bool system : {false, true}) {
            auto *watcher = new QDBusServiceWatcher(system ? "org.freedesktop.login1" : "org.freedesktop.PowerManagement",
                system ? QDBusConnection::systemBus() : QDBusConnection::sessionBus(),
                QDBusServiceWatcher::WatchForOwnerChange, this);
            connect(watcher, &QDBusServiceWatcher::serviceOwnerChanged, this, [this] { invalidate(); });
        }
    }
    PowerAvailability capability(const QString &action) override {
        if (sessionPowerRequest(action).type() == QDBusMessage::MethodCallMessage) {
            if (!logoutAuthorized()) return {false, "KDE policy does not allow signing out"};
            if (!sessionPending && (sessionStates.isEmpty() || now() >= sessionExpires)) refreshSession();
            return sessionPending ? PowerAvailability{false, "Checking KDE session availability"} : sessionStates.value(action);
        }
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
        ++sessionGeneration;
        sessionDeadline.stop(); sessionPending = false; sessionStates.clear();
        emit changed();
    }
    bool discoveryPending() const override { return pending || sessionPending; }
    PowerAvailability presentedCapability(const QString &action) override {
        if (sessionPowerRequest(action).type() == QDBusMessage::MethodCallMessage)
            return logoutAuthorized() ? sessionStates.value(action, {false, "Checking KDE session availability"})
                                     : PowerAvailability{false, "KDE policy does not allow signing out"};
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
        sessionOperation = sessionPowerRequest(action).type() == QDBusMessage::MethodCallMessage ? action : QString();
        if (sessionOperation.isEmpty() && action != "sleep" && action != "hibernate") { done("Unknown native power action"); return; }
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
