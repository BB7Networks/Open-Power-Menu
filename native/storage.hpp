#pragma once
#include "model.hpp"
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
class Storage {
  public:
    explicit Storage(QString file = {});
    QString path() const { return target; }
    Revision revision() const;
    QJsonObject load() const { return decode(revision().content); }
    void save(const QJsonObject &config, const Revision &expected) const;

  private:
    QString target;
};
} // namespace Opm
