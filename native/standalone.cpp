#include "standalone.hpp"
#include "launch.hpp"
#include <QEventLoop>
#include <QPointer>
#include "launch.hpp"
#include <QApplication>
#include <QCursor>
#include <QMouseEvent>
#include <QEvent>
#include <QIcon>
#include <QIconEngine>
#include <QImage>
#include <QPainter>
#include <QKeyEvent>
#include <QJsonDocument>
#include <QMetaEnum>
#include <QScreen>
#include <QTextStream>
#include <QWindow>
#include <QProxyStyle>
#include <QStyleOptionMenuItem>
#include <algorithm>

namespace Opm {
// A light desktop's flat symbolic icons otherwise disappear on Aero's dark
// surface. Keep the original engine's sizes, DPI and colored/multitone artwork.
class AeroIconEngine final : public QIconEngine {
    const QIcon source;
    static QPixmap readable(QPixmap pixmap, QIcon::Mode mode) {
        if (pixmap.isNull()) return pixmap;
        auto image = pixmap.toImage().convertToFormat(QImage::Format_ARGB32);
        int low = 255, high = 0;
        bool seen = false;
        for (int y = 0; y < image.height(); ++y)
            for (int x = 0; x < image.width(); ++x) {
                const auto pixel = image.pixel(x, y);
                if (qAlpha(pixel) < 32) continue;
                const int minimum = std::min({qRed(pixel), qGreen(pixel), qBlue(pixel)});
                const int maximum = std::max({qRed(pixel), qGreen(pixel), qBlue(pixel)});
                if (maximum - minimum > 16) return pixmap;
                low = std::min(low, minimum); high = std::max(high, maximum); seen = true;
            }
        if (!seen || high > 112 || high - low > 16) return pixmap;
        const QColor foreground = mode == QIcon::Disabled ? QColor("#89939c") : QColor("#e4ebf2");
        for (int y = 0; y < image.height(); ++y)
            for (int x = 0; x < image.width(); ++x)
                image.setPixel(x, y, qRgba(foreground.red(), foreground.green(), foreground.blue(), qAlpha(image.pixel(x, y))));
        auto result = QPixmap::fromImage(image);
        result.setDevicePixelRatio(pixmap.devicePixelRatio());
        return result;
    }
  public:
    explicit AeroIconEngine(QIcon icon) : source(std::move(icon)) {}
    QIconEngine *clone() const override { return new AeroIconEngine(source); }
    QSize actualSize(const QSize &size, QIcon::Mode mode, QIcon::State state) override {
        return source.actualSize(size, mode, state);
    }
    QPixmap pixmap(const QSize &size, QIcon::Mode mode, QIcon::State state) override {
        return readable(source.pixmap(size, mode, state), mode);
    }
    QPixmap scaledPixmap(const QSize &size, QIcon::Mode mode, QIcon::State state, qreal scale) override {
        return readable(source.pixmap(size, scale, mode, state), mode);
    }
    void paint(QPainter *painter, const QRect &rect, QIcon::Mode mode, QIcon::State state) override {
        painter->drawPixmap(rect, scaledPixmap(rect.size(), mode, state, painter->device()->devicePixelRatioF()));
    }
};
// Local to each OPM menu. Never replace QApplication's desktop style.
class MenuStyle final : public QProxyStyle {
    const QJsonObject config;
  public:
    MenuStyle(const QJsonObject &cfg, QMenu *menu) : config(cfg) { setParent(menu); }
    int styleHint(StyleHint hint, const QStyleOption *option = nullptr, const QWidget *widget = nullptr,
                  QStyleHintReturn *data = nullptr) const override {
        if (hint == SH_Menu_SubMenuPopupDelay && submenuHoverDelay(config) >= 0)
            return submenuHoverDelay(config);
        return QProxyStyle::styleHint(hint, option, widget, data);
    }
    int pixelMetric(PixelMetric metric, const QStyleOption *option = nullptr, const QWidget *widget = nullptr) const override {
        if (metric == PM_SmallIconSize && config["menu_icon_size"].toString("standard") != "standard") {
            const int height = widget ? widget->fontMetrics().height() : 18;
            return qRound((config["menu_icon_size"] == "small" ? 14 : 24) * std::max(1., height / 18.));
        }
        return QProxyStyle::pixelMetric(metric, option, widget);
    }
    QSize sizeFromContents(ContentsType type, const QStyleOption *option, const QSize &contents,
                           const QWidget *widget = nullptr) const override {
        auto result = QProxyStyle::sizeFromContents(type, option, contents, widget);
        const auto *item = qstyleoption_cast<const QStyleOptionMenuItem *>(option);
        if (type == CT_MenuItem && item && item->menuItemType != QStyleOptionMenuItem::Separator) {
            const auto density = config["menu_density"].toString("standard");
            const int icon = item->icon.isNull() ? 0 : pixelMetric(PM_SmallIconSize, option, widget);
            const int minimum = std::max(item->fontMetrics.height(), icon);
            if (density != "standard") result.setHeight(minimum + (density == "compact" ? 6 : 16));
            else result.setHeight(std::max(result.height(), minimum + 4));
            const auto width = config["menu_width"].toString("auto");
            if (width != "auto") result.setWidth(std::max(result.width(), qRound((width == "narrow" ? 240 : 394) * std::max(1., item->fontMetrics.height() / 18.))));
        }
        return result;
    }
};
QPoint menuPosition(const QRect &area, const QSize &size, const QPoint &cursor,
                    const QString &anchor) {
    QPoint pos = cursor;
    if (anchor == "bottom-left")
        pos = {area.left() + 8, area.bottom() - size.height() - 7};
    else if (anchor == "bottom-right")
        pos = {area.right() - size.width() - 7, area.bottom() - size.height() - 7};
    pos.setX(std::clamp(pos.x(), area.left(), std::max(area.left(), area.right() - size.width() + 1)));
    pos.setY(std::clamp(pos.y(), area.top(), std::max(area.top(), area.bottom() - size.height() + 1)));
    return pos;
}
Standalone::Standalone(QJsonObject source, QString theme, bool diagnostics, std::shared_ptr<PowerManager> power, std::function<bool()> stillCurrent)
    : config(std::move(source)), model(std::move(power)), current(std::move(stillCurrent)), traceEnabled(diagnostics),
      wayland(QGuiApplication::platformName().startsWith("wayland")),
      darkAero((theme.isEmpty() ? config["appearance"].toString() : theme) == "aero") {
    validate(config);
    elapsed.start();
    setObjectName("OpenPowerMenu");
    setWindowTitle("Open Power Menu");
    setToolTipsVisible(true);
    setStyle(new MenuStyle(config, this));
    setMinimumWidth(config["menu_width"].toString("auto") == "auto" ? 292 :
                    qRound((config["menu_width"] == "narrow" ? 240 : 394) * std::max(1., fontMetrics().height() / 18.)));
    if (wayland)
        setWindowFlags(Qt::Window | Qt::FramelessWindowHint);
    setStyleSheet("QMenu { menu-scrollable: 1; }");
    if (darkAero)
        setStyleSheet(QStringLiteral(
            "QMenu { menu-scrollable:1; background-color:#242A31; color:#E4EBF2; border:1px solid #5E7D94; padding:5px 3px; }"
            "QMenu::item { padding:%1px 25px %1px 13px; border-radius:2px; }"
            "QMenu::item:selected { background-color:#355B76; color:#FFFFFF; }"
            "QMenu::item:disabled { color:#89939C; }"
            "QMenu::separator { height:1px; background:#445463; margin:5px 10px; }"
            "QMenu::icon { padding-left:5px; }").arg(config["menu_density"] == "compact" ? 3 : config["menu_density"] == "comfortable" ? 8 : 6));
    if (config["menu_icon_size"].toString("standard") != "standard") {
        // Some desktop styles paint icons using their own metric rather than
        // the proxy's PM_SmallIconSize. Size this menu's icon subcontrol too.
        const int extent = style()->pixelMetric(QStyle::PM_SmallIconSize, nullptr, this);
        setStyleSheet(styleSheet() + QString("QMenu::icon { width:%1px; height:%1px; }").arg(extent));
    }
    captured = model.capture(config);
    presentation = captured.menu;
    installEventFilter(this);
    populate(this, presentation);
    if (presentation.isEmpty() && model.powerCapabilities()->discoveryPending()) {
        auto *loading = addAction("Checking power availability…");
        loading->setEnabled(false);
    }
    connect(model.powerCapabilities().get(), &PowerManager::changed, this, [this] {
        auto updated = model.capture(config);
        // Do not silently replace dispatch identity when only command alternatives change.
        if (updated.menu == presentation && !presentation.isEmpty()) return;
        captured = std::move(updated);
        presentation = captured.menu;
        populate(this, presentation);
        if (presentation.isEmpty() && !model.powerCapabilities()->discoveryPending() && isVisible()) close();
        if (isVisible()) adjustSize();
    });
    transitionTimer.setSingleShot(true);
    transitionTimer.setInterval(150);
    connect(&transitionTimer, &QTimer::timeout, this, [this] {
        entered = isVisible() && !inside.isEmpty();
        updateDismissal();
    });
    leaveTimer.setSingleShot(true);
    leaveTimer.setTimerType(Qt::PreciseTimer);
    leaveTimer.setInterval(pointerLeaveDelay(config));
    connect(&leaveTimer, &QTimer::timeout, this, [this] {
        if (config["auto_close_on_pointer_leave"].toBool() && isVisible() && entered &&
                !transitionTimer.isActive() && !keyboard && inside.isEmpty()) {
            report("pointer-dismissed");
            close();
        }
    });
    focusTimer.setSingleShot(true);
    focusTimer.setInterval(100);
    connect(&focusTimer, &QTimer::timeout, this, [this] {
        if (wayland && wasActive && QGuiApplication::applicationState() != Qt::ApplicationActive) {
            report("focus-dismissed");
            close();
        }
    });
    wasActive = QGuiApplication::applicationState() == Qt::ApplicationActive;
    connect(qApp, &QGuiApplication::applicationStateChanged, this, [this](Qt::ApplicationState state) {
        if (state == Qt::ApplicationActive) {
            wasActive = true;
            focusTimer.stop();
        } else if (wasActive && wayland && isVisible()) {
            focusTimer.start();
        }
    });
}
Standalone::~Standalone() {
    // QMenu destroys child menus after derived members have been destroyed.
    for (auto *child : findChildren<QMenu *>()) disconnect(child, nullptr, this, nullptr);
}
void Standalone::populate(QMenu *menu, const QJsonArray &entries) {
    // Reconcile rather than clear(): keep live submenu objects, focus, active
    // actions and dismissal membership while capability replies arrive.
    auto remaining = menu->actions();
    for (const auto &value : entries) {
        const auto entry = value.toObject();
        const auto kind = entry["kind"].toString();
        auto identity = entry;
        for (const auto &field : {"key", "items", "enabled", "unavailable_reason"}) identity.remove(field);
        QAction *action = nullptr;
        for (auto *candidate : remaining) {
            if (candidate->property("opmIdentity").toJsonObject() == identity) { action = candidate; break; }
        }
        if (action) remaining.removeOne(action);
        else {
            action = new QAction(menu);
            action->setProperty("opmIdentity", identity);
            if (kind == "submenu") {
                auto *child = new QMenu(menu);
                child->setStyle(new MenuStyle(config, child));
                child->setToolTipsVisible(true);
                child->installEventFilter(this);
                connect(child, &QObject::destroyed, this, [this, child] { inside.remove(child); });
                action->setMenu(child);
            }
            menu->insertAction(remaining.isEmpty() ? nullptr : remaining.first(), action);
        }
        auto title = entry["title"].toString();
        title.replace('&', "&&");
        if (!entry["access_hint"].toString().isEmpty()) title += '\t' + entry["access_hint"].toString();
        action->setText(title);
        QIcon icon = config["show_menu_icons"].toBool(true) ? QIcon::fromTheme(entry["icon"].toString()) : QIcon();
        if (darkAero && !icon.isNull()) icon = QIcon(new AeroIconEngine(icon));
        action->setIcon(icon);
        accessKeys.insert(action, entry["access_key"].toString());
        if (kind == "separator") action->setSeparator(true);
        else if (kind == "submenu") populate(action->menu(), entry["items"].toArray());
        else {
            action->setEnabled(entry["enabled"].toBool());
            action->setToolTip(action->isEnabled() ? QString() : entry["unavailable_reason"].toString("Application not installed or unavailable on this desktop"));
            selections.insert(action, entry["key"].toString());
        }
    }
    for (auto *action : remaining) {
        // Remove descendant map entries before deleting their owning menus.
        const auto forget = [this](auto &&self, QAction *item) -> void {
            selections.remove(item); accessKeys.remove(item);
            if (item->menu()) for (auto *child : item->menu()->actions()) self(self, child);
        };
        forget(forget, action);
        delete action->menu();
        menu->removeAction(action);
        delete action;
    }
}
void Standalone::report(const QString &event) {
    emit diagnostic(event);
    if (!traceEnabled)
        return;
    const auto *window = windowHandle();
    const QJsonObject state{{"event", event}, {"elapsed_ms", elapsed.elapsed()},
        {"platform", QGuiApplication::platformName()}, {"toplevel", wayland},
        {"visible", isVisible()}, {"exposed", window && window->isExposed()},
        {"active", isActiveWindow()}};
    QTextStream(stdout) << "OPM_LAUNCH " << QJsonDocument(state).toJson(QJsonDocument::Compact) << Qt::endl;
}
void Standalone::updateDismissal() {
    for (auto it = inside.begin(); it != inside.end();) {
        if (!(*it)->isVisible())
            it = inside.erase(it);
        else
            ++it;
    }
    if (!config["auto_close_on_pointer_leave"].toBool() || !isVisible() ||
        transitionTimer.isActive() || !entered || keyboard || !inside.isEmpty())
        leaveTimer.stop();
    else if (!leaveTimer.isActive())
        leaveTimer.start();
}
bool Standalone::eventFilter(QObject *object, QEvent *event) {
    auto *menu = qobject_cast<QMenu *>(object);
    if (menu) {
        if (event->type() == QEvent::Show && menu->screen()) {
            const int available = menu->screen()->availableGeometry().width();
            menu->setMinimumWidth(std::min(menu->minimumWidth(), available));
            menu->setMaximumWidth(available);
        }
        if (menu == this && event->type() == QEvent::Show && windowHandle())
            windowHandle()->installEventFilter(this);
        switch (event->type()) {
        case QEvent::Show: case QEvent::Move: case QEvent::Resize:
            if (isVisible()) {
                leaveTimer.stop();
                entered = false;
                transitionTimer.start();
            }
            break;
        case QEvent::Enter: inside.insert(menu); if (!transitionTimer.isActive()) entered = true; break;
        case QEvent::Leave: case QEvent::Hide: inside.remove(menu); break;
        case QEvent::KeyPress: {
            keyboard = true;
            updateDismissal();
            const auto *key = static_cast<QKeyEvent *>(event);
            if (!(key->modifiers() & (Qt::ControlModifier | Qt::AltModifier | Qt::MetaModifier)) &&
                ((key->key() >= Qt::Key_A && key->key() <= Qt::Key_Z) ||
                 (key->key() >= Qt::Key_0 && key->key() <= Qt::Key_9))) {
                if (!key->isAutoRepeat() && config["access_keys_enabled"].toBool(true)) {
                    const auto letter = QString(QChar(key->key()));
                    QAction *match = nullptr;
                    for (auto *action : menu->actions())
                        if (accessKeys.value(action) == letter) {
                            if (match) return true; // fail closed on any ambiguous presentation
                            match = action;
                        }
                    if (match && match->isEnabled()) {
                        menu->setActiveAction(match);
                        QKeyEvent activate(QEvent::KeyPress, match->menu() ? Qt::Key_Right : Qt::Key_Return,
                                           Qt::NoModifier);
                        QCoreApplication::sendEvent(menu, &activate);
                    }
                }
                return true;
            }
            break;
        }
        case QEvent::MouseMove: {
            const auto position = static_cast<QMouseEvent *>(event)->globalPosition();
            if ((!pointerKnown || position != lastPointer) && !transitionTimer.isActive()) keyboard = false;
            lastPointer = position;
            pointerKnown = true;
            break;
        }
        default: break;
        }
        if (menu == this && event->type() == QEvent::Hide) {
            leaveTimer.stop();
            focusTimer.stop();
            transitionTimer.stop();
            pointerKnown = false;
            inside.clear();
            entered = false;
        } else
            updateDismissal();
    }
    if (event->type() == QEvent::WindowActivate || event->type() == QEvent::WindowDeactivate ||
        event->type() == QEvent::Expose || event->type() == QEvent::Hide)
        report(QString::fromLatin1(QEvent::staticMetaObject.enumerator(
            QEvent::staticMetaObject.indexOfEnumerator("Type")).valueToKey(event->type())));
    return QMenu::eventFilter(object, event);
}
bool Standalone::executeSelection(QAction *action) {
    if (!action || !selections.contains(action) || !action->isEnabled())
        return false;
    lastError.clear();
    bool launched = false;
    const QPointer<Standalone> self(this);
    try {
        if (current && !current()) throw Error("Configuration changed. Reopen the menu to refresh it.");
        const auto key = selections.value(action);
        const auto snapshot = captured;
        const auto entry = model.selected(config, key, snapshot);
        if (entry.powerAction.isEmpty()) launched = launchDetached(entry.argv);
        else {
            QEventLoop wait;
            const QPointer<QEventLoop> loop(&wait);
            struct Result { bool finished = false; QString error; };
            auto result = std::make_shared<Result>();
            connect(this, &QObject::destroyed, &wait, &QEventLoop::quit);
            model.powerCapabilities()->executeAsync(entry.powerAction, [loop, result](QString error) {
                result->finished = true; result->error = error;
                if (loop) loop->quit();
            }, [self, key, snapshot] {
                if (!self) return false;
                try {
                    if (self->current && !self->current()) return false;
                    self->model.selected(self->config, key, snapshot);
                    return true;
                } catch (const Error &) { return false; }
            });
            if (!result->finished) wait.exec(); // Qt input/timers continue; no blocking D-Bus transport.
            if (!self) return false;
            lastError = result->error;
            launched = result->finished && result->error.isEmpty();
        }
    }
    catch (const Error &error) { lastError = QString::fromUtf8(error.what()); QTextStream(stderr) << error.what() << '\n'; }
    report(launched ? "command-launched" : "launch-failed");
    return launched;
}
int Standalone::open(const QString &overrideAnchor) {
    if (presentation.isEmpty() && !model.powerCapabilities()->discoveryPending()) {
        QTextStream(stderr) << "Open Power Menu: No configured commands are available on this system.\n";
        return 1;
    }
    keyboard = false;
    entered = false;
    inside.clear();
    const auto cursor = QCursor::pos();
    auto *screen = QGuiApplication::screenAt(cursor);
    if (!screen)
        screen = QGuiApplication::primaryScreen();
    const auto anchor = overrideAnchor.isEmpty() ? config["anchor"].toString() : overrideAnchor;
    const auto pos = screen ? menuPosition(screen->availableGeometry(), sizeHint(), cursor, anchor) : cursor;
    // Context-bound timers cannot outlive this menu, and are stopped on return.
    QTimer activation, sample, lateSample;
    activation.setSingleShot(true);
    sample.setSingleShot(true);
    lateSample.setSingleShot(true);
    connect(&activation, &QTimer::timeout, this, [this] {
        if (windowHandle()) {
            windowHandle()->installEventFilter(this);
            if (wayland)
                windowHandle()->requestActivate();
        }
        report("show-requested");
    });
    connect(&sample, &QTimer::timeout, this, [this] { report("visibility-sample"); });
    connect(&lateSample, &QTimer::timeout, this, [this] { report("visibility-sample"); });
    activation.start(0);
    sample.start(250);
    lateSample.start(1500);
    auto *selected = exec(pos);
    leaveTimer.stop();
    focusTimer.stop();
    report("dismissed");
    if (!selected)
        return presentation.isEmpty() && !model.powerCapabilities()->discoveryPending() ? 1 : 0;
    if (executeSelection(selected))
        return 0;
    QTextStream(stderr) << "Open Power Menu: Could not launch selection; the application may have become unavailable.\n";
    return 1;
}
} // namespace Opm
