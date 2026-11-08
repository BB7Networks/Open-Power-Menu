#include "standalone.hpp"
#include "storage.hpp"
#include <QApplication>
#include <QFile>
#include <QTemporaryDir>
#include <QTest>
#include <QSignalSpy>
#include <QEnterEvent>
#include <QJsonDocument>
#include <QProcess>
#include <QScreen>
#include <QStyle>
#include <QCursor>
#include <QWindow>
#include <QImage>
#include <QDir>
#include <QIcon>
#include <QScopeGuard>
#include <utility>

using namespace Opm;
static QJsonObject command(const QString &label = "Command", const QJsonArray &args = {"/bin/true"}) {
    return {{"label", label}, {"command", args}};
}
static QJsonObject configuration() {
    auto config = defaults();
    config["menu"] = QJsonArray{command("First"), QJsonObject{{"separator", true}},
        QJsonObject{{"submenu", "Tools"}, {"items", QJsonArray{command("Second"),
            QJsonObject{{"submenu", "Deep"}, {"items", QJsonArray{command("Third")}}}}}},
        command("Unavailable", {"/opm/not-installed"})};
    config["show_unavailable"] = true;
    config["auto_close_on_pointer_leave"] = true;
    return config;
}
static void enter(QWidget *widget) {
    QEnterEvent event(QPointF(2, 2), QPointF(2, 2), QPointF(2, 2));
    QApplication::sendEvent(widget, &event);
}
static void leave(QWidget *widget) {
    QEvent event(QEvent::Leave);
    QApplication::sendEvent(widget, &event);
}
static void moveTo(QMenu *menu, const QPoint &point) {
    if (!QGuiApplication::platformName().startsWith("wayland"))
        QCursor::setPos(menu->mapToGlobal(point));
    QMouseEvent event(QEvent::MouseMove, QPointF(point), QPointF(menu->mapToGlobal(point)),
                      Qt::NoButton, Qt::NoButton, Qt::NoModifier);
    QApplication::sendEvent(menu, &event);
}
static int openWithTimeout(Standalone &menu) {
    QTimer guard;
    guard.setSingleShot(true);
    QObject::connect(&guard, &QTimer::timeout, &menu, &QMenu::close);
    guard.start(5000);
    return menu.open();
}
class StandaloneTest : public QObject {
    Q_OBJECT
  private slots:
    void renderedIconPresets_data() {
        QTest::addColumn<QString>("appearance");
        QTest::newRow("native") << QString("native");
        QTest::newRow("aero") << QString("aero");
    }
    void renderedIconPresets() {
        QFETCH(QString, appearance);
        QTemporaryDir dir;
        QDir().mkpath(dir.filePath("qualification/64x64/apps"));
        QFile index(dir.filePath("qualification/index.theme"));
        QVERIFY(index.open(QIODevice::WriteOnly));
        index.write("[Icon Theme]\nName=Qualification\nDirectories=64x64/apps\n[64x64/apps]\nSize=64\nType=Fixed\nContext=Applications\n"); index.close();
        QImage icon(64, 64, QImage::Format_ARGB32); icon.fill(QColor(255, 0, 0));
        QVERIFY(icon.save(dir.filePath("qualification/64x64/apps/opm-probe.png")));
        const auto paths = QIcon::themeSearchPaths(); const auto theme = QIcon::themeName();
        QIcon::setThemeSearchPaths({dir.path()}); QIcon::setThemeName("qualification");
        const auto reset = qScopeGuard([&] { QIcon::setThemeSearchPaths(paths); QIcon::setThemeName(theme); });
        QList<int> painted;
        for (const auto &size : {"small", "standard", "large"}) {
            auto cfg = configuration(); cfg["appearance"] = appearance; cfg["menu_icon_size"] = size;
            auto item = command("Rendered icon"); item["icon"] = "opm-probe"; item["access_key"] = "R";
            cfg["menu"] = QJsonArray{item}; cfg["show_access_key_hints"] = true;
            for (bool visible : {true, false}) {
                cfg["show_menu_icons"] = visible;
                Standalone menu(cfg); menu.popup(QPoint(20, 20)); QTest::qWait(30);
                auto image = menu.grab().toImage();
                QRect red;
                for (int y = 0; y < image.height(); ++y)
                    for (int x = 0; x < image.width(); ++x) {
                        const auto pixel = image.pixelColor(x, y);
                        if (pixel.red() > 240 && pixel.green() < 15 && pixel.blue() < 15)
                            red = red.united(QRect(x, y, 1, 1));
                    }
                if (visible) {
                    QVERIFY2(!red.isEmpty(), "The configured icon must actually be painted");
                    painted << qRound(red.width() / image.devicePixelRatio());
                    QVERIFY(red.height() <= menu.actionGeometry(menu.actions().first()).height() * image.devicePixelRatio());
                } else QVERIFY(red.isEmpty());
                const auto output = qEnvironmentVariable("OPM_QUALIFICATION_SCREENSHOTS");
                if (!output.isEmpty()) {
                    QDir().mkpath(output);
                    QVERIFY(image.save(output + "/" + QApplication::style()->objectName() + "-" + appearance + "-" + size + (visible ? "-icons.png" : "-hidden.png")));
                }
                menu.close();
            }
        }
        QVERIFY2(painted[0] < painted[1] && painted[1] < painted[2], qPrintable(QString("Painted icon widths: %1, %2, %3").arg(painted[0]).arg(painted[1]).arg(painted[2])));
    }

    void appearancePresets_data() {
        QTest::addColumn<QString>("appearance"); QTest::addColumn<QString>("icons");
        for (const auto &theme : {"native", "aero"})
            for (const auto &size : {"small", "standard", "large"})
                QTest::newRow(qPrintable(QString(theme) + "-" + size)) << QString(theme) << QString(size);
    }
    void appearancePresets() {
        QFETCH(QString, appearance); QFETCH(QString, icons);
        auto cfg = configuration(); cfg["appearance"] = appearance; cfg["menu_icon_size"] = icons;
        QStyle *applicationStyle = QApplication::style();
        QList<int> heights, widths;
        for (const auto &density : {"compact", "standard", "comfortable"}) {
            cfg["menu_density"] = density; Standalone menu(cfg);
            menu.popup(QPoint(10, 10)); QTest::qWait(10);
            heights << menu.actionGeometry(menu.actions().first()).height(); menu.close();
        }
        QVERIFY2(heights[0] < heights[1] && heights[1] < heights[2], qPrintable(QString("heights %1 %2 %3").arg(heights[0]).arg(heights[1]).arg(heights[2])));
        for (const auto &width : {"narrow", "auto", "wide"}) {
            cfg["menu_width"] = width; Standalone menu(cfg);
            menu.popup(QPoint(10, 10)); QTest::qWait(10); widths << menu.width();
            QVERIFY(menu.width() <= menu.screen()->availableGeometry().width()); menu.close();
        }
        QVERIFY2(widths[0] < widths[1] && widths[1] < widths[2], qPrintable(QString("widths %1 %2 %3").arg(widths[0]).arg(widths[1]).arg(widths[2])));
        QCOMPARE(QApplication::style(), applicationStyle);
        cfg["menu_width"] = "wide";
        cfg["menu"] = QJsonArray{command(QString(300, QChar('W')))};
        Standalone longMenu(cfg); auto font = longMenu.font(); font.setPointSizeF(font.pointSizeF() * 1.25); longMenu.setFont(font);
        longMenu.popup(QPoint(10,10)); QTest::qWait(10);
        QVERIFY(longMenu.width() <= longMenu.screen()->availableGeometry().width());
        QVERIFY(longMenu.actionGeometry(longMenu.actions().first()).height() >= longMenu.fontMetrics().height());
        longMenu.close();
    }
    void hoverTimingAndKeyboardOverride_data() {
        QTest::addColumn<int>("delay");
        for (int delay : {-1, 0, 100, 300, 600}) QTest::newRow(qPrintable(QString::number(delay))) << delay;
    }

    void delayedSiblingKeepsOldChildUntilReplacement() {
        auto cfg = configuration(); cfg["submenu_hover_delay_ms"] = 300;
        cfg["menu"] = QJsonArray{
            QJsonObject{{"submenu", "First"}, {"items", QJsonArray{command()}}},
            QJsonObject{{"submenu", "Second"}, {"items", QJsonArray{command()}}}};
        Standalone menu(cfg); menu.popup(QPoint(50, 50)); QTest::qWait(30);
        auto *first = menu.actions()[0]->menu(); auto *second = menu.actions()[1]->menu();
        enter(&menu); menu.setActiveAction(menu.actions()[0]); QTest::keyClick(&menu, Qt::Key_Right);
        QVERIFY(first->isVisible());
        for (int i = 0; i < 10; ++i)
            moveTo(&menu, menu.actionGeometry(menu.actions()[1]).center() + QPoint(i % 2, 0));
        QTest::qWait(40);
        QVERIFY(!second->isVisible());
        QVERIFY(first->isVisible()); // Keep a usable path into the old child.
        QTRY_VERIFY_WITH_TIMEOUT(second->isVisible(), 1200);
        QVERIFY(!first->isVisible());
        menu.close();
    }
    void hoverTimingAndKeyboardOverride() {
        QFETCH(int, delay);
        auto cfg = configuration(); cfg["submenu_hover_delay_ms"] = delay;
        Standalone menu(cfg); auto *child = menu.actions()[2]->menu();
        const int expected = delay < 0 ? QApplication::style()->styleHint(QStyle::SH_Menu_SubMenuPopupDelay) : delay;
        QCOMPARE(menu.style()->styleHint(QStyle::SH_Menu_SubMenuPopupDelay, nullptr, &menu), expected);
        menu.popup(QPoint(40,40)); QTest::qWait(20);
        enter(&menu);
        moveTo(&menu, menu.actionGeometry(menu.actions()[0]).center());
        for (int i = 0; i < 10; ++i)
            moveTo(&menu, menu.actionGeometry(menu.actions()[2]).center() + QPoint(i % 2, 0));
        if (expected > 50) { QTest::qWait(40); QVERIFY(!child->isVisible()); }
        QTRY_VERIFY_WITH_TIMEOUT(child->isVisible(), expected + 600);
        // Reopen through QMenu's lifecycle; manually hiding a submenu bypasses
        // Qt's active-popup/sloppy-pointer cleanup and is not a user transition.
        QTest::keyClick(child, Qt::Key_Escape);
        menu.close(); menu.popup(QPoint(40,40)); QTest::qWait(20); enter(&menu);
        for (int i = 0; i < 10; ++i)
            moveTo(&menu, menu.actionGeometry(menu.actions()[2]).center() + QPoint(i % 2, 0));
        moveTo(&menu, menu.actionGeometry(menu.actions()[0]).center());
        QTest::qWait(expected + 80); QVERIFY(!child->isVisible());
        menu.setActiveAction(menu.actions()[2]); QTest::keyClick(&menu, Qt::Key_Right);
        QVERIFY(child->isVisible()); // explicit activation does not wait
        menu.close(); QTest::qWait(expected + 80); QVERIFY(!child->isVisible());
    }

    void powerOnlyMenuWaitsWithoutBlockingInput() {
        QList<std::pair<QDBusMessage, PowerReply>> requests;
        auto power = cachedPowerManager([&](bool, const QDBusMessage &message, PowerReply done) {
            requests.append({message, std::move(done)});
        }, [] { return 0; });
        auto cfg = configuration(); cfg["show_unavailable"] = false;
        cfg["menu"] = QJsonArray{QJsonObject{{"action", "sleep"}}};
        Standalone menu(cfg, {}, false, power);
        QCOMPARE(menu.actions().size(), 1);
        QVERIFY(!menu.actions().first()->isEnabled());
        QTimer::singleShot(20, &menu, [&] {
            QVERIFY(menu.isVisible()); // event loop and input are available while pending
            for (const auto &request : requests)
                request.second(request.first.createErrorReply("org.test.Unavailable", "No service"));
        });
        QCOMPARE(openWithTimeout(menu), 1);
        QVERIFY(menu.actions().isEmpty());
    }
    void powerRepliesUpdateLiveMenusSafely() {
        struct Request { bool system; QDBusMessage message; PowerReply done; };
        QList<Request> requests;
        auto power = cachedPowerManager([&](bool system, const QDBusMessage &message, PowerReply done) {
            requests.append({system, message, std::move(done)});
        }, [] { return 0; });
        auto cfg = configuration();
        cfg["menu"] = QJsonArray{QJsonObject{{"submenu", "Power"}, {"access_key", "U"},
            {"items", QJsonArray{command("Harmless"), QJsonObject{{"action", "sleep"}}}}}, command("Last")};
        Standalone menu(cfg, {}, false, power);
        auto *child = menu.actions()[0]->menu();
        auto *first = child->actions()[0];
        QVERIFY(!child->actions()[1]->isEnabled());
        QTimer::singleShot(50, &menu, [&] {
            child->popup(menu.mapToGlobal(menu.actionGeometry(menu.actions()[0]).topRight()));
            child->setActiveAction(first);
            const auto round = std::exchange(requests, {});
            for (const auto &request : round)
                request.done(request.message.createReply(request.message.member() == "HasInhibit" ? QVariant(false)
                    : request.system ? QVariant("yes") : QVariant(true)));
            QCOMPARE(menu.actions()[0]->menu(), child);
            QCOMPARE(child->actions()[0], first);
            QCOMPARE(child->activeAction(), first);
            QVERIFY(child->actions()[1]->isEnabled());
            QVERIFY(menu.executeSelection(first)); // harmless action still maps correctly
            menu.close();
        });
        QCOMPARE(openWithTimeout(menu), 0);
        power->invalidate();
        QVERIFY(!child->actions()[1]->isEnabled());
        // No menu receiver remains after destruction while requests are in flight.
        auto *temporary = new Standalone(cfg, {}, false, power);
        delete temporary;
        for (const auto &request : requests)
            request.done(request.message.createErrorReply("org.test.Missing", "Service stopped"));
    }
    void accessKeySequenceUsesNormalSelection() {
        auto cfg = configuration();
        cfg["menu"] = QJsonArray{QJsonObject{{"submenu","Power"},{"access_key","U"},
            {"items",QJsonArray{QJsonObject{{"label","Harmless"},{"access_key","U"},{"command",QJsonArray{"/bin/true"}}}}}}};
        Standalone menu(cfg);
        QSignalSpy spy(&menu,&Standalone::diagnostic);
        QTimer::singleShot(50,&menu,[&]{
            QTest::keyClick(&menu,Qt::Key_U);
            auto *child=menu.actions()[0]->menu();
            QTRY_VERIFY(child->isVisible());
            QTest::keyClick(child,Qt::Key_U);
        });
        QCOMPARE(openWithTimeout(menu),0);
        bool launched=false; for(const auto &event:spy) launched |= event[0].toString()=="command-launched";
        QVERIFY(launched);
    }
    void disabledKeysAndHints() {
        auto cfg=configuration();
        cfg["menu"]=QJsonArray{QJsonObject{{"label","Literal & Label"},{"access_key","X"},{"command",QJsonArray{"/bin/true"}}}};
        Standalone shown(cfg); QVERIFY(shown.actions()[0]->text().endsWith("\tX"));
        cfg["show_access_key_hints"]=false; Standalone hidden(cfg); QVERIFY(!hidden.actions()[0]->text().contains('\t'));
        cfg["access_keys_enabled"]=false; Standalone disabled(cfg);
        QSignalSpy spy(&disabled,&Standalone::diagnostic);
        QTimer::singleShot(50,&disabled,[&]{ QTest::keyClick(&disabled,Qt::Key_X); QVERIFY(disabled.isVisible()); disabled.close(); });
        QCOMPARE(openWithTimeout(disabled),0);
        for(const auto &event:spy) QVERIFY(event[0].toString()!="command-launched");
    }
    void configurableDelayAndReopening() {
        auto cfg=configuration();cfg["auto_close_delay_ms"]=500;
        Standalone menu(cfg);
        for(int cycle=0;cycle<3;++cycle) {
            QTimer::singleShot(20,&menu,[&]{enter(&menu);leave(&menu);QVERIFY(menu.pointerTimerActive());menu.close();});
            QCOMPARE(openWithTimeout(menu),0);QVERIFY(!menu.pointerTimerActive());
        }
        QElapsedTimer elapsed;
        QTimer::singleShot(20,&menu,[&]{enter(&menu);leave(&menu);elapsed.start();});
        QCOMPARE(openWithTimeout(menu),0);
        QVERIFY(elapsed.elapsed()>=450);QVERIFY(elapsed.elapsed()<2500);
    }
    void configurationAndPresentation() {
        Standalone menu(configuration());
        QCOMPARE(menu.actions().size(), 4);
        QVERIFY(menu.actions()[1]->isSeparator());
        auto *child = menu.actions()[2]->menu();
        QVERIFY(child);
        QCOMPARE(child->actions()[1]->menu()->actions()[0]->text(), "Third");
        QVERIFY(!menu.actions()[3]->isEnabled());
        QVERIFY(!menu.executeSelection(menu.actions()[3]));
        QAction forged("Command", &menu);
        forged.setData(QStringList{"/bin/true"});
        QVERIFY(!menu.executeSelection(&forged));
        menu.actions()[0]->setData(QStringList{"/bin/false"});
        QVERIFY(menu.executeSelection(menu.actions()[0])); // data is ignored
        auto cfg = configuration();
        cfg["show_unavailable"] = false;
        Standalone hidden(cfg, "aero");
        QCOMPARE(hidden.actions().size(), 3);
        QVERIFY(!hidden.styleSheet().isEmpty());
    }
    void themedIconsAndVisibility() {
        QTemporaryDir dir;
        QDir().mkpath(dir.path() + "/opm/16x16/actions");
        QFile index(dir.path() + "/opm/index.theme");
        QVERIFY(index.open(QIODevice::WriteOnly));
        index.write("[Icon Theme]\nName=OPM fixture\nDirectories=16x16/actions\n[16x16/actions]\nSize=16\nType=Fixed\nContext=Actions\n");
        index.close();
        QImage image(16, 16, QImage::Format_ARGB32); image.fill(Qt::blue);
        QVERIFY(image.save(dir.path() + "/opm/16x16/actions/system-run.png"));
        const auto paths = QIcon::themeSearchPaths();
        const auto theme = QIcon::themeName();
        QIcon::setThemeSearchPaths({dir.path()}); QIcon::setThemeName("opm");
        auto cfg = configuration();
        Standalone visible(cfg);
        QVERIFY(!visible.actions()[0]->icon().pixmap(16, 16).isNull());
        cfg["show_menu_icons"] = false;
        Standalone hidden(cfg);
        QVERIFY(hidden.actions()[0]->icon().isNull());
        QIcon::setThemeName(theme); QIcon::setThemeSearchPaths(paths);
    }
    void defaultEmptyAndLongMenus() {
        Standalone normal(defaults());
        auto config = configuration();
        config["menu"] = QJsonArray{command("Gone", {"/opm/not-installed"})};
        config["show_unavailable"] = false;
        Standalone empty(config);
        QCOMPARE(openWithTimeout(empty), 1);
        QJsonArray entries;
        for (int i = 0; i < 200; ++i)
            entries.append(command(QString("Command %1").arg(i)));
        config["menu"] = entries;
        Standalone longMenu(config);
        QCOMPARE(longMenu.actions().size(), 200);
        QCOMPARE(longMenu.style()->styleHint(QStyle::SH_Menu_Scrollable, nullptr, &longMenu), 1);
        QTimer::singleShot(100, &longMenu, [&] {
            QVERIFY(longMenu.height() <= QGuiApplication::primaryScreen()->availableGeometry().height());
            QTest::keyClick(&longMenu, Qt::Key_End);
            QCOMPARE(longMenu.activeAction(), longMenu.actions().last());
            QVERIFY(longMenu.rect().contains(longMenu.actionGeometry(longMenu.actions().last()).center()));
            longMenu.close();
        });
        QCOMPARE(openWithTimeout(longMenu), 0);
    }
    void invalidAndReadOnly() {
        QTemporaryDir dir;
        Storage storage(dir.path() + "/config/menu.json");
        { Standalone menu(storage.load()); }
        QVERIFY(!QFile::exists(storage.path()));
        auto config = configuration();
        config["appearance"] = "invalid";
        QVERIFY_EXCEPTION_THROWN(Standalone menu(config), Error);
    }
    void placement_data() {
        QTest::addColumn<QRect>("area");
        QTest::addColumn<QSize>("size");
        QTest::addColumn<QPoint>("cursor");
        QTest::addColumn<QString>("anchor");
        QTest::addColumn<QPoint>("expected");
        QTest::newRow("right-bottom") << QRect(0,0,1000,800) << QSize(300,400) << QPoint(999,799) << "cursor" << QPoint(700,400);
        QTest::newRow("left-top") << QRect(0,0,1000,800) << QSize(300,400) << QPoint(-5,-5) << "cursor" << QPoint(0,0);
        QTest::newRow("secondary-negative") << QRect(-1280,40,1280,984) << QSize(292,400) << QPoint(-50,1000) << "bottom-left" << QPoint(-1272,616);
        QTest::newRow("fractional-logical") << QRect(1536,32,1536,832) << QSize(292,400) << QPoint(1600,100) << "bottom-right" << QPoint(2772,456);
        QTest::newRow("oversize") << QRect(0,20,640,400) << QSize(900,2000) << QPoint(600,300) << "cursor" << QPoint(0,20);
    }
    void placement() {
        QFETCH(QRect, area); QFETCH(QSize, size); QFETCH(QPoint, cursor);
        QFETCH(QString, anchor); QFETCH(QPoint, expected);
        QCOMPARE(menuPosition(area, size, cursor, anchor), expected);
    }
    void pointerTransitionsAndKeyboard() {
        Standalone menu(configuration());
        menu.show();
        enter(&menu);
        leave(&menu);
        QVERIFY(menu.pointerTimerActive());
        QTest::qWait(200);
        enter(&menu);
        QVERIFY(!menu.pointerTimerActive());
        auto *child = menu.actions()[2]->menu();
        child->popup(menu.mapToGlobal(QPoint(menu.width(), 0)));
        leave(&menu);
        enter(child);
        QVERIFY(!menu.pointerTimerActive());
        QTest::qWait(1250);
        QVERIFY(menu.isVisible());
        leave(child);
        QVERIFY(menu.pointerTimerActive());
        QTest::keyClick(child, Qt::Key_Down);
        QVERIFY(menu.keyboardNavigation());
        QVERIFY(!menu.pointerTimerActive());
        QTest::qWait(1250);
        QVERIFY(menu.isVisible());
        // A genuine mouse event resumes pointer mode, including outside.
        QMouseEvent move(QEvent::MouseMove, QPointF(2,2), QPointF(2,2), Qt::NoButton, Qt::NoButton, Qt::NoModifier);
        QApplication::sendEvent(child, &move);
        QVERIFY(!menu.keyboardNavigation());
        QTRY_VERIFY_WITH_TIMEOUT(!menu.isVisible(), 1800);
        QVERIFY(!menu.pointerTimerActive());
    }
    void disabledPreferenceAndDestruction() {
        auto cfg = configuration();
        cfg["auto_close_on_pointer_leave"] = false;
        Standalone menu(cfg);
        menu.show(); enter(&menu); leave(&menu);
        QVERIFY(!menu.pointerTimerActive());
        auto *temporary = new Standalone(configuration());
        temporary->show(); enter(temporary); leave(temporary);
        QVERIFY(temporary->pointerTimerActive());
        delete temporary;
        QTest::qWait(1250); // no stale callback
    }
    void keyboardSelectionAndCancellation() {
        Standalone menu(configuration());
        QSignalSpy trace(&menu, &Standalone::diagnostic);
        QTimer::singleShot(50, &menu, [&] {
            QTest::keyClick(&menu, Qt::Key_Down);
            QCOMPARE(menu.activeAction(), menu.actions()[0]);
            QTest::keyClick(&menu, Qt::Key_Down);
            QCOMPARE(menu.activeAction(), menu.actions()[2]);
            QTest::keyClick(&menu, Qt::Key_Right);
            auto *child = menu.actions()[2]->menu();
            QTRY_VERIFY(child->isVisible());
            QTest::keyClick(child, Qt::Key_Down);
            QTest::keyClick(child, Qt::Key_Right);
            auto *deep = child->actions()[1]->menu();
            QTRY_VERIFY(deep->isVisible());
            QTest::keyClick(deep, Qt::Key_Return);
        });
        QCOMPARE(openWithTimeout(menu), 0);
        QVERIFY(trace.contains(QList<QVariant>{QString("command-launched")}));
        for (int i = 0; i < 5; ++i) {
            QTimer::singleShot(20, &menu, [&] { QTest::keyClick(&menu, Qt::Key_Escape); });
            QCOMPARE(openWithTimeout(menu), 0);
            QVERIFY(!menu.isVisible());
            QVERIFY(!menu.pointerTimerActive());
        }
    }
    void mouseSelection() {
        Standalone menu(configuration());
        QSignalSpy trace(&menu, &Standalone::diagnostic);
        QTimer::singleShot(50, &menu, [&] {
            const auto point = menu.actionGeometry(menu.actions()[0]).center();
            enter(&menu);
            // QMenu suppresses initial popup clicks until pointer movement.
            for (int i = 0; i < 10; ++i)
                moveTo(&menu, point + QPoint(i % 2, 0));
            QTest::qWait(20);
            QTest::mouseClick(&menu, Qt::LeftButton, Qt::NoModifier, point);
        });
        QCOMPARE(openWithTimeout(menu), 0);
        QVERIFY(trace.contains(QList<QVariant>{QString("command-launched")}));
    }
    void hoverAndAdaptivePlacement_data() {
        QTest::addColumn<bool>("rightEdge");
        QTest::newRow("left-edge") << false;
        QTest::newRow("right-edge") << true;
    }
    void hoverAndAdaptivePlacement() {
        QFETCH(bool, rightEdge);
        Standalone menu(configuration());
        const auto area = QGuiApplication::primaryScreen()->availableGeometry();
        QTimer::singleShot(100, &menu, [&] {
            auto *action = menu.actions()[2];
            enter(&menu);
            const auto hover = menu.actionGeometry(action).center();
            // QWidget QTest::mouseMove only warps the cursor; Wayland forbids
            // that. Deliver genuine Qt mouse-move events for portable testing.
            for (int i = 0; i < 10; ++i)
                moveTo(&menu, hover + QPoint(i % 2, 0));
            auto *child = action->menu();
            QTRY_VERIFY_WITH_TIMEOUT(child->isVisible(), 1500);
            // Qt decides popup direction; assert the visible flyout stays on screen.
            if (!QGuiApplication::platformName().startsWith("wayland")) {
                QVERIFY(area.contains(child->frameGeometry().center()));
                QVERIFY(child->frameGeometry().right() <= area.right() + 2);
            }
            for (int i = 0; i < 10; ++i) {
                moveTo(&menu, menu.actionGeometry(menu.actions()[0]).center());
                moveTo(&menu, menu.actionGeometry(action).center());
            }
            menu.close();
        });
        // Move the cursor before opening; native geometry uses that screen.
        if (!QGuiApplication::platformName().startsWith("wayland"))
            QCursor::setPos(rightEdge ? area.bottomRight() - QPoint(2, 2) : area.topLeft() + QPoint(2, 2));
        QCOMPARE(openWithTimeout(menu), 0);
    }
    void appearanceCapture_data() {
        QTest::addColumn<QString>("theme");
        QTest::newRow("native") << "native";
        QTest::newRow("aero") << "aero";
        QTest::newRow("native-dark") << "native-dark";
    }
    void appearanceCapture() {
        QFETCH(QString, theme);
        const auto palette = qApp->palette();
        if (theme == "native-dark") {
            auto dark = palette;
            dark.setColor(QPalette::Window, QColor("#242a31"));
            dark.setColor(QPalette::Base, QColor("#242a31"));
            dark.setColor(QPalette::Button, QColor("#242a31"));
            dark.setColor(QPalette::AlternateBase, QColor("#303840"));
            dark.setColor(QPalette::Light, QColor("#455463"));
            dark.setColor(QPalette::Midlight, QColor("#303840"));
            dark.setColor(QPalette::Mid, QColor("#1a1e23"));
            dark.setColor(QPalette::Dark, QColor("#121518"));
            dark.setColor(QPalette::Shadow, QColor("#080a0c"));
            dark.setColor(QPalette::ButtonText, QColor("#e4ebf2"));
            dark.setColor(QPalette::WindowText, QColor("#e4ebf2"));
            dark.setColor(QPalette::Text, QColor("#e4ebf2"));
            dark.setColor(QPalette::Disabled, QPalette::WindowText, QColor("#89939c"));
            dark.setColor(QPalette::Disabled, QPalette::Text, QColor("#89939c"));
            qApp->setPalette(dark);
        }
        Standalone menu(configuration(), theme == "native-dark" ? "native" : theme);
        QTimer::singleShot(100, &menu, [&] {
            menu.setActiveAction(menu.actions()[0]);
            const auto directory = qEnvironmentVariable("OPM_CAPTURE_DIR");
            if (!directory.isEmpty())
                QVERIFY(menu.grab().save(directory + "/standalone-" + theme + ".png"));
            menu.close();
        });
        QCOMPARE(openWithTimeout(menu), 0);
        qApp->setPalette(palette);
    }
    void applicationFocusLoss() {
        if (!QGuiApplication::platformName().startsWith("wayland") ||
            qEnvironmentVariable("OPM_WAYLAND_COMPOSITOR") != "kwin")
            QSKIP("Cross-process activation requires the KWin virtual seat; Weston headless has no input seat");
        Standalone menu(configuration());
        QSignalSpy trace(&menu, &Standalone::diagnostic);
        QProcess peer;
        QTimer::singleShot(100, &menu, [&] {
            QTRY_COMPARE_WITH_TIMEOUT(QGuiApplication::applicationState(), Qt::ApplicationActive, 2000);
            peer.start(QCoreApplication::applicationFilePath(), {"--focus-peer"});
            QVERIFY(peer.waitForStarted());
        });
        QCOMPARE(openWithTimeout(menu), 0);
        peer.terminate(); peer.waitForFinished(2000);
        QVERIFY(trace.contains(QList<QVariant>{QString("focus-dismissed")}));
    }
    void changedAvailabilityFailsClosed() {
        QTemporaryDir dir;
        QString program = dir.path() + "/temporary program";
        QFile file(program);
        QVERIFY(file.open(QIODevice::WriteOnly));
        file.write("#!/bin/sh\nexit 0\n"); file.close();
        QVERIFY(file.setPermissions(QFile::ReadOwner | QFile::WriteOwner | QFile::ExeOwner));
        auto cfg = configuration();
        cfg["show_unavailable"] = false;
        cfg["menu"] = QJsonArray{command("Temporary", {program}), command("Survivor")};
        Standalone menu(cfg);
        QVERIFY(file.remove());
        QVERIFY(!menu.executeSelection(menu.actions()[0])); // never runs Survivor
    }
    void literalArgumentsDetachedAndFailure() {
        QTemporaryDir dir;
        const auto output = dir.path() + "/result file";
        const auto script = dir.path() + "/application with spaces";
        QFile file(script);
        QVERIFY(file.open(QIODevice::WriteOnly));
        // This shell is the explicitly configured application, not an implicit launcher.
        file.write("#!/bin/sh\nsleep 0.3\nprintf '%s\\n' \"$2\" \"$3\" > \"$1\"\n"); file.close();
        QVERIFY(file.setPermissions(QFile::ReadOwner | QFile::WriteOwner | QFile::ExeOwner));
        auto cfg = configuration();
        cfg["menu"] = QJsonArray{command("Literal", {script, output, "$(touch SHOULD_NOT_EXIST)", "a b; * ' \""})};
        const auto configFile = dir.path() + "/menu.json";
        QFile saved(configFile); QVERIFY(saved.open(QIODevice::WriteOnly));
        saved.write(QJsonDocument(cfg).toJson()); saved.close();
        QProcess launcher;
        launcher.start(QCoreApplication::applicationFilePath(), {"--execute-child", configFile});
        QVERIFY(launcher.waitForFinished(5000));
        QCOMPARE(launcher.exitCode(), 0);
        // The complete launching process has exited before the delayed application writes.
        QTRY_VERIFY_WITH_TIMEOUT(QFile::exists(output), 2000);
        QFile result(output); QVERIFY(result.open(QIODevice::ReadOnly));
        QCOMPARE(result.readAll(), QByteArray("$(touch SHOULD_NOT_EXIST)\na b; * ' \"\n"));
        QVERIFY(!QFile::exists("SHOULD_NOT_EXIST"));
        QFile broken(script); QVERIFY(broken.open(QIODevice::WriteOnly | QIODevice::Truncate));
        broken.write("#!/missing/interpreter\n"); broken.close();
        Standalone failed(cfg);
        QVERIFY(!failed.executeSelection(failed.actions()[0]));
    }
};
int main(int argc, char **argv) {
    QApplication app(argc, argv);
    if (app.arguments().contains("--focus-peer")) {
        QWidget window;
        window.setWindowTitle("OPM disposable focus peer");
        window.resize(300, 200);
        window.show();
        QTimer::singleShot(50, &window, [&] { window.windowHandle()->requestActivate(); });
        QTimer::singleShot(4000, &app, &QCoreApplication::quit);
        return app.exec();
    }
    if (app.arguments().size() == 3 && app.arguments()[1] == "--execute-child") {
        Standalone menu(Storage(app.arguments()[2]).load());
        return menu.executeSelection(menu.actions().first()) ? 0 : 1;
    }
    StandaloneTest test;
    return QTest::qExec(&test, argc, argv);
}
#include "standalone_test.moc"
