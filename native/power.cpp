#include "power.hpp"
#include "model.hpp"
#include <QDBusArgument>
#include <QDBusConnection>
#include <QVariant>
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
std::shared_ptr<PowerManager> powerManager(PowerCall call) {
    if (!call) call = [](bool system, const QDBusMessage &request) {
        return (system ? QDBusConnection::systemBus() : QDBusConnection::sessionBus())
            .call(request, QDBus::Block, request.isInteractiveAuthorizationAllowed() ? 120000 : 1500);
    };
    return std::make_shared<DBusPower>(std::move(call));
}
}
