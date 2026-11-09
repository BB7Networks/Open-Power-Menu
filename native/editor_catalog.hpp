#pragma once
#include <QObject>
#include <QUrl>
#include <QVariantList>
#include "power.hpp"

namespace Opm {
class EditorCatalog : public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantList actions READ actions CONSTANT)
    Q_PROPERTY(QVariantList launchers READ launchers NOTIFY refreshed)
    Q_PROPERTY(QVariantList applications READ applications NOTIFY refreshed)
    Q_PROPERTY(QString snapshotStatus READ snapshotStatus NOTIFY refreshed)
    QVariantList applicationRows, launcherRows;
    std::shared_ptr<PowerManager> power = powerManager();

  public:
    explicit EditorCatalog(QObject *parent = nullptr);
    QVariantList actions() const;
    QVariantList launchers() const { return launcherRows; }
    QVariantList applications() const { return applicationRows; }
    QString snapshotStatus() const;
    Q_INVOKABLE void refresh();
    Q_INVOKABLE QString applicationItem(const QString &storageId) const;
    Q_INVOKABLE QVariantMap builtinDetails(const QString &actionId) const;
    Q_INVOKABLE QString localFile(const QUrl &url) const { return url.toLocalFile(); }
    Q_INVOKABLE void copy(const QString &text) const;
  signals:
    void refreshed();
    void powerChanged();
};
} // namespace Opm
