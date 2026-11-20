#include "physical_keys.hpp"
#include <QGuiApplication>
#include <QPointer>
#include <QQmlExtensionPlugin>
#include <QWindow>
#include <QtQml>
#include <QScopedValueRollback>

class InputGuard : public QObject {
    Q_OBJECT
    Q_PROPERTY(bool ready READ ready NOTIFY readyChanged)
    Q_PROPERTY(bool active READ active WRITE setActive NOTIFY activeChanged)
    Q_PROPERTY(bool navigationEnabled MEMBER navigationEnabled)
    Q_PROPERTY(bool diagnosticsEnabled MEMBER diagnosticsEnabled)
    Opm::PhysicalKeys keys;
    QSet<QObject *> windows;
    bool enabled = false, replaying = false, navigationEnabled = true;
    bool diagnosticsEnabled = false;
  public:
    explicit InputGuard(QObject *parent = nullptr) : QObject(parent) {
        qApp->installEventFilter(this);
    }
    ~InputGuard() override { qApp->removeEventFilter(this); }
    bool ready() const { return keys.ready(); }
    bool active() const { return enabled; }
    void setActive(bool value) {
        if (value == enabled) return;
        keys.setActive(value); enabled = value; emit activeChanged(); emit readyChanged();
    }
    Q_INVOKABLE void watch(QObject *window) {
        if (!qobject_cast<QWindow *>(window) || windows.contains(window)) return;
        windows.insert(window);
        connect(window, &QObject::destroyed, this, [this, window] { windows.remove(window); });
    }
    Q_INVOKABLE void unwatch(QObject *window) { windows.remove(window); }
  signals:
    void readyChanged();
    void activeChanged();
    void inputDecision(QString decision, int key, bool qtRepeat, QObject *window);
  protected:
    bool eventFilter(QObject *object, QEvent *event) override {
        if (replaying || !windows.contains(object)) return false;
        if (event->type() == QEvent::KeyRelease) {
            keys.release(*static_cast<QKeyEvent *>(event)); return false;
        }
        if (event->type() != QEvent::KeyPress) return false;
        auto *key = static_cast<QKeyEvent *>(event);
        const auto admission = keys.press(*key);
        if (diagnosticsEnabled)
            emit inputDecision(admission == Opm::KeyAdmission::Press ? "press" :
                admission == Opm::KeyAdmission::NavigationRepeat ? "navigation-repeat" : "rejected",
                key->key(), key->isAutoRepeat(), object);
        emit readyChanged();
        // Preserve typing/repeat in editable controls. Physical evidence is
        // still consumed so moving focus out of a field cannot rearm its hold.
        auto *item = object->property("activeFocusItem").value<QObject *>();
        const bool editable = item && item->property("text").isValid() && item->property("cursorPosition").isValid();
        if (!navigationEnabled || editable) return false;
        if (admission == Opm::KeyAdmission::Reject) return true;
        const bool repeat = admission == Opm::KeyAdmission::NavigationRepeat;
        if (key->isAutoRepeat() == repeat) return false;
        // Raw XI2 can prove a genuine same-millisecond release/repress that
        // Qt mislabeled as repeat. Normalize only this OPM window's delivery.
        QKeyEvent normalized(key->type(), key->key(), key->modifiers(), key->nativeScanCode(),
            key->nativeVirtualKey(), key->nativeModifiers(), key->text(), repeat, key->count(), key->device());
        normalized.setTimestamp(key->timestamp());
        QScopedValueRollback<bool> scope(replaying, true);
        QCoreApplication::sendEvent(object, &normalized);
        return true;
    }
};
class InputPlugin : public QQmlExtensionPlugin {
    Q_OBJECT
    Q_PLUGIN_METADATA(IID QQmlExtensionInterface_iid)
  public:
    void registerTypes(const char *uri) override { qmlRegisterType<InputGuard>(uri, 1, 0, "InputGuard"); }
};
#include "input_plugin.moc"
