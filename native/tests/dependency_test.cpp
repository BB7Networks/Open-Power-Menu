#include "packaging/dependency_review.hpp"
#include <QDir>
#include <QElapsedTimer>
#include <QFile>
#include <QJsonArray>
#include <QTemporaryDir>
#include <QtTest>
#include <fcntl.h>
#include <sys/file.h>
#include <unistd.h>
using namespace Opm::Install;
class DependencyTests : public QObject {
    Q_OBJECT
  private slots:
    void unsupportedAndFailedQueries() {
        auto noRun=[](const QString &,const QStringList &)->PackageQuery { qFatal("Unexpected query"); };
        auto report=dependencyReview(noRun,[](const QString &){return false;});
        QVERIFY(!report["installed"].toBool()); QVERIFY(!report["complete"].toBool());
        report=dependencyReview([](const QString &,const QStringList &){return PackageQuery{};},[](const QString &n){return n=="pacman";});
        QVERIFY(!report["complete"].toBool());
        QVERIFY(dependencyGuidance(report).contains("Keep PySide6"));
    }
    void arch_data() {
        QTest::addColumn<int>("code"); QTest::addColumn<QString>("required"); QTest::addColumn<QString>("optional");
        QTest::newRow("absent")<<1<<QString()<<QString();
        QTest::newRow("explicit-unused")<<0<<QString("None")<<QString("None");
        QTest::newRow("reverse-dependencies")<<0<<QString("other-app")<<QString("optional-app");
        QTest::newRow("incomplete")<<0<<QString()<<QString();
    }
    void arch() {
        QFETCH(int,code);QFETCH(QString,required);QFETCH(QString,optional);
        auto report=dependencyReview([&](const QString &program,const QStringList &args){
            if(program!="pacman" || args!=QStringList{"-Qi","pyside6"}) qFatal("Mutating or unexpected package command");
            return PackageQuery{code,"Name : pyside6\nInstall Reason : Explicitly installed\nRequired By : "+required+"\nOptional For : "+optional+"\n",true};
        },[](const QString &n){return n=="pacman";});
        QCOMPARE(report["installed"].toBool(),code==0);
        QCOMPARE(report["recommendation"].toString(),"Keep PySide6");
        const auto guide=dependencyGuidance(report);
        QVERIFY(guide.contains("not proof")); QVERIFY(guide.contains("Rollback"));
        QVERIFY(!guide.contains("pacman -R"));
    }
    void slowQueryFailsClosedWithinBudget() {
        QTemporaryDir tmp;
        QFile program(tmp.filePath("pacman"));
        QVERIFY(program.open(QIODevice::WriteOnly));
        program.write("#!/bin/sh\nexec /bin/sleep 3\n");
        program.close();
        QVERIFY(program.setPermissions(QFile::ReadOwner | QFile::WriteOwner | QFile::ExeOwner));
        const auto previous = qgetenv("PATH");
        qputenv("PATH", QFile::encodeName(tmp.path()));
        QElapsedTimer elapsed;
        elapsed.start();
        const auto report = dependencyReview({}, [](const QString &name) { return name == "pacman"; });
        qputenv("PATH", previous);
        QVERIFY(!report["complete"].toBool());
        QVERIFY(!report["installed"].toBool());
        QVERIFY(elapsed.elapsed() < 2500);
    }
    void archWrappedDependencies() {
        const auto report = dependencyReview([](const QString &, const QStringList &) {
            return PackageQuery{0, "Name            : pyside6\nRequired By     : app-one  app-two\n                  app-three\nOptional For    : optional-one\n                  optional-two\nInstall Reason  : Installed as a dependency for another package\n", true};
        }, [](const QString &name) { return name == "pacman"; });
        QVERIFY(report["complete"].toBool());
        const auto item = report["packages"].toArray().first().toObject();
        QVERIFY(item["required_by"].toString().contains("app-three"));
        QVERIFY(item["optional_for"].toString().contains("optional-two"));
    }
    void concurrentNoticeLeavesStateUntouched() {
        QTemporaryDir tmp;
        const auto state = tmp.filePath("open-power-menu-recovery/dependency-review");
        QVERIFY(QDir().mkpath(state));
        const auto path = QFile::encodeName(state + "/lock");
        const int lock = ::open(path.constData(), O_RDWR | O_CREAT, 0600);
        QVERIFY(lock >= 0);
        QVERIFY(::flock(lock, LOCK_EX | LOCK_NB) == 0);
        int queries = 0;
        offerDependencyReview(tmp.path(), true, [&] { ++queries; return QJsonObject{{"installed", true}}; });
        QCOMPARE(queries, 0);
        QVERIFY(!QFile::exists(state + "/native-2.1.json"));
        ::close(lock);
        offerDependencyReview(tmp.path(), true, [&] { ++queries; return QJsonObject{{"installed", true}}; });
        QCOMPARE(queries, 1);
        QVERIFY(QFile::exists(state + "/native-2.1.json"));
    }
    void debianAndLiteralQueries() {
        QStringList calls;
        auto report=dependencyReview([&](const QString &program,const QStringList &args){
            calls<<program;
            if(program=="dpkg-query") return PackageQuery{0,"installed\tpython3-pyside6.qtcore:amd64\ninstalled\tpython3-pyside6.qtwidgets\nconfig-files\tpython3-pyside6.qtgui\n",true};
            if(args.last().contains(';')) qFatal("Untrusted package argument");
            if(program=="apt-mark") return PackageQuery{0,args.last()+"\n",true};
            if(program=="apt-cache") return PackageQuery{0,"Reverse Depends:\n other-app\n",true};
            qFatal("Unexpected command");
        },[](const QString &n){return n!="pacman";});
        QVERIFY(report["installed"].toBool()); QVERIFY(report["complete"].toBool());
        QCOMPARE(report["packages"].toArray().size(),2);
        QVERIFY(!calls.contains("apt-get"));
        QVERIFY(report["review_command"].toString().startsWith("apt-get --simulate remove "));
    }
    void noticeIsPostUpgradeOnceAndDeclineKeepsPackages() {
        QTemporaryDir tmp; int queries=0;
        auto discover=[&]{++queries;return QJsonObject{{"installed",true},{"complete",true}};};
        offerDependencyReview(tmp.path(),false,discover); QCOMPARE(queries,0);
        offerDependencyReview(tmp.path(),true,discover); QCOMPARE(queries,1);
        offerDependencyReview(tmp.path(),true,discover); QCOMPARE(queries,1);
        QVERIFY(QFile::exists(tmp.filePath("open-power-menu-recovery/dependency-review/native-2.1.json")));
        QVERIFY(!QFile::exists(tmp.filePath("menu.json")));
        reviewDependencies(tmp.path(),true);
        offerDependencyReview(tmp.path(),true,discover); QCOMPARE(queries,1);
    }
    void absentAndFailedNoticeDoNotFailInstallation() {
        QTemporaryDir tmp;
        offerDependencyReview(tmp.path(),true,[]{return QJsonObject{{"installed",false}};});
        QVERIFY(!QFile::exists(tmp.filePath("open-power-menu-recovery/dependency-review/native-2.1.json")));
        offerDependencyReview(tmp.path(),true,[]()->QJsonObject{throw std::runtime_error("mock query failed");});
        QVERIFY(!QFile::exists(tmp.filePath("open-power-menu-recovery/dependency-review/native-2.1.json")));
    }
    void noticeRefusesSymlinkState() {
        QTemporaryDir tmp; auto state=tmp.filePath("open-power-menu-recovery/dependency-review");
        QDir().mkpath(state); QFile target(tmp.filePath("untouched")); QVERIFY(target.open(QIODevice::WriteOnly));target.write("sentinel");target.close();
        QVERIFY(QFile::link(target.fileName(),state+"/native-2.1.json"));
        offerDependencyReview(tmp.path(),true,[]{return QJsonObject{{"installed",true}};});
        QVERIFY(target.open(QIODevice::ReadOnly));QCOMPARE(target.readAll(),QByteArray("sentinel"));
    }
};
QTEST_GUILESS_MAIN(DependencyTests)
#include "dependency_test.moc"
