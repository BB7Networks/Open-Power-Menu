#include "service.hpp"
#include "editor_session.hpp"
#include <QCoreApplication>
#include <QFile>
#include <QJsonDocument>
#include <QProcess>
#include <QSettings>
#include <QTemporaryDir>
#include <QtTest>
using namespace Opm;

// Every request, including system-bus policy reads, is injected. No host power
// service is contacted by this executable.
struct Recorder {
    QList<QDBusMessage> reads, finals;
    QString permission = "yes", failure;
    bool hold = false, malformed = false;
    PowerReply pending;
    std::shared_ptr<PowerManager> manager(int timeout = 1500) {
        return cachedPowerManager([this](bool system, const QDBusMessage &m, PowerReply done) {
            if (m.service() == "org.kde.Shutdown" || m.service() == "org.kde.LogoutPrompt") {
                if (system || !m.arguments().isEmpty()) qFatal("Unsafe session request");
                finals.append(m);
                if (hold) { pending = std::move(done); return; }
                done(!failure.isEmpty() ? m.createErrorReply(failure, "simulated refusal") :
                     malformed ? m.createReply(true) : m.createReply());
            } else {
                reads.append(m);
                if (m.member() == "ListNames") done(m.createReply(QStringList{"org.kde.Shutdown", "org.kde.LogoutPrompt"}));
                else if (m.member() == "ListActivatableNames") done(m.createReply(QStringList{}));
                else if (m.member() == "CanPowerOff" || m.member() == "CanReboot") {
                    if (!system) qFatal("Policy read on wrong bus");
                    done(m.createReply(permission));
                } else qFatal("Unexpected request in session fixture");
            }
        }, [] { return 0; }, {}, timeout);
    }
};
static QJsonObject configuration(const QString &action, bool confirm) {
    auto cfg = defaults(); cfg["confirm_power_actions"] = confirm;
    cfg["menu"] = QJsonArray{QJsonObject{{"action", action}, {"access_key", "Z"}}};
    return cfg;
}
static QString selection(Service &service) {
    return QJsonDocument::fromJson(service.GetMenu().toUtf8()).array().first().toObject()["key"].toString();
}
static QJsonObject result(const QString &json) { return QJsonDocument::fromJson(json.toUtf8()).object(); }

class SessionPowerTests : public QObject {
    Q_OBJECT
  private slots:
    void exactDispatch_data() {
        QTest::addColumn<QString>("action"); QTest::addColumn<bool>("confirm"); QTest::addColumn<bool>("kdeConfirm");
        for (const auto &action : {"shutdown", "reboot", "logout"}) for (bool confirm : {false, true}) for (bool kde : {false, true})
            QTest::newRow(qPrintable(QString("%1-opm%2-kde%3").arg(action).arg(confirm).arg(kde))) << QString(action) << confirm << kde;
    }
    void exactDispatch() {
        QFETCH(QString, action); QFETCH(bool, confirm); QFETCH(bool, kdeConfirm);
        QTemporaryDir dir; Storage store(dir.filePath("menu.json"));
        QSettings kde(dir.filePath("ksmserverrc"), QSettings::IniFormat);
        kde.setValue("General/confirmLogout", kdeConfirm); kde.sync();
        const auto oldConfig = qgetenv("XDG_CONFIG_HOME"); qputenv("XDG_CONFIG_HOME", QFile::encodeName(dir.path()));
        const auto restore = qScopeGuard([&] { qputenv("XDG_CONFIG_HOME", oldConfig); });
        store.save(configuration(action, confirm), {});
        Recorder record; auto manager = record.manager(); Service service(store, nullptr, manager);
        const auto key = selection(service);
        QVERIFY(!key.isEmpty()); QVERIFY(record.finals.isEmpty());
        for (const auto &read : record.reads) QVERIFY(!read.autoStartService());
        const auto outcome = result(service.StartRun(key));
        QVERIFY2(outcome["ok"].toBool(), qPrintable(outcome["error"].toString()));
        QCOMPARE(outcome["state"].toString(), "finished");
        QCOMPARE(record.finals.size(), 1);
        const auto request = record.finals.first();
        QCOMPARE(request.service(), confirm ? "org.kde.LogoutPrompt" : "org.kde.Shutdown");
        QCOMPARE(request.path(), confirm ? "/LogoutPrompt" : "/Shutdown");
        QCOMPARE(request.interface(), request.service());
        const QString expected = action == "shutdown" ? (confirm ? "promptShutDown" : "logoutAndShutdown") :
            action == "reboot" ? (confirm ? "promptReboot" : "logoutAndReboot") : (confirm ? "promptLogout" : "logout");
        QCOMPARE(request.member(), expected); QVERIFY(request.arguments().isEmpty());
        QVERIFY(!result(service.StartRun(key))["ok"].toBool()); // Same protected presentation is consumed.
        QCOMPARE(record.finals.size(), 1);
        QCOMPARE(kde.value("General/confirmLogout").toBool(), kdeConfirm);
    }
    void preferenceMigrationLabelsAndStaleIdentity() {
        const auto cfg = decode(QByteArray(R"({"menu":[{"action":"shutdown","access_key":"Z","extra":123},{"label":"My command...","command":["true"],"access_key":""}],"future":{"keep":true}})"));
        QVERIFY(!cfg["confirm_power_actions"].toBool());
        QCOMPARE(integration(cfg)["confirm_power_actions"], QJsonValue(false));
        for (auto bad : {QJsonValue(0), QJsonValue("false"), QJsonValue(), QJsonValue(QJsonArray{})}) {
            auto invalid = cfg; invalid["confirm_power_actions"] = bad;
            QVERIFY_EXCEPTION_THROWN(validate(invalid), Error);
        }
        Recorder record; Model model(record.manager());
        const auto immediate = model.capture(cfg);
        QCOMPARE(immediate.menu[0].toObject()["title"].toString(), "Shut down");
        auto confirmed = cfg; confirmed["confirm_power_actions"] = true;
        QCOMPARE(model.publicMenu(confirmed)[0].toObject()["title"].toString(), "Shut down...");
        QVERIFY_EXCEPTION_THROWN(model.selected(confirmed, "0", immediate), Error);
        auto custom = cfg; auto rows = custom["menu"].toArray(); auto row = rows[0].toObject();
        row["label"] = "Custom title..."; rows[0] = row; custom["menu"] = rows;
        const auto shown = model.capture(custom); custom["confirm_power_actions"] = true;
        QCOMPARE(model.publicMenu(custom)[0].toObject()["title"].toString(), "Custom title...");
        QVERIFY_EXCEPTION_THROWN(model.selected(custom, "0", shown), Error); // Equal labels cannot hide changed meaning.
        QVERIFY(record.finals.isEmpty());
        QTemporaryDir dir; Storage store(dir.filePath("menu.json")); store.save(cfg, {});
        Service service(store, nullptr, record.manager()); const auto key = selection(service);
        store.save(confirmed, store.revision());
        QVERIFY(result(service.StartRun(key))["error"].toString().contains("Configuration changed"));
        QVERIFY(record.finals.isEmpty());
    }
    void preferenceEditorRoundTrip() {
        QTemporaryDir dir; Storage store(dir.filePath("menu.json"));
        const auto cfg = decode(QByteArray(R"({"menu":[{"action":"logout","label":"Leave...","access_key":"Z","extra":123}],"future":42})"));
        store.save(cfg, {}); EditorSession editor(store);
        QVERIFY(editor.preference(R"({"confirm_power_actions":true})")); QVERIFY(editor.save());
        QCOMPARE(store.load()["menu"], cfg["menu"]); QCOMPARE(store.load()["future"], cfg["future"]);
        EditorSession reopened(store); QVERIFY(reopened.configuration()["confirm_power_actions"].toBool());
        const auto file = QUrl::fromLocalFile(dir.filePath("export.json"));
        QVERIFY(reopened.exportConfiguration(file));
        QVERIFY(reopened.preference(R"({"confirm_power_actions":false})")); QVERIFY(reopened.save());
        QVERIFY(!reopened.previewImport(file).isEmpty()); QVERIFY(reopened.applyImport());
        QVERIFY(reopened.configuration()["confirm_power_actions"].toBool());
        QVERIFY(reopened.resetLayout()); QVERIFY(reopened.configuration()["confirm_power_actions"].toBool());
        reopened.undo(); // Layout-only reset preserves General preferences.
        QVERIFY(reopened.preference(R"({"confirm_power_actions":false})")); QVERIFY(reopened.save());
        QCOMPARE(store.load()["menu"], cfg["menu"]); QVERIFY(!store.load()["confirm_power_actions"].toBool());
        QVERIFY(!store.backups().isEmpty());
    }
    void failuresAndUncertainReplies_data() {
        QTest::addColumn<QString>("failure"); QTest::addColumn<bool>("uncertain");
        QTest::newRow("denied") << QString("org.freedesktop.DBus.Error.AccessDenied") << false;
        QTest::newRow("lost-reply") << QString("org.freedesktop.DBus.Error.NoReply") << true;
        QTest::newRow("malformed") << QString("malformed") << true;
        QTest::newRow("timeout") << QString("timeout") << true;
    }
    void failuresAndUncertainReplies() {
        QFETCH(QString, failure); QFETCH(bool, uncertain);
        Recorder record; record.hold = failure == "timeout"; record.malformed = failure == "malformed";
        if (!record.hold && !record.malformed) record.failure = failure;
        auto manager = record.manager(20); QString error; bool complete = false;
        manager->executeAsync("shutdown", [&](QString value) { error = value; complete = true; });
        QTRY_VERIFY(complete); QVERIFY(!error.isEmpty()); QCOMPARE(record.finals.size(), 1);
        QCOMPARE(manager->executionPending(), uncertain);
        if (uncertain) {
            manager->executeAsync("logout", [](QString value) { QVERIFY(!value.isEmpty()); });
            QCOMPARE(record.finals.size(), 1);
        }
        if (record.pending) { record.pending(record.finals[0].createReply()); QVERIFY(!error.isEmpty()); }
    }
    void acceptedRequestSurvivesMenuCloseAndConfigChange() {
        QTemporaryDir dir; Storage store(dir.filePath("menu.json")); store.save(configuration("logout", false), {});
        Recorder record; record.hold = true; Service service(store, nullptr, record.manager());
        const auto key = selection(service); const auto started = result(service.StartRun(key));
        QCOMPARE(started["state"].toString(), "pending"); QCOMPARE(record.finals.size(), 1);
        // There is no close-menu cancellation API. Reopening/refreshing and
        // editing after dispatch cannot cancel or repeat the accepted request.
        service.GetMenu(); store.save(configuration("logout", true), store.revision());
        QVERIFY(!result(service.StartRun(key))["ok"].toBool());
        record.pending(record.finals[0].createReply());
        QVERIFY(result(service.RunResult(started["operation"].toString()))["ok"].toBool());
        QCOMPARE(record.finals.size(), 1);
    }
    void policyDenialAndStaleCheckNeverDispatch() {
        Recorder record; record.permission = "no"; auto manager = record.manager();
        QVERIFY(!manager->capability("shutdown").available);
        manager->executeAsync("shutdown", [](QString e) { QVERIFY(!e.isEmpty()); });
        QVERIFY(record.finals.isEmpty());
        record.permission = "yes";
        manager->executeAsync("shutdown", [](QString e) { QVERIFY(!e.isEmpty()); }, [] { return false; });
        QVERIFY(record.finals.isEmpty());
    }
    void kioskRestrictions() {
        for (const auto &key : {"logout", "action/logout"}) {
            QTemporaryDir dir; QFile file(dir.filePath("kdeglobals")); QVERIFY(file.open(QIODevice::WriteOnly));
            file.write(QByteArray("[KDE Action Restrictions]\n") + key + "=false\n"); file.close();
            QProcess p; auto env = QProcessEnvironment::systemEnvironment(); env.insert("XDG_CONFIG_HOME", dir.path());
            p.setProcessEnvironment(env); p.start(QCoreApplication::applicationFilePath(), {"--kiosk-probe"});
            QVERIFY(p.waitForFinished(5000)); QCOMPARE(p.exitCode(), 0);
        }
    }
};
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    if (app.arguments().contains("--kiosk-probe")) {
        Recorder record; auto manager = record.manager(); bool refused = false;
        const bool available = manager->capability("logout").available;
        manager->executeAsync("logout", [&](QString error) { refused = !error.isEmpty(); });
        return !available && refused && record.finals.isEmpty() ? 0 : 1;
    }
    SessionPowerTests tests; return QTest::qExec(&tests, argc, argv);
}
#include "session_power_test.moc"
