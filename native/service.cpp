#include "service.hpp"
#include <QCoreApplication>
#include <QDebug>
#include <QJsonDocument>
#include <QProcess>

namespace Opm {
static QString json(const QJsonObject &value) {
    return QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
}
static QString reply(const std::function<QJsonObject()> &operation) {
    try {
        return json(operation());
    } catch (const Error &error) {
        const auto message =
            error.code == "configuration"
                ? QString("Could not read or save configuration safely; your draft is retained")
                : QString::fromUtf8(error.what());
        return json({{"ok", false}, {"code", error.code}, {"message", message}});
    }
}
Service::Service(Storage source, QObject *parent)
    : QObject(parent), storage(std::move(source)), layouts(storage) {
    idle.setSingleShot(true);
    idle.setInterval(5 * 60 * 1000);
    connect(&idle, &QTimer::timeout, QCoreApplication::instance(), &QCoreApplication::quit);
    touch();
}
void Service::touch() {
    idle.start();
}
QString Service::Ping() {
    touch();
    return "Open Power Menu v" OPM_NATIVE_VERSION;
}
QString Service::GetMenu() {
    touch();
    try {
        return QString::fromUtf8(
            QJsonDocument(model.publicMenu(storage.load())).toJson(QJsonDocument::Compact));
    } catch (const Error &error) {
        qWarning() << "Open Power Menu configuration error:" << error.what();
        return QString::fromUtf8(
            QJsonDocument(QJsonArray{QJsonObject{{"kind", "command"},
                                                 {"key", ""},
                                                 {"title", "Invalid menu.json — see README"},
                                                 {"icon", "dialog-error"},
                                                 {"enabled", false}}})
                .toJson(QJsonDocument::Compact));
    }
}
QString Service::GetIntegration() {
    touch();
    try {
        return json(integration(storage.load()));
    } catch (const Error &error) {
        qWarning() << "Integration configuration error:" << error.what();
        return json(integration(defaults()));
    }
}
bool Service::Run(const QString &key) {
    touch();
    try {
        auto args = model.command(storage.load(), key);
        if (args.isEmpty())
            return false;
        QProcess process;
        process.setProgram(args.takeFirst());
        process.setArguments(args);
        process.setStandardInputFile(QProcess::nullDevice());
        process.setStandardOutputFile(QProcess::nullDevice());
        process.setStandardErrorFile(QProcess::nullDevice());
        // Qt's Unix detached launch creates a new session and reaps its
        // intermediate child; no shell or inherited service pipes are used.
        return process.startDetached();
    } catch (const Error &error) {
        qWarning() << "Could not resolve menu item:" << error.what();
        return false;
    }
}
bool Service::Edit() {
    touch();
    qWarning("Native Configure is not implemented yet. Keep using the normal 1.0.1 application for "
             "editing.");
    return false;
}
QString Service::BeginLayoutEdit() {
    touch();
    return reply([this] { return layouts.begin(); });
}
QString Service::SaveLayoutEdit(const QString &token, const QString &references) {
    touch();
    return reply([&] { return layouts.save(token, references); });
}
bool Service::CancelLayoutEdit(const QString &token) {
    touch();
    return layouts.cancel(token);
}
QString Service::KeepLayoutEdit(const QString &token) {
    touch();
    return reply([&] { return QJsonObject{{"ok", layouts.keep(token)}}; });
}
} // namespace Opm
