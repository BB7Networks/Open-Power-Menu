#include "safe_fs.hpp"
#include <QCoreApplication>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusInterface>
#include <QDBusReply>
#include <QElapsedTimer>
#include <QFileInfo>
#include <QLibraryInfo>
#include <QPluginLoader>
#include <QProcess>
#include <QProcessEnvironment>
#include <QRegularExpression>
#include <QSysInfo>
#include <QTemporaryDir>
#include <QTextStream>
#include <QThread>
#include <QUuid>
#include <signal.h>
#include <sys/file.h>
#include <sys/syscall.h>
#include <vector>
using namespace Opm;
using namespace Opm::Install;
static const QString busName = "org.openpowermenu.Service";
static QString xdg(const char *key, const QString &fallback) {
    return qEnvironmentVariable(key, fallback);
}
static QString dataRoot() {
    return xdg("XDG_DATA_HOME", QDir::homePath() + "/.local/share");
}
static QString configRoot() {
    return xdg("XDG_CONFIG_HOME", QDir::homePath() + "/.config");
}
static QString binRoot() {
    return xdg("XDG_BIN_HOME", QDir::homePath() + "/.local/bin");
}
static QString execQuoted(QString p, bool desktop = false) {
    if (p.contains('\n') || p.contains('\r') || p.contains('\t'))
        throw Error("Control characters in install path");
    if (desktop)
        p.replace('%', "%%");
    p.replace('\\', "\\\\");
    p.replace('"', "\\\"");
    p.replace('`', "\\`");
    p.replace('$', "\\$");
    p = '"' + p + '"';
    if (desktop)
        p.replace('\\', "\\\\");
    return p;
}
static void run(const QString &exe, const QStringList &args, bool gui = false) {
    QProcess p;
    auto env = QProcessEnvironment::systemEnvironment();
    if (gui) {
        env.insert("QT_QPA_PLATFORM", "offscreen");
        env.insert("QT_QUICK_BACKEND", "software");
    }
    p.setProcessEnvironment(env);
    p.start(exe, args);
    if (!p.waitForFinished(20000)) {
        p.kill();
        p.waitForFinished();
        throw Error("Runtime validation timed out: " + exe);
    }
    if (p.exitStatus() != QProcess::NormalExit || p.exitCode() != 0)
        throw Error("Runtime validation failed: " + exe + "\n" +
                    QString::fromUtf8(p.readAllStandardError()));
}
static QString call(const QString &method) {
    QDBusInterface remote(busName, "/OpenPowerMenu", busName, QDBusConnection::sessionBus());
    remote.setTimeout(5000);
    QDBusReply<QString> reply = remote.call(method);
    if (!reply.isValid())
        throw Error("D-Bus " + method + ": " + reply.error().message());
    return reply.value();
}
static void verifyService(bool native = true) {
    const auto ping = call("Ping");
    if (native && ping != "Open Power Menu v" OPM_NATIVE_VERSION)
        throw Error("Wrong activated service version");
    if (!native && !ping.startsWith("Open Power Menu v"))
        throw Error("Unexpected service");
    // Invalid personal config must remain recoverable; the service's disabled
    // error row is a valid response. Never rewrite config just to pass installation.
    if (!QJsonDocument::fromJson(call("GetMenu").toUtf8()).isArray() ||
        !QJsonDocument::fromJson(call("GetIntegration").toUtf8()).isObject())
        throw Error("Invalid service protocol");
}
static void reload() {
    auto *bus = QDBusConnection::sessionBus().interface();
    if (!bus)
        throw Error("A session D-Bus is required");
    QDBusReply<void> r = bus->call("ReloadConfig");
    if (!r.isValid())
        throw Error(r.error().message());
}
static void activate(bool native = true) {
    QDBusConnection::sessionBus().interface()->setTimeout(5000);
    QDBusReply<uint> r =
        QDBusConnection::sessionBus().interface()->call("StartServiceByName", busName, uint(0));
    if (!r.isValid())
        throw Error("D-Bus activation failed: " + r.error().message());
    verifyService(native);
}
// Read /proc only after obtaining the owner from the bus. pidfd prevents PID reuse.
static Fd serviceOwner(const QString &appPath) {
    auto *bus = QDBusConnection::sessionBus().interface();
    if (!bus || !QDBusConnection::sessionBus().isConnected())
        throw Error("A session D-Bus is required");
    QDBusReply<bool> registered = bus->isServiceRegistered(busName);
    if (!registered.isValid())
        throw Error("Cannot inspect service owner");
    if (!registered.value())
        return Fd();
    auto pid = bus->servicePid(busName);
    auto uid = bus->serviceUid(busName);
    if (!pid.isValid() || !uid.isValid() || uid.value() != getuid() || pid.value() < 2)
        throw Error("Unrelated service owner; left running");
    Fd handle(syscall(SYS_pidfd_open, pid.value(), 0));
    need(handle >= 0, "Open service pidfd (Linux 5.3+ required)");
    QFile f(QString("/proc/%1/cmdline").arg(pid.value()));
    need(f.open(QIODevice::ReadOnly), "Read service arguments");
    auto args = f.readAll().split('\0');
    const auto exe = QFileInfo(QString("/proc/%1/exe").arg(pid.value())).symLinkTarget();
    bool native = exe == appPath + "/bin/open-power-menu-native" && args.contains("--service");
    bool legacy = (QFileInfo(exe).fileName().startsWith("python3")) &&
                  args.contains(QFile::encodeName(appPath + "/run.py")) &&
                  args.contains("--service");
    if (!native && !legacy)
        throw Error("Unrelated D-Bus owner; refusing to signal it");
    return handle;
}
static void retire(const QString &appPath) {
    auto handle = serviceOwner(appPath);
    if (handle < 0)
        return;
    need(syscall(SYS_pidfd_send_signal, int(handle), SIGTERM, nullptr, 0) == 0,
         "Stop identified OPM service");
    QElapsedTimer wait;
    wait.start();
    while (QDBusConnection::sessionBus().interface()->isServiceRegistered(busName).value()) {
        if (wait.elapsed() > 5000)
            throw Error("OPM owner did not release D-Bus; no force kill attempted");
        QThread::msleep(25);
    }
}
struct Component {
    QString parentPath, leaf;
    Fd parent;
    Component(QString p, QString n)
        : parentPath(std::move(p)), leaf(std::move(n)), parent(directory(parentPath, true)) {}
};
static std::vector<Component> components() {
    std::vector<Component> v;
    v.emplace_back(dataRoot(), "open-power-menu");
    v.emplace_back(dataRoot() + "/plasma/plasmoids", "org.openpowermenu.start");
    v.emplace_back(binRoot(), "open-power-menu");
    v.emplace_back(dataRoot() + "/applications", "org.openpowermenu.desktop");
    v.emplace_back(dataRoot() + "/icons/hicolor/scalable/apps", "open-power-menu.svg");
    v.emplace_back(dataRoot() + "/dbus-1/services", "org.openpowermenu.Service.service");
    v.emplace_back(dataRoot() + "/applications", "org.openpowermenu.configure.desktop");
    return v;
}
static QJsonObject current(std::vector<Component> &cs) {
    QJsonObject o;
    for (size_t i = 0; i < cs.size(); ++i)
        o[QString::number(i)] = digest(cs[i].parent, cs[i].leaf);
    return o;
}
static QString sibling(const QString &id, int i, const QString &suffix) {
    return ".opm-" + id + '-' + QString::number(i) + '-' + suffix;
}
static void identity(std::vector<Component> &cs, int recovery) {
    if (exists(recovery, "receipt.json")) {
        if (json(recovery, "receipt.json")["files"].toObject() != current(cs))
            throw Error("Installed components changed; preserve them and resolve the conflict "
                        "before replacing/removing");
        return;
    }
    bool any = false;
    for (auto &c : cs)
        any |= exists(c.parent, c.leaf);
    if (!any)
        return;
    if (!exists(cs[0].parent, cs[0].leaf))
        throw Error("Unowned installation collision");
    auto app = child(cs[0].parent, cs[0].leaf);
    auto module = child(app, "openpowermenu");
    if (!read(module, "__init__.py").contains("__version__ = \"1.0.1\"") ||
        !read(app, "run.py").contains("openpowermenu.cli"))
        throw Error("Only identified 1.0.1 or receipted native installs can be upgraded");
    if (exists(cs[1].parent, cs[1].leaf)) {
        auto widget = child(cs[1].parent, cs[1].leaf);
        if (json(widget, "metadata.json")["KPlugin"].toObject()["Id"] != "org.openpowermenu.start")
            throw Error("Unrelated widget collision");
    }
    if (exists(cs[2].parent, cs[2].leaf)) {
        auto wrapper = read(cs[2].parent, cs[2].leaf);
        if (!wrapper.contains("exec python3 \"$appdir/run.py\" \"$@\"") ||
            !wrapper.contains("/open-power-menu"))
            throw Error("Unrelated launcher collision");
    }
    for (int i : {3, 4, 5, 6})
        if (exists(cs[i].parent, cs[i].leaf)) {
            auto bytes = read(cs[i].parent, cs[i].leaf);
            if ((i == 3 && (!bytes.contains("Name=Open Power Menu\n") ||
                            !bytes.contains("Icon=open-power-menu") ||
                            !bytes.contains(
                                ("Exec=" + execQuoted(binRoot() + "/open-power-menu", true) + "\n")
                                    .toUtf8()))) ||
                (i == 4 && bytes != QByteArray::fromBase64(OPM_ICON_BASE64)) ||
                (i == 5 &&
                 (!bytes.contains("Name=org.openpowermenu.Service\n") ||
                  !bytes.contains(QFile::encodeName(binRoot() + "/open-power-menu --service")))) ||
                i == 6)
                throw Error("Unrelated integration file collision");
        }
    current(cs); // validate the entire legacy tree before copying it
}
static void snapshot(int tx, std::vector<Component> &cs, QJsonObject &journal) {
    mkdir(tx, "old");
    auto old = child(tx, "old");
    for (size_t i = 0; i < cs.size(); ++i)
        if (exists(cs[i].parent, cs[i].leaf))
            copy(cs[i].parent, cs[i].leaf, old, QString::number(i));
    journal["old"] = current(cs);
    for (size_t i = 0; i < cs.size(); ++i)
        if (digest(old, QString::number(i)) !=
            journal["old"].toObject()[QString::number(i)].toString())
            throw Error("Installed component changed while taking its snapshot");
}
static void restore(int tx, std::vector<Component> &cs, const QJsonObject &j) {
    const auto id = j["id"].toString();
    const auto oldHashes = j["old"].toObject(), newHashes = j["new"].toObject();
    auto old = child(tx, "old");
    // Refuse a modified snapshot or an unexpected live component before any recovery write.
    for (size_t i = 0; i < cs.size(); ++i) {
        auto key = QString::number(i);
        auto now = digest(cs[i].parent, cs[i].leaf);
        if (digest(old, key) != oldHashes[key].toString())
            throw Error("Rollback snapshot changed");
        if (!now.isEmpty() && now != oldHashes[key].toString() && now != newHashes[key].toString())
            throw Error("Live component changed during transaction; retained recovery journal");
        auto saved = sibling(id, i, "old");
        if (exists(cs[i].parent, saved) && digest(cs[i].parent, saved) != oldHashes[key].toString())
            throw Error("Displaced component changed");
    }
    for (size_t i = 0; i < cs.size(); ++i) {
        auto key = QString::number(i);
        auto &c = cs[i];
        auto incoming = sibling(id, i, "new");
        auto saved = sibling(id, i, "old");
        remove(c.parent, incoming);
        if (digest(c.parent, c.leaf) != oldHashes[key].toString()) {
            remove(c.parent, c.leaf);
            if (exists(old, key)) {
                copy(old, key, c.parent, incoming);
                move(c.parent, incoming, c.parent, c.leaf);
            }
        }
        remove(c.parent, saved);
    }
}
static void cleanStaging(std::vector<Component> &cs, const QJsonObject &j) {
    const auto id = j["id"].toString();
    for (size_t i = 0; i < cs.size(); ++i)
        for (const auto &suffix : {"old", "new"}) {
            const auto path = sibling(id, i, suffix);
            if (exists(cs[i].parent, path) &&
                digest(cs[i].parent, path) != j[suffix].toObject()[QString::number(i)].toString())
                throw Error("Staged component changed; retained recovery journal");
        }
    for (size_t i = 0; i < cs.size(); ++i)
        for (const auto &suffix : {"old", "new"})
            remove(cs[i].parent, sibling(id, i, suffix));
}
static void checkId(const QString &id) {
    if (!QRegularExpression("^[0-9a-f]{32}$").match(id).hasMatch())
        throw Error("Invalid transaction ID");
}
static int probe(const QString &backend) {
    QTemporaryDir profile;
    QProcess p;
    p.start(backend,
            {"--service", "--bus-name", busName, "--config", profile.path() + "/menu.json"});
    try {
        QElapsedTimer t;
        t.start();
        while (!QDBusConnection::sessionBus().interface()->isServiceRegistered(busName).value()) {
            if (t.elapsed() > 5000)
                throw Error("Private service failed to start");
            QThread::msleep(20);
        }
        verifyService();
        p.terminate();
        p.waitForFinished(5000);
        return 0;
    } catch (...) {
        p.kill();
        p.waitForFinished();
        throw;
    }
}
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    auto args = app.arguments();
    try {
        if (args.size() == 3 && args[1] == "--probe-service")
            return probe(args[2]);
        if (args.size() == 3 && args[1] == "--seal-bundle") {
            auto root = directory(args[2]);
            QJsonObject files;
            inventory(root, files);
            write(root, "bundle.json",
                  QJsonDocument(QJsonObject{{"format", 1},
                                            {"version", OPM_NATIVE_VERSION},
                                            {"os", QSysInfo::productType()},
                                            {"os_version", QSysInfo::productVersion()},
                                            {"cpu", QSysInfo::currentCpuArchitecture()},
                                            {"files", files}})
                      .toJson());
            return 0;
        }
        if (getuid() == 0)
            throw Error("Run as your desktop user without sudo");
        const bool install = args.size() == 3 && args[1] == "--install";
        if (!install && !(args.size() == 2 &&
                          QStringList{"--uninstall", "--rollback", "--recover"}.contains(args[1])))
            throw Error("Usage: open-power-menu-install --install BUNDLE | --uninstall | "
                        "--rollback | --recover");
        auto cs = components();
        const auto appPath = dataRoot() + "/open-power-menu";
        auto recovery = directory(dataRoot() + "/open-power-menu-recovery/native-installs", true);
        Fd lock(openat(recovery, "lock", O_RDWR | O_CREAT | O_NOFOLLOW | O_CLOEXEC, 0600));
        need(lock >= 0, "Open install lock");
        struct stat ls{};
        need(fstat(lock, &ls) == 0, "Inspect lock");
        inspect(ls);
        need(flock(lock, LOCK_EX | LOCK_NB) == 0, "Another installation is active");
        if (exists(recovery, "active.json")) {
            auto active = json(recovery, "active.json");
            auto id = active["id"].toString();
            checkId(id);
            auto tx = child(recovery, id);
            auto j = json(tx, "journal.json");
            if (j["id"].toString() != id || j["old"].toObject().size() != int(cs.size()) ||
                j["new"].toObject().size() != int(cs.size()))
                throw Error("Invalid transaction journal");
            if (j["roots"].toArray() != QJsonArray{dataRoot(), binRoot(), configRoot()})
                throw Error("Recovery requires the original XDG roots");
            if (j["committed"].toBool())
                cleanStaging(cs, j);
            else {
                retire(appPath);
                restore(tx, cs, j);
                if (j["receipt"].isObject())
                    replaceJson(recovery, "receipt.json", j["receipt"].toObject());
                else
                    remove(recovery, "receipt.json");
                reload();
                if (j["wasRunning"].toBool() && exists(cs[5].parent, cs[5].leaf))
                    activate(false);
            }
            remove(recovery, "active.json");
            QTextStream(stdout) << "Recovered interrupted transaction " << id << '\n';
        }
        if (args[1] == "--recover")
            return 0;
        identity(cs, recovery);
        auto owner = serviceOwner(appPath); // refuse unrelated owner before preparing a transaction
        QJsonObject previousReceipt;
        if (exists(recovery, "receipt.json"))
            previousReceipt = json(recovery, "receipt.json");
        const auto id = QUuid::createUuid().toString(QUuid::Id128);
        mkdir(recovery, id);
        auto tx = child(recovery, id);
        QJsonObject j{{"id", id},
                      {"roots", QJsonArray{dataRoot(), binRoot(), configRoot()}},
                      {"committed", false},
                      {"wasRunning", owner >= 0}};
        if (!previousReceipt.isEmpty())
            j["receipt"] = previousReceipt;
        snapshot(tx, cs, j);
        mkdir(tx, "new");
        auto staged = child(tx, "new");
        if (install) {
            auto bundle = directory(args[2], false, true);
            auto spec = parseJson(read(bundle, "bundle.json", true), true).object();
            QJsonObject files;
            inventory(bundle, files, {}, true);
            files.remove("bundle.json");
            if (spec["format"] != 1 || spec["version"] != OPM_NATIVE_VERSION ||
                spec["files"].toObject() != files)
                throw Error("Invalid/corrupt native bundle");
            if (spec["os"] != QSysInfo::productType() ||
                spec["os_version"] != QSysInfo::productVersion() ||
                spec["cpu"] != QSysInfo::currentCpuArchitecture())
                throw Error(
                    "Bundle distribution/version/architecture mismatch; use a matching build");
            copy(bundle, "app", staged, "0", true);
            copy(bundle, "widget", staged, "1", true);
            auto packageApp = child(bundle, "app", true);
            auto binaries = child(packageApp, "bin", true);
            copy(binaries, "open-power-menu", staged, "2", true);
            copy(bundle, "open-power-menu.svg", staged, "4", true);
            // Validate the private copy before executing it: the source can change
            // between its initial inventory and these copies.
            QJsonObject stagedFiles, expectedFiles;
            inventory(staged, stagedFiles);
            for (auto it = files.begin(); it != files.end(); ++it) {
                if (it.key().startsWith("app/"))
                    expectedFiles["0/" + it.key().mid(4)] = it.value();
                else if (it.key().startsWith("widget/"))
                    expectedFiles["1/" + it.key().mid(7)] = it.value();
            }
            expectedFiles["2"] = files["app/bin/open-power-menu"];
            expectedFiles["4"] = files["open-power-menu.svg"];
            if (stagedFiles != expectedFiles)
                throw Error("Bundle changed while staging");
            QString wrapper = execQuoted(binRoot() + "/open-power-menu", true);
            auto desktop = [&](QString title, QString options) {
                return QString(
                           "[Desktop "
                           "Entry]\nType=Application\nName=%1\nExec=%2%3\nIcon=open-power-"
                           "menu\nTerminal=false\nCategories=System;Utility;\nStartupNotify=true\n")
                    .arg(title, wrapper, options)
                    .toUtf8();
            };
            write(staged, "3", desktop("Open Power Menu", {}));
            write(staged, "6", desktop("Configure Open Power Menu", " --edit"));
            write(staged, "5",
                  QString("[D-BUS Service]\nName=%1\nExec=%2 --service --bus-name %1\n")
                      .arg(busName, execQuoted(appPath + "/bin/open-power-menu-native"))
                      .toUtf8());
            const auto stagedBin =
                dataRoot() + "/open-power-menu-recovery/native-installs/" + id + "/new/0/bin/";
            for (const auto &n : {"open-power-menu-native", "open-power-menu-standalone"})
                run(stagedBin + n, {"--version"});
            for (const auto &platform : {"libqxcb.so", "libqwayland-generic.so"}) {
                QPluginLoader plugin(QLibraryInfo::path(QLibraryInfo::PluginsPath) + "/platforms/" +
                                     platform);
                if (!plugin.load())
                    throw Error("Required Qt platform plugin unavailable: " + QString(platform) +
                                ": " + plugin.errorString());
                plugin.unload();
            }
            QTemporaryDir testProfile;
            run(stagedBin + "open-power-menu-editor",
                {"--config", testProfile.path() + "/menu.json", "--smoke-test"}, true);
            run("dbus-run-session", {"--", QCoreApplication::applicationFilePath(),
                                     "--probe-service", stagedBin + "open-power-menu-native"});
        } else if (args[1] == "--rollback") {
            const auto previous = previousReceipt["transaction"].toString();
            checkId(previous);
            auto oldTx = child(recovery, previous);
            auto oldJournal = json(oldTx, "journal.json");
            auto old = child(oldTx, "old");
            for (size_t i = 0; i < cs.size(); ++i) {
                auto n = QString::number(i);
                if (digest(old, n) != oldJournal["old"].toObject()[n].toString())
                    throw Error("Rollback snapshot changed");
                if (exists(old, n))
                    copy(old, n, staged, n);
            }
            j["rollbackReceipt"] = oldJournal["receipt"];
        } else {
            if (QFileInfo::exists(configRoot())) {
                auto configDirectory = directory(configRoot());
                if (exists(configDirectory, "plasma-org.kde.plasma.desktop-appletsrc") &&
                    read(configDirectory, "plasma-org.kde.plasma.desktop-appletsrc")
                        .contains("plugin=org.openpowermenu.start"))
                    throw Error("Remove the OPM applet from your panel first so Plasma restores "
                                "its launcher and shortcut bindings");
            }
        }
        QJsonObject newHashes;
        for (size_t i = 0; i < cs.size(); ++i)
            newHashes[QString::number(i)] = digest(staged, QString::number(i));
        j["new"] = newHashes;
        replaceJson(tx, "journal.json", j);
        replaceJson(recovery, "active.json", {{"id", id}});
        bool commitStarted = false, committed = false;
        try {
            // Every incoming tree is prepared before retiring an existing service.
            for (size_t i = 0; i < cs.size(); ++i)
                if (exists(staged, QString::number(i)))
                    copy(staged, QString::number(i), cs[i].parent, sibling(id, i, "new"));
            if (current(cs) != j["old"].toObject())
                throw Error("Installation changed during validation; refusing replacement");
            retire(appPath);
            for (size_t i = 0; i < cs.size(); ++i) {
                auto &c = cs[i];
                if (exists(c.parent, c.leaf))
                    move(c.parent, c.leaf, c.parent, sibling(id, i, "old"));
#ifdef OPM_INSTALL_TEST_HOOKS
                if (qEnvironmentVariable("OPM_INSTALL_CRASH_GAP") == QString::number(i))
                    _exit(86);
#endif
                if (exists(c.parent, sibling(id, i, "new")))
                    move(c.parent, sibling(id, i, "new"), c.parent, c.leaf);
#ifdef OPM_INSTALL_TEST_HOOKS
                if (qEnvironmentVariable("OPM_INSTALL_CRASH_AFTER") == QString::number(i))
                    _exit(86);
                if (qEnvironmentVariable("OPM_INSTALL_FAIL_AFTER") == QString::number(i))
                    throw Error("Injected replacement failure");
#endif
            }
            reload();
            if (install)
                activate();
            else if (args[1] == "--rollback" && exists(cs[5].parent, cs[5].leaf))
                activate(false);
            if (args[1] == "--rollback") {
                if (j["rollbackReceipt"].isObject())
                    replaceJson(recovery, "receipt.json", j["rollbackReceipt"].toObject());
                else
                    remove(recovery, "receipt.json");
            } else
                replaceJson(recovery, "receipt.json",
                            {{"transaction", id}, {"files", current(cs)}});
            j["committed"] = true;
            commitStarted = true;
            replaceJson(tx, "journal.json", j);
            committed = true;
#ifdef OPM_INSTALL_TEST_HOOKS
            if (qEnvironmentVariableIsSet("OPM_INSTALL_CRASH_COMMIT"))
                _exit(86);
#endif
            cleanStaging(cs, j);
            remove(recovery, "active.json");
            QTextStream(stdout)
                << "Native transaction committed: " << id
                << "\nSnapshots retained; configuration, panels and shortcuts preserved.\n";
        } catch (...) {
            if (committed) {
                QTextStream(stderr)
                    << "Installation committed; pending cleanup will resume with --recover.\n";
                return 0;
            }
            if (commitStarted) {
                QTextStream(stderr)
                    << "Commit durability uncertain; retained journal. Run --recover before "
                       "retrying.\n";
                throw;
            }
            try {
                retire(appPath);
                restore(tx, cs, j);
                if (previousReceipt.isEmpty())
                    remove(recovery, "receipt.json");
                else
                    replaceJson(recovery, "receipt.json", previousReceipt);
                reload();
                if (j["wasRunning"].toBool() && exists(cs[5].parent, cs[5].leaf))
                    activate(false);
                remove(recovery, "active.json");
            } catch (const Error &e) {
                QTextStream(stderr) << "Recovery requires --recover: " << e.what() << '\n';
            }
            throw;
        }
        return 0;
    } catch (const Error &e) {
        QTextStream(stderr) << "Open Power Menu install: " << e.what() << '\n';
        return 2;
    }
}
