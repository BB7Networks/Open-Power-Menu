#pragma once
#include "power.hpp"
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
    QString powerAction;
    QString program;
    QList<Entry> children;
};
struct Presentation { QJsonArray menu; QHash<QString, Entry> entries; };
class Model {
  public:
    explicit Model(std::shared_ptr<PowerManager> power = powerManager()) : power(std::move(power)) {}
    bool execute(const QJsonObject &config, const QString &key, const QJsonArray *expectedPresentation = nullptr);
    QList<Entry> normalize(const QJsonArray &items, bool showUnavailable = false, bool discoverPower = true);
    QJsonArray publicMenu(const QJsonObject &config);
    Presentation capture(const QJsonObject &config);
    Entry selected(const QJsonObject &config, const QString &key, const Presentation &shown);
    // One-shot CLI diagnostics can await discovery; interactive frontends must
    // use publicMenu(), which never waits for a power service.
    QJsonArray diagnosticMenu(const QJsonObject &config);
    std::shared_ptr<PowerManager> powerCapabilities() const { return power; }
    QStringList command(const QJsonObject &config, const QString &key,
                        const QJsonArray *expectedPresentation = nullptr);

  private:
    std::shared_ptr<PowerManager> power;
    std::optional<Entry> selection(const QJsonObject &config, const QString &key, const QJsonArray *expectedPresentation);
    struct Probe {
        qint64 expires;
        QString output;
    };
    QHash<QString, Probe> probes;
    QString probe(const QString &program, const QStringList &arguments);
    QStringList resolve(const QJsonObject &spec, bool expand = true);
};
} // namespace Opm
