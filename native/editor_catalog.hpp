#pragma once
#include <QObject>
#include <QVariantList>

namespace Opm {
class EditorCatalog : public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantList actions READ actions CONSTANT)
    Q_PROPERTY(QVariantList launchers READ launchers NOTIFY refreshed)
    Q_PROPERTY(QVariantList applications READ applications NOTIFY refreshed)
    Q_PROPERTY(QString snapshotStatus READ snapshotStatus NOTIFY refreshed)
    QVariantList applicationRows, launcherRows;

  public:
    using QObject::QObject;
    QVariantList actions() const;
    QVariantList launchers() const { return launcherRows; }
    QVariantList applications() const { return applicationRows; }
    QString snapshotStatus() const;
    Q_INVOKABLE void refresh();
    Q_INVOKABLE QString applicationItem(const QString &storageId) const;
    Q_INVOKABLE void copy(const QString &text) const;
  signals:
    void refreshed();
};
} // namespace Opm
