#include "layouts.hpp"
#include <QJsonDocument>
#include <QSet>
#include <QUuid>
#include <chrono>

namespace Opm {
Layouts::Layouts(Storage source, std::function<qint64()> time)
    : storage(std::move(source)), clock(std::move(time)) {
    if (!clock)
        clock = [] {
            return std::chrono::duration_cast<std::chrono::milliseconds>(
                       std::chrono::steady_clock::now().time_since_epoch())
                .count();
        };
}
void Layouts::expire() {
    const auto cutoff = clock() - 30 * 60 * 1000;
    for (auto it = sessions.begin(); it != sessions.end();) {
        if (it->touched <= cutoff)
            it = sessions.erase(it);
        else
            ++it;
    }
}
Layouts::Session &Layouts::session(const QString &token) {
    expire();
    auto found = sessions.find(token);
    if (found == sessions.end())
        throw Error("Editing session expired; cancel and unlock again", "expired");
    found->touched = clock();
    return found.value();
}
QJsonObject Layouts::begin() {
    expire();
    if (sessions.size() >= 4)
        throw Error("Close another layout session before unlocking", "busy");
    Session state;
    state.revision = storage.revision();
    state.config = decode(state.revision.content);
    state.touched = clock();
    std::function<QJsonArray(const QJsonArray &)> present = [&](const QJsonArray &items) {
        QJsonArray views;
        for (const auto &value : items) {
            auto item = value.toObject();
            const auto id = QUuid::createUuid().toString(QUuid::Id128);
            QJsonObject view{{"id", id}};
            if (item.value("separator") == QJsonValue(true)) {
                view["kind"] = "separator";
                view["title"] = "Separator";
                view["icon"] = "list-remove";
            } else if (item.contains("submenu")) {
                view["kind"] = "submenu";
                view["title"] = item.value("submenu");
                view["icon"] = item.value("icon").toString().isEmpty() ? QJsonValue("folder")
                                                                       : item.value("icon");
                view["items"] = present(item.value("items").toArray());
                item.remove("items");
            } else {
                const auto action = actions()[item.value("action").toString()].toObject();
                view["kind"] = "command";
                auto title = item.value("label").toString();
                if (title.isEmpty())
                    title = action["title"].toString();
                auto icon = item.value("icon").toString();
                if (icon.isEmpty())
                    icon = action["icon"].toString();
                view["title"] = title.isEmpty() ? "Custom command" : title;
                view["icon"] = icon.isEmpty() ? "system-run" : icon;
            }
            state.references.insert(id, item);
            views.append(view);
        }
        return views;
    };
    const auto token = QUuid::createUuid().toString(QUuid::Id128);
    QJsonObject result{
        {"ok", true}, {"token", token}, {"entries", present(state.config["menu"].toArray())}};
    if (QJsonDocument(result).toJson(QJsonDocument::Compact).size() > MaxConfigBytes)
        throw Error("Layout too large for in-menu editing", "too-large");
    sessions.insert(token, state);
    return result;
}
bool Layouts::keep(const QString &token) {
    session(token);
    return true;
}
bool Layouts::cancel(const QString &token) {
    expire();
    return sessions.remove(token) > 0;
}
QJsonObject Layouts::save(const QString &token, const QString &payload) {
    auto &state = session(token);
    if (payload.size() > MaxConfigBytes)
        throw Error("Layout request exceeds the 4 MiB limit", "too-large");
    QJsonDocument proposal;
    try {
        proposal = parseJson(payload.toUtf8(), true);
    } catch (const Error &error) {
        throw Error(QString::fromUtf8(error.what()),
                    error.code == "too-large" ? "too-large" : "invalid");
    }
    QSet<QString> seen;
    std::function<QJsonArray(const QJsonValue &, int)> rebuild = [&](const QJsonValue &value,
                                                                     int depth) {
        if (depth > 8 || !value.isArray() || value.toArray().size() > 200)
            throw Error("Invalid layout size or nesting", "invalid");
        QJsonArray result;
        for (const auto &node : value.toArray()) {
            if (!node.isObject() || !node.toObject()["id"].isString())
                throw Error("Expected an existing item reference", "invalid");
            const auto object = node.toObject();
            const auto id = object["id"].toString();
            if (seen.contains(id) || !state.references.contains(id))
                throw Error("Unknown or repeated item reference", "invalid");
            seen.insert(id);
            auto item = state.references[id];
            const bool submenu =
                item.contains("submenu") && item.value("separator") != QJsonValue(true);
            const auto keys = object.keys();
            if (keys != (submenu ? QStringList{"id", "items"} : QStringList{"id"}))
                throw Error("Rearrangement cannot change item definitions", "invalid");
            if (submenu)
                item["items"] = rebuild(object["items"], depth + 1);
            result.append(item);
        }
        return result;
    };
    if (!proposal.isArray())
        throw Error("Layout must be an array", "invalid");
    auto config = state.config;
    config["menu"] = rebuild(proposal.array(), 0);
    if (seen.size() != state.references.size())
        throw Error("The layout is missing entries", "invalid");
    validate(config);
    if (storage.revision() != state.revision)
        throw Error("menu.json changed elsewhere; your draft is retained", "conflict");
    const bool changed = config["menu"] != state.config["menu"];
    if (changed)
        storage.save(config, state.revision);
    sessions.remove(token);
    return {{"ok", true}, {"changed", changed}};
}
} // namespace Opm
