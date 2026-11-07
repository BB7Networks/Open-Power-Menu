#pragma once
#include <QHash>
#include <QJsonArray>
#include <QJsonObject>
#include <QStringList>
#include <optional>
#include <stdexcept>

namespace Opm {
constexpr qint64 MaxConfigBytes = 4 * 1024 * 1024;
class Error : public std::runtime_error {
  public:
    QString code;
    explicit Error(const QString &message, const QString &category = "configuration")
        : std::runtime_error(message.toStdString()), code(category) {}
};
QJsonObject defaults();
QJsonObject actions();
QJsonDocument parseJson(const QByteArray &bytes, bool uniqueKeys = false);
QJsonObject decode(const std::optional<QByteArray> &bytes);
void validate(const QJsonObject &config);
QJsonObject integration(const QJsonObject &config);
QString expandPart(QString value);

struct Entry {
    QJsonObject view;
    QStringList argv;
    QList<Entry> children;
};
class Model {
  public:
    QList<Entry> normalize(const QJsonArray &items, bool showUnavailable = false);
    QJsonArray publicMenu(const QJsonObject &config);
    QStringList command(const QJsonObject &config, const QString &key,
                        const QJsonArray *expectedPresentation = nullptr);

  private:
    struct Probe {
        qint64 expires;
        QString output;
    };
    QHash<QString, Probe> probes;
    QString probe(const QString &program, const QStringList &arguments);
    QStringList resolve(const QJsonObject &spec, bool expand = true);
};
} // namespace Opm
