#pragma once
#include "layouts.hpp"
#include <QObject>
#include <QTimer>
#include <QDBusContext>
#include <QDBusServiceWatcher>
#include <QElapsedTimer>

namespace Opm {
class Service : public QObject, protected QDBusContext {
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.openpowermenu.Service")
    Storage storage;
    Model model;
    Layouts layouts;
    QTimer idle;
    QHash<QString, QString> errors;
    struct Menu { Revision revision; Presentation shown; qint64 expires; };
    QHash<QString, Menu> menus;
    struct Operation { bool pending = true, alive = true; QString owner, error; qint64 expires = 0; };
    QHash<QString, std::shared_ptr<Operation>> operations;
    QElapsedTimer elapsed;
    std::function<qint64()> now;
    QDBusServiceWatcher clients;
    QString caller() const;
    void prune();
    void start(const QString &key, std::function<void(QString)> done, std::function<bool()> alive = {});
    bool lastMenuPowerPending = false;
    void touch();

  public:
    explicit Service(Storage source, QObject *parent = nullptr,
                     std::shared_ptr<PowerManager> power = powerManager(), std::function<qint64()> clock = {});
  public slots:
    QString Ping();
    QString GetMenu();
    bool PowerCapabilitiesPending();
    QString GetIntegration();
    bool Run(const QString &key);
    QString StartRun(const QString &key);
    QString RunResult(const QString &operation);
    QString LastError();
    bool Edit();
    QString BeginLayoutEdit();
    QString SaveLayoutEdit(const QString &token, const QString &references);
    bool CancelLayoutEdit(const QString &token);
    QString KeepLayoutEdit(const QString &token);
};
} // namespace Opm
