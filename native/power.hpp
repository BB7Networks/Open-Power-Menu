#pragma once
#include <QDBusMessage>
#include <QString>
#include <QObject>
#include <functional>
#include <memory>
namespace Opm {
struct PowerAvailability { bool available = false; QString reason; };
class PowerManager : public QObject {
    Q_OBJECT
  public:
    virtual ~PowerManager() = default;
    virtual PowerAvailability capability(const QString &action) = 0;
    // Selection must not initiate a new discovery that shifts presented keys.
    // This is presentation state only; execute() always checks current policy.
    virtual PowerAvailability presentedCapability(const QString &action) { return capability(action); }
    virtual void execute(const QString &action) = 0;
    virtual void invalidate() {}
    virtual bool discoveryPending() const { return false; }
  signals:
    void changed();
};
// Injectable transport: tests never need a real power manager or a host bus.
using PowerCall = std::function<QDBusMessage(bool system, const QDBusMessage &)>;
std::shared_ptr<PowerManager> powerManager(PowerCall call = {});
using PowerReply = std::function<void(QDBusMessage)>;
using PowerAsyncCall = std::function<void(bool, const QDBusMessage &, PowerReply)>;
// All callbacks run on the owner's event thread. Injectable clock/transport
// allow deterministic cache, recovery and late-response tests without power actions.
std::shared_ptr<PowerManager> cachedPowerManager(PowerAsyncCall call,
                                               std::function<qint64()> clock,
                                               PowerCall execution = {});
}
