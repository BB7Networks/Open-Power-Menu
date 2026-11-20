// Documentation capture driver, never installed or linked into production.
// It loads unchanged production QML with real EditorSession/EditorCatalog data.
#include "editor_catalog.hpp"
#include "editor_session.hpp"
#include <QGuiApplication>
#include <QIcon>
#include <QFile>
#include <QDir>
#include <QJsonDocument>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickItem>
#include <QQuickWindow>
#include <QScreen>
#include <QCursor>
#include <QtTest>
using namespace Opm;

int main(int argc, char **argv) {
    QGuiApplication app(argc,argv);
    app.setApplicationName("Open Power Menu Configure");
    app.setApplicationVersion("2.1.0");
    app.setOrganizationDomain("openpowermenu.org");
    QGuiApplication::setDesktopFileName("org.openpowermenu.configure");
    const QIcon icon(":/editor/open-power-menu.svg");
    QGuiApplication::setWindowIcon(icon);
    if (argc != 3) qFatal("Usage: opm-showcase-editor private-config output-directory");
    const QString output=QString::fromLocal8Bit(argv[2]);
    QDir().mkpath(output);
    EditorSession session(Storage(QString::fromLocal8Bit(argv[1])));
    // Create genuine ordinary backup revisions via the same save path as Configure.
    if (!session.preference(R"({"menu_density":"compact"})") || !session.save() ||
        !session.preference(R"({"menu_density":"standard"})") || !session.save())
        qFatal("Cannot prepare disposable backup history");
    EditorCatalog catalog;catalog.refresh();
    QQmlApplicationEngine engine;
    engine.rootContext()->setContextProperty("editorSession",&session);
    engine.rootContext()->setContextProperty("editorCatalog",&catalog);
    engine.load(QUrl("qrc:/editor/qml/Main.qml"));
    if (engine.rootObjects().isEmpty()) qFatal("Configure failed to load");
    auto *window=qobject_cast<QQuickWindow *>(engine.rootObjects().first());
    window->setIcon(icon);window->resize(1000,780);window->setPosition(300,80);
    if (!QTest::qWaitForWindowExposed(window)) qFatal("Configure not exposed");
    QTest::qWait(1000);
    const auto item=[&](const char *name) {
        auto *result=window->findChild<QQuickItem *>(QString::fromLatin1(name));
        if (!result) qFatal("Missing UI item: %s",name);
        return result;
    };
    const auto focus=[&](const char *name) {
        item(name)->forceActiveFocus();QTest::qWait(250);
    };
    const auto click=[&](const char *name) {
        auto *control=item(name);focus(name);
        const QPointF center(control->width()/2,control->height()/2);
        QCursor::setPos(control->mapToGlobal(center).toPoint());QTest::qWait(20);
        QTest::mouseClick(control->window(),Qt::LeftButton,Qt::NoModifier,control->mapToScene(center).toPoint());
        QTest::qWait(250);
    };
    QJsonArray records;
    const auto capture=[&](const QString &name) {
        QCursor::setPos(1590,10);QTest::qWait(400);
        const QRect rect=window->frameGeometry().adjusted(-6,-6,6,6);
        if (!window->screen()->grabWindow(0,rect.x(),rect.y(),rect.width(),rect.height()).save(output+'/'+name+".png"))
            qFatal("Cannot save editor screenshot");
        records.append(QJsonObject{{"name",name},{"crop",QJsonArray{rect.x(),rect.y(),rect.width(),rect.height()}},
            {"capture","QScreen.grabWindow(0); production QML and C++ models, documentation-only QtTest driver"},
            {"settings",QJsonDocument::fromJson(session.settingsJson().toUtf8()).object()}});
    };
    const auto invoke=[&](QObject *object,const char *method) {
        if (!QMetaObject::invokeMethod(object,method)) qFatal("Cannot invoke UI action: %s",method);
        QTest::qWait(200);
    };
    capture("configure-general");
    click("launcherSelection");capture("configure-launcher");QTest::keyClick(window,Qt::Key_Escape);
    focus("menu_icon_size");capture("configure-appearance");
    focus("accessKeyHints");capture("configure-keyboard-hover");
    click("powerConfirmation");capture("configure-power");QTest::keyClick(window,Qt::Key_Escape);
    click("layoutTab");
    const QJsonValue beforeReorder=session.configuration().value("menu");
    focus("inMenuLayoutEditor");
    QTest::keyClick(window,Qt::Key_Down);
    QTest::keyClick(window,Qt::Key_Down,Qt::AltModifier);
    QTest::qWait(200);
    if (session.configuration().value("menu")==beforeReorder) qFatal("Layout demonstration did not reorder the draft");
    capture("configure-layout");session.undo();
    auto *dialog=window->findChild<QObject *>("entryDialog");
    const auto begin=[&](const char *kind) {
        if (!QMetaObject::invokeMethod(dialog,"begin",Q_ARG(QVariant,kind),Q_ARG(QVariant,""),Q_ARG(QVariant,"")))
            qFatal("Cannot open entry dialog");
        QTest::qWait(300);
    };
    begin("builtin");capture("configure-builtin");invoke(dialog,"reject");
    auto *applications=window->findChild<QObject *>("applicationPicker");
    bool installedTerminal=false;
    for (const auto &row:catalog.applications())
        if (row.toMap()["id"].toString()=="org.kde.konsole.desktop") installedTerminal=true;
    if (!installedTerminal) qFatal("Real Konsole desktop entry missing from application catalog");
    invoke(applications,"open");item("applicationSearch")->setProperty("text","terminal");
    QTest::qWait(300);capture("configure-application");invoke(applications,"close");
    begin("command");
    item("entryName")->setProperty("text","Project terminal");
    item("entryIcon")->setProperty("text","utilities-terminal");
    item("entryAccessKey")->setProperty("text","C");
    const QVariant command=QVariantList{"konsole","--workdir","~/Projects"};
    if (!QMetaObject::invokeMethod(dialog,"setCommand",Q_ARG(QVariant,command))) qFatal("Cannot set example argv");
    capture("configure-custom-command");invoke(dialog,"reject");
    begin("submenu");
    item("entryName")->setProperty("text","Development");
    item("entryIcon")->setProperty("text","folder-development");
    item("entryAccessKey")->setProperty("text","B");
    capture("configure-submenu");invoke(dialog,"reject");
    click("backupsTab");session.refreshBackups();
    const auto backups=QJsonDocument::fromJson(session.backupsJson().toUtf8()).array();
    if (backups.isEmpty() || !session.selectBackup(backups.first().toObject()["name"].toString()))
        qFatal("No genuine backup to preview");
    capture("configure-backups");
    QFile manifest(output+"/editor-captures.json");
    if (!manifest.open(QIODevice::WriteOnly)) qFatal("Cannot write editor provenance");
    manifest.write(QJsonDocument(records).toJson());
    return 0;
}
