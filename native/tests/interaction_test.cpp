#include "interaction.hpp"
#include "editor_session.hpp"
#include "power.hpp"
#include "service.hpp"
#include <QFile>
#include <QProcess>
#include <QDBusVirtualObject>
#include <QDBusPendingCallWatcher>
#include <QDBusConnectionInterface>
#include <QScopeGuard>
#include <QJsonDocument>
#include <QTemporaryDir>
#include <QtTest>
#include <algorithm>
#include <utility>
using namespace Opm;
class RefusingPower : public QDBusVirtualObject {
  public:
    int delay = 0, activations = 0;
    QString introspect(const QString &) const override { return {}; }
    bool handleMessage(const QDBusMessage &request, const QDBusConnection &bus) override {
        const auto method = request.member();
        if (method.endsWith("WithFlags")) {
            ++activations;
            QTimer::singleShot(2200, this, [request, bus] {
                bus.send(request.createErrorReply("org.test.Cancelled", "Simulated authorization cancellation"));
            });
        } else if (method == "CanSuspend" || method == "CanHibernate" || method == "HasInhibit") {
            const auto value = method == "HasInhibit" ? QVariant(false) :
                request.interface().endsWith(".Manager") ? QVariant("challenge") : QVariant(true);
            QTimer::singleShot(delay, this, [request, bus, value] { bus.send(request.createReply(value)); });
        } else bus.send(request.createErrorReply("org.test.Refused", "Fixture refuses all other requests"));
        return true;
    }
};
class InteractionTests : public QObject {
    Q_OBJECT
  private slots:
    void appearanceAndHoverValidation() {
        const auto legacy = decode(QByteArray(R"({"menu":[{"action":"files"}],"future":true})"));
        QCOMPARE(submenuHoverDelay(legacy), -1);
        QCOMPARE(legacy["menu_density"].toString(), "standard");
        QCOMPARE(legacy["menu_width"].toString(), "auto");
        QCOMPARE(legacy["menu_icon_size"].toString(), "standard");
        for (int delay : {-1, 0, 100, 200, 300, 400, 500, 600}) {
            auto cfg = legacy; cfg["submenu_hover_delay_ms"] = delay;
            validate(cfg); QCOMPARE(submenuHoverDelay(cfg), delay);
            QCOMPARE(integration(cfg)["submenu_hover_delay_ms"].toInt(), delay);
        }
        for (const auto value : {QJsonValue(-2), QJsonValue(1), QJsonValue(150), QJsonValue(601), QJsonValue(100.5), QJsonValue("100"), QJsonValue(true)}) {
            auto cfg = legacy; cfg["submenu_hover_delay_ms"] = value;
            QVERIFY_EXCEPTION_THROWN(validate(cfg), Error);
        }
        for (const auto &key : {"menu_density", "menu_width", "menu_icon_size"}) {
            auto cfg = legacy; cfg[key] = "invalid";
            QVERIFY_EXCEPTION_THROWN(validate(cfg), Error);
            cfg[key] = false; QVERIFY_EXCEPTION_THROWN(validate(cfg), Error);
        }
    }
    void migrateWithoutReplacingLayout() {
        const auto cfg = decode(QByteArray(R"({"auto_close_on_pointer_leave":false,"menu":[{"action":"files","label":"My files","icon":"custom"},{"action":"terminal"},{"action":"terminal"},{"label":"Custom","command":["true"],"access_key":"e"}]})"));
        const auto menu = cfg["menu"].toArray();
        QCOMPARE(menu.size(), 4);
        QVERIFY(!menu[0].toObject().contains("access_key")); // explicitly reserved
        QVERIFY(!menu[1].toObject().contains("access_key")); // duplicate preset
        QCOMPARE(menu[0].toObject()["label"].toString(), "My files");
        QCOMPARE(pointerLeaveDelay(cfg), 1200);
        QVERIFY(!cfg["auto_close_on_pointer_leave"].toBool());
        QCOMPARE(decode(QJsonDocument(cfg).toJson()), cfg);
    }
    void defaultsAndScopes() {
        const auto cfg = defaults();
        validate(cfg);
        const auto root = cfg["menu"].toArray();
        QCOMPARE(root.first().toObject()["access_key"].toString(), "P");
        const auto power = root[root.size()-2].toObject();
        QCOMPARE(power["access_key"].toString(), "U");
        QHash<QString,QString> expected{{"lock","L"},{"logout","I"},{"reboot","R"},{"shutdown","U"},{"sleep","S"},{"hibernate","H"}};
        for (const auto &v : power["items"].toArray()) {
            const auto item = v.toObject();
            QCOMPARE(item["access_key"].toString(), expected[item["action"].toString()]);
        }
        auto custom = cfg;
        custom["menu"] = QJsonArray{QJsonObject{{"submenu","Level"},{"access_key","X"},{"items",QJsonArray{QJsonObject{{"command",QJsonArray{"true"}},{"access_key","x"}}}}}};
        validate(custom);
        auto items = custom["menu"].toArray(); items.append(items.first()); custom["menu"] = items;
        QVERIFY_EXCEPTION_THROWN(validate(custom), Error);
    }
    void delay_data() {
        QTest::addColumn<int>("value"); QTest::addColumn<bool>("valid");
        for (int value : {0,499,500,600,1200,4900,5000,5001,5050,99999})
            QTest::newRow(qPrintable(QString::number(value))) << value << (value>=500 && value<=5000 && value%100==0);
    }
    void delay() {
        QFETCH(int,value); QFETCH(bool,valid);
        auto cfg = defaults(); cfg["auto_close_delay_ms"] = value;
        if (valid) { validate(cfg); QCOMPARE(pointerLeaveDelay(cfg),value); }
        else QVERIFY_EXCEPTION_THROWN(validate(cfg), Error);
    }
    void presentationEnableHintsAndUnavailable() {
        Model model;
        auto cfg=defaults(); cfg["show_unavailable"]=true;
        cfg["menu"] = QJsonArray{QJsonObject{{"label","Test"},{"command",QJsonArray{"/bin/true"}},{"access_key","x"}},QJsonObject{{"command",QJsonArray{"opm-not-installed"}},{"access_key","Y"}}};
        auto menu=model.publicMenu(cfg);
        QCOMPARE(menu[0].toObject()["access_key"].toString(),"X");
        QCOMPARE(menu[0].toObject()["access_hint"].toString(),"X");
        QVERIFY(!model.execute(cfg,"1",&menu));
        cfg["show_access_key_hints"]=false;
        menu=model.publicMenu(cfg);
        QVERIFY(menu[0].toObject().contains("access_key"));
        QVERIFY(!menu[0].toObject().contains("access_hint"));
        cfg["access_keys_enabled"]=false; menu=model.publicMenu(cfg);
        QVERIFY(!menu[0].toObject().contains("access_key"));
        QVERIFY(!menu[0].toObject().contains("access_hint"));
    }
    void editorRoundtripUndoAndCollision() {
        QTemporaryDir tmp; Storage storage(tmp.filePath("menu.json"));
        auto cfg=defaults(); cfg["menu"]=QJsonArray{QJsonObject{{"action","files"},{"access_key","Z"},{"future",123}},QJsonObject{{"action","terminal"},{"access_key","I"}}};
        storage.save(cfg,{}); EditorSession editor(storage);
        auto rows=QJsonDocument::fromJson(editor.layoutJson().toUtf8()).object()["entries"].toArray();
        const auto id=rows[0].toObject()["id"].toString();
        QVERIFY(!editor.editItem(id,R"({"access_key":"i"})"));
        QCOMPARE(editor.errorCode(),"access-key-collision");
        QVERIFY(editor.editItem(id,R"({"label":"Renamed","icon":"computer"})"));
        QCOMPARE(editor.configuration()["menu"].toArray()[0].toObject()["access_key"].toString(),"Z");
        QVERIFY(editor.resetAccessKeys());
        QCOMPARE(editor.configuration()["menu"].toArray()[0].toObject()["access_key"].toString(),"E");
        editor.undo(); QCOMPARE(editor.configuration()["menu"].toArray()[0].toObject()["access_key"].toString(),"Z");
        editor.redo(); QVERIFY(editor.preference(R"({"auto_close_delay_ms":5000,"access_keys_enabled":false})"));
        QVERIFY(editor.save());
        const auto loaded=storage.load(); QCOMPARE(loaded,editor.configuration());
        QCOMPARE(loaded["menu"].toArray()[0].toObject()["future"].toInt(),123);
    }
  private:
    struct PendingPower {
        bool system;
        QDBusMessage request;
        PowerReply reply;
    };
    static void answer(QList<PendingPower> requests, bool allowed = true) {
        // Deliberately reverse arrival order.
        std::reverse(requests.begin(), requests.end());
        for (auto &call : requests)
            call.reply(call.request.createReply(call.request.member() == "HasInhibit" ? QVariant(false)
                : call.system ? QVariant(allowed ? "yes" : "no") : QVariant(allowed)));
    }
  private slots:
    void privateBusActivationAndClientDisappearance() {
        QTemporaryDir dir;
        QProcess daemon;
        daemon.start("dbus-daemon", {"--session", "--nofork", "--print-address=1"});
        QVERIFY(daemon.waitForReadyRead(3000));
        const auto address = QString::fromUtf8(daemon.readLine()).trimmed();
        QVERIFY(address.startsWith("unix:"));
        auto fixtureBus = QDBusConnection::connectToBus(address, "opm-fixture");
        RefusingPower fixture;
        QVERIFY(fixtureBus.registerService("org.freedesktop.PowerManagement"));
        QVERIFY(fixtureBus.registerService("org.freedesktop.login1"));
        for (const auto &path : {"/org/freedesktop/PowerManagement", "/org/freedesktop/PowerManagement/Inhibit", "/org/freedesktop/login1"})
            QVERIFY(fixtureBus.registerVirtualObject(path, &fixture));
        Storage storage(dir.filePath("menu.json"));
        auto cfg = defaults(); cfg["show_unavailable"] = true;
        cfg["menu"] = QJsonArray{QJsonObject{{"action", "sleep"}}};
        storage.save(cfg, storage.revision());
        QProcess backend;
        auto env = QProcessEnvironment::systemEnvironment();
        env.insert("DBUS_SESSION_BUS_ADDRESS", address); env.insert("DBUS_SYSTEM_BUS_ADDRESS", address);
        backend.setProcessEnvironment(env);
        backend.start(QCoreApplication::applicationDirPath() + "/open-power-menu-native", {"--service", "--config", storage.path()});
        QVERIFY(backend.waitForStarted());
        auto a = QDBusConnection::connectToBus(address, "opm-client-a");
        auto b = QDBusConnection::connectToBus(address, "opm-client-b");
        const auto cleanup = qScopeGuard([&] {
            backend.terminate(); backend.waitForFinished();
            for (const auto &name : {"opm-client-a", "opm-client-b", "opm-client-c", "opm-fixture"}) QDBusConnection::disconnectFromBus(name);
            daemon.terminate(); daemon.waitForFinished();
        });
        QTRY_VERIFY(a.interface()->isServiceRegistered("org.openpowermenu.NativePreview").value());
        auto call = [&](const QDBusConnection &bus, const QString &method, const QStringList &args = {}) {
            auto request = QDBusMessage::createMethodCall("org.openpowermenu.NativePreview", "/OpenPowerMenu", "org.openpowermenu.Service", method);
            QList<QVariant> values; for (const auto &arg : args) values.append(arg); request.setArguments(values);
            QDBusPendingCallWatcher watcher(bus.asyncCall(request, 5000));
            QEventLoop wait;
            connect(&watcher, &QDBusPendingCallWatcher::finished, &wait, &QEventLoop::quit);
            if (!watcher.isFinished()) wait.exec();
            return watcher.reply().arguments().value(0).toString();
        };
        auto menu = [&](const QDBusConnection &bus) { return QJsonDocument::fromJson(call(bus, "GetMenu").toUtf8()).array(); };
        QTRY_VERIFY(menu(a)[0].toObject()["enabled"].toBool());
        const auto key = menu(a)[0].toObject()["key"].toString();
        const auto started = QJsonDocument::fromJson(call(a, "StartRun", {key}).toUtf8()).object();
        QCOMPARE(started["state"].toString(), "pending");
        const auto id = started["operation"].toString();
        QTRY_COMPARE(fixture.activations, 1);
        QElapsedTimer timer; timer.start();
        QVERIFY(call(b, "Ping").startsWith("Open Power Menu"));
        QVERIFY(!menu(b).isEmpty()); QVERIFY(!call(b, "GetIntegration").isEmpty());
        qInfo() << "Private D-Bus Ping/GetMenu/GetIntegration during 2200ms authorization, ms:" << timer.elapsed();
        QVERIFY(timer.elapsed() < 1000);
        const auto foreign = QJsonDocument::fromJson(call(b, "RunResult", {id}).toUtf8()).object();
        QVERIFY(!foreign["ok"].toBool()); QVERIFY(foreign["error"].toString().contains("another client"));
        const auto duplicate = QJsonDocument::fromJson(call(b, "StartRun", {menu(b)[0].toObject()["key"].toString()}).toUtf8()).object();
        QVERIFY(!duplicate["ok"].toBool()); QCOMPARE(fixture.activations, 1);
        QTRY_VERIFY_WITH_TIMEOUT(call(a, "RunResult", {id}).contains("Simulated authorization cancellation"), 4000);
        // A client disappearing during fresh checks must not dispatch later.
        fixture.delay = 150;
        {
            auto c = QDBusConnection::connectToBus(address, "opm-client-c");
            auto token = menu(c)[0].toObject()["key"].toString();
            QVERIFY(call(c, "StartRun", {token}).contains("pending"));
        }
        QDBusConnection::disconnectFromBus("opm-client-c");
        QTest::qWait(600);
        QCOMPARE(fixture.activations, 1);
        QVERIFY(call(a, "Ping").startsWith("Open Power Menu"));
    }
    void presentationExpiryReplayAndRestart() {
        QTemporaryDir dir; Storage storage(dir.filePath("menu.json"));
        auto cfg = defaults(); cfg["menu"] = QJsonArray{QJsonObject{{"command", QJsonArray{"/bin/true"}}}};
        storage.save(cfg, storage.revision());
        qint64 now = 0;
        Service service(storage, nullptr, powerManager(), [&] { return now; });
        auto key = [&](Service &source) { return QJsonDocument::fromJson(source.GetMenu().toUtf8()).array()[0].toObject()["key"].toString(); };
        const auto valid = key(service);
        QVERIFY(service.Run(valid)); QVERIFY(!service.Run(valid));
        const auto expired = key(service); now = 120001;
        QVERIFY(!service.Run(expired));
        const auto old = key(service);
        Service restarted(storage); QVERIFY(!restarted.Run(old));
        for (const auto &bad : {QString("0"), QString("/0"), QString(200, 'x'), old + ".99999"}) QVERIFY(!service.Run(bad));
        // Bounded retention expires the oldest presentation safely.
        const auto evicted = key(service);
        for (int i = 0; i < 17; ++i) { ++now; key(service); }
        QVERIFY(!service.Run(evicted));
    }
    void asyncActivationLifecycle() {
        for (const auto &scenario : {"success", "denial", "cancel", "inhibit", "missing", "owner", "client", "timeout", "late", "malformed"}) {
            QList<PendingPower> requests;
            auto manager = cachedPowerManager([&](bool system, const QDBusMessage &request, PowerReply done) {
                requests.append({system, request, std::move(done)});
            }, [] { return 0; }, {}, 60, 60);
            int completions = 0; QString result; bool alive = true;
            manager->executeAsync("sleep", [&](QString error) { ++completions; result = error; }, [&] { return alive; });
            QCOMPARE(requests.size(), 1); QCOMPARE(requests[0].request.member(), "CanSuspend");
            QString duplicate;
            manager->executeAsync("hibernate", [&](QString error) { duplicate = error; });
            QVERIFY(!duplicate.isEmpty()); QCOMPARE(requests.size(), 1);
            if (QString(scenario) == "missing") {
                requests.takeFirst().reply(QDBusMessage::createError("org.freedesktop.DBus.Error.ServiceUnknown", "missing"));
            } else if (QString(scenario) == "owner") {
                manager->invalidate(); answer(std::exchange(requests, {}));
            } else if (QString(scenario) == "timeout") {
                QTRY_COMPARE_WITH_TIMEOUT(completions, 1, 500); answer(std::exchange(requests, {}));
            } else {
                auto first = requests.takeFirst();
                if (QString(scenario) == "client") alive = false;
                first.reply(first.request.createReply(QVariant(true)));
                if (alive) {
                    QCOMPARE(requests.size(), 1); QCOMPARE(requests[0].request.member(), "HasInhibit");
                    auto inhibitor = requests.takeFirst();
                    inhibitor.reply(inhibitor.request.createReply(QVariant(QString(scenario) == "inhibit")));
                    if (QString(scenario) != "inhibit") {
                        auto permission = requests.takeFirst();
                        QCOMPARE(permission.request.member(), "CanSuspend");
                        permission.reply(permission.request.createReply(QVariant(QString(scenario) == "denial" ? "no" : "challenge")));
                        if (QString(scenario) != "denial") {
                            QCOMPARE(requests.size(), 1);
                            auto authorization = requests.takeFirst();
                            QCOMPARE(authorization.request.member(), "SuspendWithFlags");
                            QVERIFY(authorization.system); QVERIFY(authorization.request.isInteractiveAuthorizationAllowed());
                            QCOMPARE(authorization.request.arguments().first().toULongLong(), qulonglong(1));
                            QCOMPARE(completions, 0);
                            if (QString(scenario) == "late") {
                                QTRY_COMPARE_WITH_TIMEOUT(completions, 1, 500);
                                authorization.reply(authorization.request.createReply());
                                QVERIFY(manager->executionPending()); // uncertain operation cannot be overlapped/retried
                            } else if (QString(scenario) == "cancel") authorization.reply(authorization.request.createErrorReply("org.test.Cancelled", "authentication cancelled"));
                            else if (QString(scenario) == "malformed") authorization.reply(authorization.request.createReply(QVariant(true)));
                            else authorization.reply(authorization.request.createReply());
                        }
                    }
                }
            }
            QCOMPARE(completions, 1);
            QCOMPARE(result.isEmpty(), QString(scenario) == "success");
            QVERIFY(requests.isEmpty());
        }
    }
    void serviceResponsiveDuringAuthorization() {
        QTemporaryDir dir; Storage storage(dir.filePath("menu.json"));
        auto cfg = defaults(); cfg["menu"] = QJsonArray{QJsonObject{{"action", "sleep"}}};
        storage.save(cfg, storage.revision());
        int dispatched = 0;
        auto manager = cachedPowerManager([&](bool system, const QDBusMessage &request, PowerReply done) {
            if (request.member().endsWith("WithFlags")) {
                ++dispatched;
                QTimer::singleShot(2200, this, [done, request] { done(request.createErrorReply("org.test.Denied", "delayed refusal")); });
            } else QTimer::singleShot(10, this, [done, request, system] {
                done(request.createReply(request.member() == "HasInhibit" ? QVariant(false) : system ? QVariant("challenge") : QVariant(true)));
            });
        }, [] { return 0; });
        Service service(storage, nullptr, manager);
        service.GetMenu(); QTRY_VERIFY(!manager->discoveryPending());
        const auto key = QJsonDocument::fromJson(service.GetMenu().toUtf8()).array()[0].toObject()["key"].toString();
        const auto started = QJsonDocument::fromJson(service.StartRun(key).toUtf8()).object();
        QCOMPARE(started["state"].toString(), "pending"); QVERIFY(!started.contains("ok"));
        const auto id = started["operation"].toString();
        QTRY_COMPARE(dispatched, 1);
        QElapsedTimer timer; timer.start();
        for (int i = 0; i < 100; ++i) { QVERIFY(!service.Ping().isEmpty()); QVERIFY(!service.GetMenu().isEmpty()); QVERIFY(!service.GetIntegration().isEmpty()); }
        qInfo() << "100 Ping/GetMenu/GetIntegration sets during authorization, ms:" << timer.elapsed();
        QVERIFY(timer.elapsed() < 1000);
        QVERIFY(manager->executionPending());
        QTRY_COMPARE_WITH_TIMEOUT(QJsonDocument::fromJson(service.RunResult(id).toUtf8()).object()["state"].toString(), "finished", 4000);
        const auto result = QJsonDocument::fromJson(service.RunResult(id).toUtf8()).object();
        QVERIFY(!result["ok"].toBool()); QVERIFY(result["error"].toString().contains("delayed refusal"));
        QCOMPARE(dispatched, 1);
    }
    void asynchronousPowerCacheAndRecovery() {
        qint64 now = 0;
        QList<PendingPower> requests;
        auto manager = cachedPowerManager([&](bool system, const QDBusMessage &request, PowerReply done) {
            requests.append({system, request, std::move(done)});
        }, [&] { return now; });
        QVERIFY(!manager->capability("sleep").available);
        QVERIFY(manager->discoveryPending());
        QCOMPARE(requests.size(), 5);
        for (int i = 0; i < 100; ++i) QVERIFY(!manager->capability("hibernate").available);
        QCOMPARE(requests.size(), 5); // one shared, coalesced generation
        answer(std::exchange(requests, {}));
        QVERIFY(manager->capability("sleep").available);
        QVERIFY(manager->capability("hibernate").available);
        now = 4999; QVERIFY(manager->capability("sleep").available);
        QVERIFY(requests.isEmpty());
        now = 5000; QVERIFY(!manager->capability("sleep").available); // stale fails closed
        QCOMPARE(requests.size(), 5);
        const auto stale = std::exchange(requests, {});
        manager->invalidate();
        QVERIFY(!manager->capability("sleep").available);
        QCOMPARE(requests.size(), 5);
        answer(stale); // late success cannot grant permission in the new epoch
        QVERIFY(!manager->capability("sleep").available);
        answer(std::exchange(requests, {}), false);
        QVERIFY(!manager->capability("hibernate").available);
        manager->invalidate(); // service recovery
        QVERIFY(!manager->capability("sleep").available);
        answer(std::exchange(requests, {}));
        QVERIFY(manager->capability("sleep").available);
        manager.reset();
        answer(stale); // no callbacks into a destroyed owner
    }
    void asynchronousPowerTimeoutAndMalformedReply() {
        QList<PendingPower> requests;
        auto manager = cachedPowerManager([&](bool system, const QDBusMessage &request, PowerReply done) {
            requests.append({system, request, std::move(done)});
        }, [] { return 0; });
        QVERIFY(!manager->capability("sleep").available);
        QSignalSpy changed(manager.get(), &PowerManager::changed);
        QTRY_COMPARE_WITH_TIMEOUT(changed.size(), 1, 2500);
        QVERIFY(!manager->discoveryPending());
        QVERIFY(manager->capability("sleep").reason.contains("timed out"));
        answer(std::exchange(requests, {})); // ignore replies after deadline
        QVERIFY(!manager->capability("sleep").available);
        manager->invalidate();
        QVERIFY(!manager->capability("sleep").available);
        for (auto &call : requests) call.reply(call.request.createReply(QVariant(1)));
        QVERIFY(!manager->capability("sleep").available); // integer is not a bool/string
        requests.clear();
        manager->invalidate();
        QVERIFY(!manager->capability("sleep").available);
        for (auto &call : requests)
            call.reply(call.request.createErrorReply("org.test.Failure", "Service failed"));
        QVERIFY(manager->capability("hibernate").reason.contains("org.test.Failure"));
    }
    void asynchronousPowerNeverDispatchesCachedPermission() {
        QList<PendingPower> requests;
        int dispatches = 0;
        auto manager = cachedPowerManager([&](bool system, const QDBusMessage &request, PowerReply done) {
            requests.append({system, request, std::move(done)});
        }, [] { return 0; }, [&](bool, const QDBusMessage &request) {
            if (request.member().endsWith("WithFlags")) ++dispatches;
            return request.createErrorReply("org.test.Denied", "Fresh check failed");
        });
        manager->capability("sleep"); answer(requests);
        QVERIFY(manager->capability("sleep").available);
        QVERIFY_EXCEPTION_THROWN(manager->execute("sleep"), Error);
        QCOMPARE(dispatches, 0);
    }
    void powerPolicy_data() {
        QTest::addColumn<QString>("permission"); QTest::addColumn<bool>("inhibited"); QTest::addColumn<bool>("supported"); QTest::addColumn<bool>("expected");
        QTest::newRow("yes")<<QString("yes")<<false<<true<<true;
        QTest::newRow("polkit")<<QString("challenge")<<false<<true<<true;
        QTest::newRow("denied")<<QString("no")<<false<<true<<false;
        QTest::newRow("unsupported")<<QString("na")<<false<<true<<false;
        QTest::newRow("kde-inhibited")<<QString("yes")<<true<<true<<false;
        QTest::newRow("kde-unavailable")<<QString("yes")<<false<<false<<false;
    }
    void powerPolicy() {
        QFETCH(QString,permission); QFETCH(bool,inhibited); QFETCH(bool,supported); QFETCH(bool,expected);
        QStringList operations;
        auto manager=powerManager([&](bool system,const QDBusMessage &request) {
            if (request.member().endsWith("WithFlags")) {
                if (!request.isInteractiveAuthorizationAllowed()) qFatal("Missing Polkit flag");
                if (!system || request.arguments().first().toULongLong()!=1) qFatal("Unsafe power request");
                operations<<request.member(); return request.createReply();
            }
            if (request.member()=="HasInhibit") return request.createReply(QVariant(inhibited));
            return request.createReply(system ? QVariant(permission) : QVariant(supported));
        });
        for(const auto &action : {QString("sleep"),QString("hibernate")}) {
            QCOMPARE(manager->capability(action).available,expected);
            if(expected) manager->execute(action);
            else QVERIFY_EXCEPTION_THROWN(manager->execute(action),Error);
        }
        QCOMPARE(operations.size(),expected?2:0);
    }
    void powerRechecksAndReportsErrors() {
        bool available=true; int activated=0;
        auto manager=powerManager([&](bool system,const QDBusMessage &request) {
            if(request.member().endsWith("WithFlags")) { ++activated; return request.createErrorReply("org.freedesktop.login1.OperationInhibited","Another app is preventing sleep"); }
            if(request.member()=="HasInhibit") return request.createReply(QVariant(!available));
            return request.createReply(system?QVariant("yes"):QVariant(true));
        });
        Model model(manager); auto cfg=defaults(); cfg["show_unavailable"]=true;
        cfg["menu"]=QJsonArray{QJsonObject{{"action","sleep"},{"access_key","S"}}};
        auto shown=model.publicMenu(cfg); QVERIFY(shown[0].toObject()["enabled"].toBool());
        available=false; QVERIFY(!model.execute(cfg,"0",&shown)); QCOMPARE(activated,0);
        available=true; QVERIFY_EXCEPTION_THROWN(model.execute(cfg,"0",&shown),Error); QCOMPARE(activated,1);
        QVERIFY(model.command(cfg,"0").isEmpty()); // no shell fallback
    }
};
QTEST_GUILESS_MAIN(InteractionTests)
#include "interaction_test.moc"
