#pragma once
#include "model.hpp"
#include <QDateTime>
#include <sys/types.h>

namespace Opm {
struct Revision {
    std::optional<QByteArray> content;
    dev_t device = 0;
    ino_t inode = 0;
    bool operator==(const Revision &other) const {
        return content == other.content && device == other.device && inode == other.inode;
    }
    bool operator!=(const Revision &other) const { return !(*this == other); }
};
struct BackupSnapshot {
    QString name;
    dev_t directoryDevice = 0;
    ino_t directoryInode = 0;
    dev_t device = 0;
    ino_t inode = 0;
    qint64 size = 0;
    qint64 modifiedNs = 0;
    qint64 changedNs = 0;
    QByteArray digest;
    bool operator==(const BackupSnapshot &other) const;
    bool operator!=(const BackupSnapshot &other) const { return !(*this == other); }
};
struct Backup {
    QString name;
    qint64 size = 0;
    QDateTime modified;
    bool protectedCopy = false;
    std::optional<BackupSnapshot> snapshot;
    std::optional<QJsonObject> config;
    QString error;
};
enum class SaveReason { Normal, Overwrite };
class Storage {
  public:
    explicit Storage(QString file = {});
    QString path() const { return target; }
    Revision revision() const;
    QJsonObject load() const { return decode(revision().content); }
    Revision save(const QJsonObject &config, const Revision &expected,
                  SaveReason reason = SaveReason::Normal) const;
    QList<Backup> backups() const;
    Backup preview(const QString &name) const;
    Revision restore(const BackupSnapshot &source, const Revision &expected) const;
    void removeBackup(const BackupSnapshot &source, bool confirmProtected = false) const;

  private:
    QString target;
};
} // namespace Opm
