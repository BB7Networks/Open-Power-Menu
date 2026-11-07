#include "editor_session.hpp"
#include <QJsonDocument>
#include <QSet>
#include <QUuid>

namespace Opm {
namespace {
QString json(const QJsonObject &value) {
    return QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
}
QJsonObject object(const QString &text) {
    if (text.size() > MaxConfigBytes)
        throw Error("Editor change exceeds the 4 MiB limit", "too-large");
    auto value = parseJson(text.toUtf8(), true);
    if (!value.isObject())
        throw Error("Expected an object of edited fields", "invalid");
    return value.object();
}
QString kind(const QJsonObject &item) {
    if (item.value("separator") == QJsonValue(true))
        return "separator";
    if (item.contains("submenu"))
        return "submenu";
    return item.contains("action") ? "builtin" : "command";
}
QJsonArray nodes(const QJsonArray &items) {
    QJsonArray result;
    for (const auto &entry : items) {
        auto definition = entry.toObject();
        QJsonObject node{{"id", QUuid::createUuid().toString(QUuid::Id128)}};
        if (kind(definition) == "submenu") {
            node["items"] = nodes(definition.value("items").toArray());
            definition.remove("items");
        }
        node["definition"] = definition;
        result.append(node);
    }
    return result;
}
QJsonArray definitions(const QJsonArray &tree) {
    QJsonArray result;
    for (const auto &value : tree) {
        const auto node = value.toObject();
        auto item = node["definition"].toObject();
        if (kind(item) == "submenu")
            item["items"] = definitions(node["items"].toArray());
        result.append(item);
    }
    return result;
}
QJsonObject fields(const QJsonObject &node) {
    const auto item = node["definition"].toObject();
    const auto type = kind(item);
    const auto builtin = actions()[item["action"].toString()].toObject();
    QJsonObject result{{"id", node["id"]}, {"kind", type}};
    result["label"] = item["label"].toString();
    result["icon"] = item["icon"].toString();
    result["title"] = type == "separator"                      ? QString("Separator")
                      : type == "submenu"                      ? item["submenu"].toString()
                      : !item["label"].toString().isEmpty()    ? item["label"].toString()
                      : !builtin["title"].toString().isEmpty() ? builtin["title"].toString()
                                                               : QString("Custom command");
    if (type == "builtin")
        result["action"] = item["action"];
    if (type == "submenu")
        result["submenu"] = item["submenu"];
    if (type == "command") {
        const auto first =
            item.contains("command") ? item["command"] : item["commands"].toArray().first();
        result["command"] = first.isObject() ? first.toObject()["argv"] : first;
        result["alternatives"] = item.contains("commands");
    }
    return result;
}
QJsonArray views(const QJsonArray &tree) {
    QJsonArray result;
    for (const auto &value : tree) {
        const auto node = value.toObject();
        const auto data = fields(node);
        const auto type = data["kind"].toString();
        QJsonObject view{{"id", node["id"]},
                         {"title", data["title"]},
                         {"icon", data["icon"]},
                         {"kind", type == "builtin" ? "command" : type}};
        if (type == "submenu")
            view["items"] = views(node["items"].toArray());
        result.append(view);
    }
    return result;
}
QJsonObject find(const QJsonArray &tree, const QString &id) {
    for (const auto &value : tree) {
        const auto node = value.toObject();
        if (node["id"] == id)
            return node;
        const auto child = find(node["items"].toArray(), id);
        if (!child.isEmpty())
            return child;
    }
    return {};
}
QJsonArray modify(const QJsonArray &tree, const QString &id,
                  const std::function<QJsonArray(QJsonObject)> &change) {
    QJsonArray result;
    for (const auto &value : tree) {
        auto node = value.toObject();
        if (node["id"] == id) {
            for (const auto &replacement : change(node))
                result.append(replacement);
        } else {
            if (node.contains("items"))
                node["items"] = modify(node["items"].toArray(), id, change);
            result.append(node);
        }
    }
    return result;
}
QJsonArray insert(const QJsonArray &tree, const QString &parentId, const QString &beforeId,
                  const QJsonObject &node) {
    const auto into = [&](QJsonArray list) {
        qsizetype index = list.size();
        if (!beforeId.isEmpty()) {
            index = -1;
            for (qsizetype i = 0; i < list.size(); ++i)
                if (list[i].toObject()["id"] == beforeId)
                    index = i;
            if (index < 0)
                throw Error("Choose a position inside this submenu", "invalid");
        }
        list.insert(index, node);
        return list;
    };
    if (parentId.isEmpty())
        return into(tree);
    const auto parent = find(tree, parentId);
    if (parent.isEmpty() || !parent.contains("items"))
        throw Error("Choose an existing submenu", "invalid");
    return modify(tree, parentId, [&](QJsonObject value) {
        value["items"] = into(value["items"].toArray());
        return QJsonArray{value};
    });
}
QString summary(const QJsonObject &config) {
    QStringList lines;
    std::function<void(const QJsonArray &, int)> walk = [&](const QJsonArray &tree, int depth) {
        for (const auto &value : tree) {
            const auto node = value.toObject();
            lines.append(QString(depth * 2, ' ') + fields(node)["title"].toString());
            walk(node["items"].toArray(), depth + 1);
        }
    };
    walk(nodes(config["menu"].toArray()), 0);
    auto settings = config;
    settings.remove("menu");
    return QString::number(lines.size()) + " entries\n" + lines.join('\n') + "\n\nSettings:\n" +
           QString::fromUtf8(QJsonDocument(settings).toJson());
}
} // namespace
EditorSession::EditorSession(Storage source, QObject *parent)
    : QObject(parent), storage(std::move(source)),
      token(QUuid::createUuid().toString(QUuid::Id128)) {
    try {
        baseline = storage.revision();
        reset(decode(baseline.content), baseline);
    } catch (const Error &failure) {
        reset(defaults(), baseline);
        loadFailure = QString::fromUtf8(failure.what());
        message = loadFailure;
        category = "configuration";
    }
    refreshBackups();
}
QJsonObject EditorSession::configuration(const State &state) const {
    auto value = state.settings;
    value["menu"] = definitions(state.nodes);
    return value;
}
QString EditorSession::settingsJson() const {
    return json(history[position].settings);
}
QString EditorSession::layoutJson() const {
    return json({{"token", token}, {"entries", views(history[position].nodes)}});
}
bool EditorSession::dirty() const {
    return !loadFailure.isEmpty() || configuration() != savedConfig;
}
void EditorSession::reset(const QJsonObject &config, const Revision &revision) {
    auto settings = config;
    settings.remove("menu");
    history = {{settings, nodes(config["menu"].toArray()), {}}};
    position = 0;
    baseline = revision;
    savedConfig = config;
    loadFailure.clear();
    external = false;
    overwritePreview.reset();
    emit changed();
    emit messageChanged();
}
void EditorSession::apply(State state) {
    const auto config = configuration(state);
    validate(config);
    if (QJsonDocument(config).toJson().size() > MaxConfigBytes)
        throw Error("Configuration exceeds the 4 MiB limit", "too-large");
    if (config == configuration())
        return;
    while (history.size() > position + 1)
        history.removeLast();
    history.append(std::move(state));
    ++position;
    // Bound retained drafts by both count and serialized size. Unknown metadata
    // remains native JSON, never round-tripped through JavaScript numbers.
    qsizetype retained = 0;
    for (qsizetype i = history.size() - 1; i >= 0; --i) {
        retained +=
            QJsonDocument(configuration(history[i])).toJson(QJsonDocument::Compact).size() * 2;
        if (i < position && (retained > 64 * 1024 * 1024 || history.size() - i > 100)) {
            history.erase(history.begin(), history.begin() + i + 1);
            position -= i + 1;
            break;
        }
    }
    overwritePreview.reset();
    emit changed();
}
bool EditorSession::perform(const std::function<void()> &operation) {
    try {
        operation();
        message.clear();
        category.clear();
        emit messageChanged();
        return true;
    } catch (const Error &failure) {
        message = QString::fromUtf8(failure.what());
        category = failure.code;
        if (category == "conflict")
            external = true;
        emit messageChanged();
        return false;
    }
}
QString EditorSession::itemFields(const QString &id) const {
    const auto node = find(history[position].nodes, id);
    return node.isEmpty() ? "{}" : json(fields(node));
}
bool EditorSession::preference(const QString &text) {
    return perform([&] {
        const auto changes = object(text);
        auto state = history[position];
        const QSet<QString> allowed{"appearance",
                                    "anchor",
                                    "hide_original_launcher",
                                    "launcher_applet_id",
                                    "button_icon_mode",
                                    "button_icon",
                                    "show_menu_icons",
                                    "auto_close_on_pointer_leave",
                                    "backup_retention",
                                    "show_unavailable"};
        for (auto it = changes.begin(); it != changes.end(); ++it) {
            if (!allowed.contains(it.key()))
                throw Error("Unknown editable preference", "invalid");
            state.settings[it.key()] = it.value();
        }
        apply(state);
    });
}
bool EditorSession::addItem(const QString &parentId, const QString &beforeId, const QString &text) {
    return perform([&] {
        const auto item = object(text);
        auto check = defaults();
        check["menu"] = QJsonArray{item};
        validate(check);
        auto state = history[position];
        const auto added = nodes(QJsonArray{item})[0].toObject();
        state.nodes = insert(state.nodes, parentId, beforeId, added);
        state.selection = added["id"].toString();
        apply(state);
        emit focusItem(added["id"].toString());
    });
}
bool EditorSession::editItem(const QString &id, const QString &text) {
    return perform([&] {
        auto state = history[position];
        const auto selectedNode = find(state.nodes, id);
        if (selectedNode.isEmpty())
            throw Error("Select an existing entry", "invalid");
        const auto type = kind(selectedNode["definition"].toObject());
        const auto changes = object(text);
        const QSet<QString> allowed = type == "submenu"   ? QSet<QString>{"submenu", "icon"}
                                      : type == "builtin" ? QSet<QString>{"action", "label", "icon"}
                                      : type == "command"
                                          ? QSet<QString>{"label", "icon", "command"}
                                          : QSet<QString>{};
        for (const auto &key : changes.keys())
            if (!allowed.contains(key))
                throw Error("This field does not belong to the selected entry", "invalid");
        state.nodes = modify(state.nodes, id, [&](QJsonObject node) {
            auto item = node["definition"].toObject();
            if (changes.contains("command") && changes["command"] != fields(node)["command"]) {
                item.remove("commands");
                item.remove("desktop_file");
            }
            for (auto it = changes.begin(); it != changes.end(); ++it) {
                if (it.key() == "command" && it.value() == fields(node)["command"])
                    continue;
                item[it.key()] = it.value();
            }
            node["definition"] = item;
            return QJsonArray{node};
        });
        apply(state);
    });
}
bool EditorSession::removeItem(const QString &id) {
    return perform([&] {
        auto state = history[position];
        if (find(state.nodes, id).isEmpty())
            throw Error("Select an entry", "invalid");
        state.nodes = modify(state.nodes, id, [](QJsonObject) { return QJsonArray{}; });
        apply(state);
    });
}
bool EditorSession::duplicateItem(const QString &id) {
    return perform([&] {
        auto state = history[position];
        if (find(state.nodes, id).isEmpty())
            throw Error("Select an entry", "invalid");
        QString addedId;
        state.nodes = modify(state.nodes, id, [&](QJsonObject node) {
            const auto added = nodes(definitions(QJsonArray{node}))[0].toObject();
            addedId = added["id"].toString();
            return QJsonArray{node, added};
        });
        state.selection = addedId;
        apply(state);
        emit focusItem(addedId);
    });
}
bool EditorSession::rearrange(const QString &text) {
    return perform([&] {
        if (text.size() > MaxConfigBytes)
            throw Error("Layout request is too large", "too-large");
        const auto proposal = parseJson(text.toUtf8(), true);
        QHash<QString, QJsonObject> originals;
        std::function<void(const QJsonArray &)> collect = [&](const QJsonArray &list) {
            for (const auto &value : list) {
                const auto node = value.toObject();
                originals[node["id"].toString()] = node;
                collect(node["items"].toArray());
            }
        };
        collect(history[position].nodes);
        QSet<QString> seen;
        std::function<QJsonArray(const QJsonValue &, int)> rebuild = [&](const QJsonValue &list,
                                                                         int depth) {
            if (!list.isArray() || depth > 8 || list.toArray().size() > 200)
                throw Error("Invalid layout size or depth", "invalid");
            QJsonArray result;
            for (const auto &value : list.toArray()) {
                const auto ref = value.toObject();
                const auto id = ref["id"].toString();
                if (!originals.contains(id) || seen.contains(id))
                    throw Error("Unknown or repeated entry", "invalid");
                seen.insert(id);
                auto node = originals[id];
                const bool submenu = node.contains("items");
                if (ref.keys() != (submenu ? QStringList{"id", "items"} : QStringList{"id"}))
                    throw Error("Rearranging cannot change definitions", "invalid");
                if (submenu)
                    node["items"] = rebuild(ref["items"], depth + 1);
                result.append(node);
            }
            return result;
        };
        auto state = history[position];
        if (!proposal.isArray())
            throw Error("Expected layout references", "invalid");
        state.nodes = rebuild(proposal.array(), 0);
        if (seen.size() != originals.size())
            throw Error("The layout is missing entries", "invalid");
        apply(state);
    });
}
bool EditorSession::resetLayout() {
    return perform([&] {
        auto state = history[position];
        state.nodes = nodes(defaults()["menu"].toArray());
        apply(state);
    });
}
void EditorSession::undo() {
    if (canUndo()) {
        --position;
        overwritePreview.reset();
        emit changed();
        emit focusItem(history[position].selection);
    }
}
void EditorSession::redo() {
    if (canRedo()) {
        ++position;
        overwritePreview.reset();
        emit changed();
        emit focusItem(history[position].selection);
    }
}
void EditorSession::selectItem(const QString &id) {
    if (id.isEmpty() || !find(history[position].nodes, id).isEmpty())
        history[position].selection = id;
}
void EditorSession::saved(const Revision &revision) {
    baseline = revision;
    savedConfig = configuration();
    loadFailure.clear();
    external = false;
    overwritePreview.reset();
    emit changed();
    refreshBackups();
}
bool EditorSession::save() {
    return perform([&] {
        if (!loadFailure.isEmpty())
            throw Error("Restore a backup or explicitly overwrite after preserving the unreadable "
                        "configuration",
                        "configuration");
        if (storage.revision() != baseline)
            throw Error("Configuration changed outside this editor; your draft is retained",
                        "conflict");
        if (!dirty() && baseline.content)
            return;
        saved(storage.save(configuration(), baseline));
    });
}
bool EditorSession::reload(bool discard) {
    return perform([&] {
        if (dirty() && !discard)
            throw Error("Save or explicitly discard your draft before reloading", "unsaved");
        const auto current = storage.revision();
        const auto config = decode(current.content);
        reset(config, current);
    });
}
bool EditorSession::checkExternal() {
    try {
        external = storage.revision() != baseline;
        emit messageChanged();
        return true;
    } catch (const Error &failure) {
        message = QString::fromUtf8(failure.what());
        category = failure.code;
        emit messageChanged();
        return false;
    }
}
QString EditorSession::prepareOverwrite() {
    QString result;
    perform([&] {
        overwritePreview = storage.revision();
        result = "If a current file exists, it will be kept as a protected recovery copy.\n\n";
        try {
            result += summary(decode(overwritePreview->content));
        } catch (const Error &failure) {
            result += "Current file is invalid: " + QString::fromUtf8(failure.what());
        }
    });
    return result;
}
bool EditorSession::confirmOverwrite() {
    return perform([&] {
        if (!overwritePreview)
            throw Error("Preview the current file before overwriting", "invalid");
        saved(storage.save(configuration(), *overwritePreview, SaveReason::Overwrite));
    });
}
void EditorSession::refreshBackups() {
    try {
        backupList = storage.backups();
    } catch (const Error &failure) {
        message = QString::fromUtf8(failure.what());
        category = failure.code;
        emit messageChanged();
    }
    emit backupsChanged();
}
QString EditorSession::backupsJson() const {
    QJsonArray rows;
    for (const auto &backup : backupList)
        rows.append(QJsonObject{
            {"name", backup.name},
            {"size", backup.size},
            {"modified", backup.modified.toLocalTime().toString("yyyy-MM-dd HH:mm:ss t")},
            {"protectedCopy", backup.protectedCopy},
            {"valid", backup.valid},
            {"error", backup.error}});
    return QString::fromUtf8(QJsonDocument(rows).toJson(QJsonDocument::Compact));
}
QString EditorSession::backupPreview() const {
    if (!selected)
        return "Select a backup to preview it. Preview never launches commands or changes the "
               "active file.";
    if (!selected->config)
        return selected->name + "\n\n" + selected->error;
    return selected->name + "\n\n" + summary(*selected->config);
}
bool EditorSession::selectBackup(const QString &name) {
    selected.reset();
    emit backupsChanged();
    return perform([&] {
        selected = storage.preview(name);
        emit backupsChanged();
    });
}
bool EditorSession::restoreBackup(bool discardDraft) {
    return perform([&] {
        if (dirty() && !discardDraft)
            throw Error("Save or explicitly discard the current draft before restoring", "unsaved");
        if (!canRestore())
            throw Error("Preview a valid backup before restoring", "invalid");
        const auto config = *selected->config;
        const auto revision = storage.restore(*selected->snapshot, baseline);
        reset(config, revision);
        selected.reset();
        refreshBackups();
    });
}
bool EditorSession::deleteBackup(bool confirmProtected) {
    return perform([&] {
        if (!canDeleteBackup())
            throw Error("Preview a safe backup before deleting", "invalid");
        storage.removeBackup(*selected->snapshot, confirmProtected);
        selected.reset();
        refreshBackups();
    });
}
} // namespace Opm
