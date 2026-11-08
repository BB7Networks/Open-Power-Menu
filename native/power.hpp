#pragma once
#include <QDBusMessage>
#include <QString>
#include <functional>
#include <memory>
namespace Opm {
struct PowerAvailability { bool available = false; QString reason; };
class PowerManager {
  public:
    virtual ~PowerManager() = default;
    virtual PowerAvailability capability(const QString &action) = 0;
    virtual void execute(const QString &action) = 0;
};
// Injectable transport: tests never need a real power manager or a host bus.
using PowerCall = std::function<QDBusMessage(bool system, const QDBusMessage &)>;
std::shared_ptr<PowerManager> powerManager(PowerCall call = {});
}
