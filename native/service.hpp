#pragma once
#include "layouts.hpp"
#include <QObject>
#include <QTimer>

namespace Opm {
class Service : public QObject {
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.openpowermenu.Service")
    Storage storage;
    Model model;
    Layouts layouts;
    QTimer idle;
    QString lastError;
    std::optional<QJsonArray> lastMenu;
    void touch();

  public:
    explicit Service(Storage source, QObject *parent = nullptr);
  public slots:
    QString Ping();
    QString GetMenu();
    QString GetIntegration();
    bool Run(const QString &key);
    QString LastError();
    bool Edit();
    QString BeginLayoutEdit();
    QString SaveLayoutEdit(const QString &token, const QString &references);
    bool CancelLayoutEdit(const QString &token);
    QString KeepLayoutEdit(const QString &token);
};
} // namespace Opm
