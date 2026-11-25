#pragma once
#include "storage.hpp"
#include <functional>

namespace Opm {
class Layouts {
    struct Session {
        QJsonObject config;
        Revision revision;
        QHash<QString, QJsonObject> references;
        qint64 touched;
    };
    Storage storage;
    QHash<QString, Session> sessions;
    std::function<qint64()> clock;
    void expire();
    Session &session(const QString &token);

  public:
    explicit Layouts(Storage source, std::function<qint64()> time = {});
    QJsonObject begin();
    QJsonObject save(const QString &token, const QString &payload);
    bool keep(const QString &token);
    bool cancel(const QString &token);
};
} // namespace Opm
