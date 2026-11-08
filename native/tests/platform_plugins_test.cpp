#include "packaging/platform_plugins.hpp"
#include "model.hpp"
#include <QDir>
#include <QFile>
#include <QLibraryInfo>
#include <QPluginLoader>
#include <QTemporaryDir>
#include <QtTest>
using namespace Opm;
class PlatformPluginTests : public QObject {
    Q_OBJECT
    QString directory() const { return QLibraryInfo::path(QLibraryInfo::PluginsPath) + "/platforms"; }
    QString plugin(const QString &key) const {
        for (const auto &file : QDir(directory()).entryInfoList({"*.so"}, QDir::Files)) {
            QPluginLoader loader(file.absoluteFilePath());
            if (loader.metaData().value("MetaData").toObject().value("Keys").toArray().contains(key))
                return file.absoluteFilePath();
        }
        return {};
    }
  private slots:
    void distributionPluginsLoad() {
        Install::validatePlatformPlugins(directory());
    }
    void renamedLibrariesRetainCapabilities() {
        QTemporaryDir temp;
        QVERIFY(!plugin("xcb").isEmpty());
        QVERIFY(!plugin("wayland").isEmpty());
        QVERIFY(QFile::copy(plugin("xcb"), temp.filePath("libdifferent-x.so")));
        QVERIFY(QFile::copy(plugin("wayland"), temp.filePath("libdifferent-w.so")));
        Install::validatePlatformPlugins(temp.path());
    }
    void missingBackendFailsClosed() {
        QTemporaryDir temp;
        QVERIFY_EXCEPTION_THROWN(Install::validatePlatformPlugins(temp.path()), Error);
        QVERIFY(QFile::copy(plugin("xcb"), temp.filePath("libplatform.so")));
        try {
            Install::validatePlatformPlugins(temp.path());
            QFAIL("Missing Wayland backend accepted");
        } catch (const Error &error) {
            QVERIFY(QString::fromUtf8(error.what()).contains("wayland"));
        }
    }
    void filenameAloneCannotSatisfyBackend() {
        QTemporaryDir temp;
        for (const auto &name : {"libqxcb.so", "libqwayland-generic.so", "libqwayland.so"}) {
            QFile file(temp.filePath(name));
            QVERIFY(file.open(QIODevice::WriteOnly));
            file.write("not a Qt platform plugin");
        }
        QVERIFY_EXCEPTION_THROWN(Install::validatePlatformPlugins(temp.path()), Error);
    }
};
QTEST_GUILESS_MAIN(PlatformPluginTests)
#include "platform_plugins_test.moc"
