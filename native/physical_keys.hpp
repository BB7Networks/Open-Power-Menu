#pragma once
#include <QKeyEvent>
#include <QObject>
#include <QQueue>
#include <QSet>
#include <memory>

namespace Opm {
enum class KeyAdmission { Reject, Press, NavigationRepeat };

// Native scan codes/timestamps only; never key text. Queued physical presses
// survive releases so a complete rapid press/release/press batch stays valid.
class PhysicalPresses {
    struct Press { quint32 scan, time; };
    QQueue<Press> presses;
    QSet<quint64> down;
    QSet<quint32> unknownDown, navigation;
    bool collecting = false;
  public:
    void collect(bool enabled) { collecting = enabled; presses.clear(); navigation.clear(); }
    void snapshot(const QSet<quint32> &held) { down.clear(); unknownDown = held; presses.clear(); navigation.clear(); }
    void press(quint32 scan, quint32 time, quint16 source, bool repeat);
    void release(quint32 scan, quint16 source);
    KeyAdmission take(quint32 scan, quint32 time, bool arrow);
};

// One instance for an entire OPM menu tree. X11 observes XI2 on a separate,
// read-only connection; it never changes the shell's XKB or input settings.
class PhysicalKeys : public QObject {
    Q_OBJECT
    struct X11;
    std::unique_ptr<X11> x11;
    QSet<int> held, navigation;
    bool active = false;
  public:
    explicit PhysicalKeys(QObject *parent = nullptr);
    ~PhysicalKeys() override;
    bool ready() const;
    bool isX11() const { return bool(x11); }
    void setActive(bool value);
    KeyAdmission press(const QKeyEvent &event);
    void release(const QKeyEvent &event);
};
} // namespace Opm
