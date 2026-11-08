#include "interaction.hpp"
#include "editor_session.hpp"
#include "power.hpp"
#include <QJsonDocument>
#include <QTemporaryDir>
#include <QtTest>
#include <algorithm>
#include <utility>
using namespace Opm;
class InteractionTests : public QObject {
    Q_OBJECT
  private slots:
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
