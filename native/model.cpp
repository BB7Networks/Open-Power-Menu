#include "model.hpp"
#include "interaction.hpp"
#include "launch.hpp"
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonParseError>
#include <QProcess>
#include <QRegularExpression>
#include <QSet>
#include <QStandardPaths>
#include <QStringDecoder>
#include <QUrl>
#include <QVariant>
#include <cmath>
#include <pwd.h>

static void initCatalog() {
    Q_INIT_RESOURCE(catalog);
}
namespace Opm {
static QJsonObject resource(const QString &name) {
    initCatalog();
    QFile file(":/opm/" + name + ".json");
    if (!file.open(QIODevice::ReadOnly))
        throw Error("Missing embedded catalog");
    return QJsonDocument::fromJson(file.readAll()).object();
}
QJsonObject defaults() {
    static const auto value = [] {
        auto config = resource("defaults");
        config["access_keys_enabled"] = true;
        config["show_access_key_hints"] = true;
        config["auto_close_delay_ms"] = PointerLeaveDefault;
        auto menu = config["menu"].toArray();
        for (qsizetype i = 0; i < menu.size(); ++i) {
            auto item = menu[i].toObject();
            if (defaultAccessKey(item) == "U") {
                auto children = item["items"].toArray();
                children.append(QJsonObject{{"action", "sleep"}});
                children.append(QJsonObject{{"action", "hibernate"}});
                item["items"] = children;
                menu[i] = item;
            }
        }
        config["menu"] = defaultAccessKeys(menu);
        return config;
    }();
    return value;
}
QJsonObject actions() {
    static const auto value = [] {
        auto catalog = resource("actions");
        catalog["sleep"] = QJsonObject{{"title", "Sleep"}, {"icon", "system-suspend"}, {"native_power", "sleep"}, {"commands", QJsonArray{}}};
        catalog["hibernate"] = QJsonObject{{"title", "Hibernate"}, {"icon", "system-suspend-hibernate"}, {"native_power", "hibernate"}, {"commands", QJsonArray{}}};
        return catalog;
    }();
    return value;
}

// Qt already validates JSON syntax. This walk additionally rejects duplicate
// layout object fields, including keys written with different Unicode escapes.
class JsonContract {
    const QByteArray &s;
    bool unique;
    qsizetype at = 0;
    void whitespace() {
        while (at < s.size() && QByteArray(" \r\n\t").contains(s[at]))
            ++at;
    }
    QByteArray string() {
        const auto begin = at++;
        while (at < s.size()) {
            if (s[at++] == '\\') {
                ++at;
                continue;
            }
            if (s[at - 1] == '"')
                break;
        }
        return s.mid(begin, at - begin);
    }
    void value(int depth) {
        if (depth > 256)
            throw Error("JSON nesting exceeds the native safety limit");
        whitespace();
        const char kind = s[at];
        if (kind == '"') {
            string();
            return;
        }
        if (kind != '{' && kind != '[') {
            const auto begin = at;
            while (at < s.size() && !QByteArray(",]} \r\n\t").contains(s[at]))
                ++at;
            const auto number = s.mid(begin, at - begin);
            if ((kind == '-' || (kind >= '0' && kind <= '9')) && !number.contains('.') &&
                !number.contains('e') && !number.contains('E')) {
                bool exact = false;
                number.toLongLong(&exact);
                if (!exact)
                    throw Error("Integer exceeds the native signed 64-bit range; configuration was "
                                "not changed");
            }
            return;
        }
        ++at;
        whitespace();
        const char end = kind == '{' ? '}' : ']';
        QSet<QString> keys;
        while (s[at] != end) {
            QString key;
            if (kind == '{') {
                key = QJsonDocument::fromJson("[" + string() + "]").array()[0].toString();
                if (unique && keys.contains(key))
                    throw Error("Repeated layout fields", "invalid");
                keys.insert(key);
                whitespace();
                ++at;
            }
            whitespace();
            const auto begin = at;
            value(depth + 1);
            if (depth == 0 && (key == "backup_retention" || key == "launcher_applet_id")) {
                const auto token = s.mid(begin, at - begin);
                if (token.contains('.') || token.contains('e') || token.contains('E'))
                    throw Error(key + " must be a JSON integer, not a decimal/exponent");
            }
            whitespace();
            if (s[at] == ',') {
                ++at;
                whitespace();
            }
        }
        ++at;
    }

  public:
    JsonContract(const QByteArray &bytes, bool uniqueFields) : s(bytes), unique(uniqueFields) {
        value(0);
    }
};

QJsonDocument parseJson(const QByteArray &bytes, bool uniqueKeys) {
    if (bytes.size() > MaxConfigBytes)
        throw Error("Configuration exceeds the 4 MiB limit", "too-large");
    QStringDecoder utf8(QStringDecoder::Utf8);
    const QString text = utf8(bytes);
    if (utf8.hasError())
        throw Error("Configuration must contain valid UTF-8 JSON");
    QJsonParseError error;
    auto result = QJsonDocument::fromJson(text.toUtf8(), &error);
    if (error.error != QJsonParseError::NoError)
        throw Error("Invalid configuration JSON: " + error.errorString());
    JsonContract check(text.toUtf8(), uniqueKeys);
    return result;
}
static bool truth(const QJsonValue &v) {
    if (v.isNull() || v.isUndefined())
        return false;
    if (v.isBool())
        return v.toBool();
    if (v.isString())
        return !v.toString().isEmpty();
    if (v.isArray())
        return !v.toArray().isEmpty();
    if (v.isObject())
        return !v.toObject().isEmpty();
    return v.toDouble() != 0;
}
static QString textValue(const QJsonValue &v) {
    if (v.isString())
        return v.toString();
    if (v.isBool())
        return v.toBool() ? "True" : "False";
    if (v.isNull())
        return "None";
    if (v.isDouble())
        return QString::number(v.toDouble(), 'g', 16);
    return {};
}
static QString label(const QJsonObject &object, const QString &key, const QString &fallback) {
    return truth(object[key]) ? textValue(object[key]) : fallback;
}
static void requirements(const QJsonObject &spec) {
    for (const auto &key : {"requires", "desktops"}) {
        const auto value = spec[key];
        if (value.isNull() || value.isUndefined())
            continue;
        if (!value.isArray())
            throw Error(QString(key) + " must be an array of names");
        for (const auto &part : value.toArray())
            if (!part.isString() || part.toString().isEmpty() || part.toString().contains(QChar(0)))
                throw Error(QString(key) + " must contain nonempty names");
    }
    if (spec.contains("kcm") && (!spec["kcm"].isString() || spec["kcm"].toString().isEmpty()))
        throw Error("kcm must be a module name");
}
static QStringList argv(const QJsonValue &candidate, bool expand) {
    const auto raw = candidate.isObject() ? candidate.toObject()["argv"] : candidate;
    if (!raw.isArray() || raw.toArray().isEmpty())
        throw Error("Commands must be nonempty argument arrays");
    QStringList result;
    for (const auto &part : raw.toArray()) {
        if (!part.isString() || part.toString().isEmpty() || part.toString().contains(QChar(0)))
            throw Error("Command arguments must be nonempty strings without NUL");
        result.append(expand ? expandPart(part.toString()) : part.toString());
    }
    return result;
}
static void validateMenu(const QJsonValue &items, int depth = 0) {
    if (depth > 8 || !items.isArray() || items.toArray().size() > 200)
        throw Error("Keep at most eight submenu levels and 200 entries per menu");
    for (const auto &value : items.toArray()) {
        if (!value.isObject())
            throw Error("Menu entries must be objects");
        const auto item = value.toObject();
        if (item["separator"] == QJsonValue(true))
            continue;
        if (item.contains("submenu")) {
            if (!item["submenu"].isString() || item["submenu"].toString().trimmed().isEmpty())
                throw Error("Every submenu needs a name");
            validateMenu(item["items"], depth + 1);
        } else if (item.contains("action")) {
            if (!item["action"].isString() || !actions().contains(item["action"].toString()))
                throw Error("Unknown built-in action");
        } else {
            const auto candidates = item.contains("command")
                                        ? QJsonValue(QJsonArray{item["command"]})
                                        : item["commands"];
            if (!candidates.isArray() || candidates.toArray().isEmpty())
                throw Error("Custom entries need argument-array commands");
            requirements(item);
            for (const auto &candidate : candidates.toArray()) {
                argv(candidate, false);
                if (candidate.isObject())
                    requirements(candidate.toObject());
            }
        }
    }
}
void validate(const QJsonObject &config) {
    for (const auto &key :
         {"auto_close_on_pointer_leave", "show_menu_icons", "hide_original_launcher"})
        if (!config[key].isBool())
            throw Error(QString(key) + " must be a boolean");
    if (!QStringList{"native", "aero"}.contains(config["appearance"].toString()))
        throw Error("Invalid appearance");
    if (!QStringList{"cursor", "bottom-left", "bottom-right"}.contains(config["anchor"].toString()))
        throw Error("Invalid anchor");
    for (const auto &key : {"backup_retention", "launcher_applet_id"}) {
        const auto v = config[key];
        const double n = v.toDouble(-1);
        const double maximum = QString(key) == "backup_retention" ? 1000 : 2147483647;
        if (!v.isDouble() || v.toVariant().typeId() != QMetaType::LongLong || n < 0 ||
            n > maximum || std::floor(n) != n)
            throw Error(QString(key) + " must be an integer in range");
    }
    if (!QStringList{"launcher", "custom"}.contains(config["button_icon_mode"].toString()))
        throw Error("Invalid button icon mode");
    const auto icon = config["button_icon"].toString();
    if (!config["button_icon"].isString() || icon.size() > 512 || icon.contains(QChar(0)))
        throw Error("Invalid button icon");
    static const QRegularExpression theme("^[A-Za-z0-9][A-Za-z0-9_.+\\-]{0,127}$");
    if (!icon.isEmpty() && !theme.match(icon).hasMatch()) {
        QString path = icon;
        if (icon.startsWith("file://")) {
            const QUrl url(icon);
            if (!url.isValid() || url.scheme() != "file" ||
                (!url.host().isEmpty() && url.host() != "localhost") || url.hasQuery() ||
                url.hasFragment())
                throw Error("Only local image URLs are supported");
            path = url.path(QUrl::FullyDecoded);
        }
        if (!path.startsWith('/') ||
            !QStringList{"png", "svg", "svgz", "jpg", "jpeg", "webp", "ico"}.contains(
                QFileInfo(path).suffix().toLower()))
            throw Error("Use a theme icon or absolute local image path");
    }
    for (const auto &key : {"access_keys_enabled", "show_access_key_hints"})
        if (config.contains(key) && !config[key].isBool())
            throw Error(QString(key) + " must be a boolean");
    pointerLeaveDelay(config);
    validateMenu(config["menu"]);
    validateAccessKeys(config["menu"].toArray());
}
QJsonObject decode(const std::optional<QByteArray> &bytes) {
    auto result = defaults();
    if (bytes) {
        const auto document = parseJson(*bytes);
        if (!document.isObject() || !document.object()["menu"].isArray())
            throw Error("Configuration must contain a menu array");
        const auto custom = document.object();
        for (auto it = custom.begin(); it != custom.end(); ++it)
            result[it.key()] = it.value();
    }
    validate(result); // Reject malformed trees before applying migration defaults.
    result["menu"] = defaultAccessKeys(result["menu"].toArray());
    validate(result);
    return result;
}
QJsonObject integration(const QJsonObject &config) {
    QJsonObject result;
    for (const auto &key :
         {"hide_original_launcher", "launcher_applet_id", "button_icon_mode", "button_icon",
          "appearance", "show_menu_icons", "auto_close_on_pointer_leave",
          "auto_close_delay_ms", "access_keys_enabled", "show_access_key_hints"})
        result[key] = config[key];
    return result;
}
QString expandPart(QString value) {
    value.replace("{home}", QDir::homePath());
    if (value.startsWith('~')) {
        const auto end = value.indexOf('/');
        const auto user = value.mid(1, end < 0 ? -1 : end - 1);
        QString home;
        if (user.isEmpty())
            home = QDir::homePath();
        else if (auto *entry = getpwnam(user.toLocal8Bit().constData()))
            home = QFile::decodeName(entry->pw_dir);
        if (!home.isEmpty())
            value = home + (end < 0 ? QString() : value.mid(end));
    }
    static const QRegularExpression vars("\\$(?:\\{([^}]+)\\}|([A-Za-z0-9_]+))");
    QString output;
    qsizetype start = 0;
    auto matches = vars.globalMatch(value);
    while (matches.hasNext()) {
        auto match = matches.next();
        output += value.mid(start, match.capturedStart() - start);
        const auto key =
            (match.captured(1).isEmpty() ? match.captured(2) : match.captured(1)).toLocal8Bit();
        output += qEnvironmentVariableIsSet(key.constData()) ? qEnvironmentVariable(key.constData())
                                                             : match.captured();
        start = match.capturedEnd();
    }
    return output + value.mid(start);
}
static bool executable(const QString &name) {
    if (!name.contains('/'))
        return !QStandardPaths::findExecutable(name).isEmpty();
    for (const auto &candidate : {name, expandPart(name)}) {
        QFileInfo file(candidate);
        if (file.isFile() && file.isExecutable())
            return true;
    }
    return false;
}
static bool desktop(const QJsonValue &allowed) {
    if (!truth(allowed))
        return true;
    const auto current =
        qEnvironmentVariable("XDG_CURRENT_DESKTOP").toUpper().replace(';', ':').split(':');
    for (const auto &item : allowed.toArray())
        if (current.contains(item.toString().toUpper()))
            return true;
    return false;
}
QString Model::probe(const QString &program, const QStringList &arguments) {
    const auto key = program + QChar(0) + arguments.join(QChar(0));
    const auto now = QDateTime::currentMSecsSinceEpoch();
    if (probes.contains(key) && probes[key].expires > now)
        return probes[key].output;
    QProcess process;
    process.setProgram(program);
    process.setArguments(arguments);
    process.setStandardInputFile(QProcess::nullDevice());
    process.setStandardErrorFile(QProcess::nullDevice());
    process.start();
    QString output;
    if (process.waitForFinished(2000) && process.exitStatus() == QProcess::NormalExit &&
        process.exitCode() == 0)
        output = QString::fromUtf8(process.readAllStandardOutput());
    else {
        process.kill();
        process.waitForFinished(1000);
    }
    if (probes.size() >= 32)
        probes.clear();
    probes.insert(key, {now + 30000, output});
    return output;
}
QStringList Model::resolve(const QJsonObject &spec, bool expand) {
    if (!desktop(spec["desktops"]))
        return {};
    if (spec.contains("requires") && !spec["requires"].isArray())
        throw Error("requires must be an array of names");
    if (truth(spec["path_required"]) && !spec["path_required"].isString())
        throw Error("path_required must be a path string");
    if (truth(spec["path_required"]) &&
        !QFileInfo::exists(expandPart(spec["path_required"].toString())))
        return {};
    for (const auto &required : spec["requires"].toArray())
        if (!executable(required.toString()))
            return {};
    const auto candidates =
        spec.contains("command") ? QJsonArray{spec["command"]} : spec["commands"].toArray();
    for (const auto &candidate : candidates) {
        auto args = argv(candidate, expand);
        if (!executable(args[0]))
            continue;
        const auto options = candidate.toObject();
        if (!desktop(options["desktops"]))
            continue;
        if (options.contains("requires") && !options["requires"].isArray())
            throw Error("requires must be an array of names");
        bool available = true;
        for (const auto &required : options["requires"].toArray())
            if (!executable(required.toString()))
                available = false;
        if (!available)
            continue;
        if (truth(options["kwin_shortcut"])) {
            if (!options["kwin_shortcut"].isString())
                throw Error("kwin_shortcut must be an action name");
            auto lines = probe(args[0], {"org.kde.kglobalaccel", "/component/kwin",
                                         "org.kde.kglobalaccel.Component.shortcutNames"})
                             .split('\n');
            if (!lines.contains(options["kwin_shortcut"].toString()))
                continue;
        }
        if (truth(options["kcm"])) {
            if (!executable("kcmshell6"))
                continue;
            bool found = false;
            for (const auto &line : probe("kcmshell6", {"--list"}).split('\n'))
                if (line.simplified().section(' ', 0, 0) == options["kcm"].toString())
                    found = true;
            if (!found)
                continue;
        }
        return args;
    }
    return {};
}
QList<Entry> Model::normalize(const QJsonArray &items, bool showUnavailable) {
    QList<Entry> result;
    for (const auto &value : items) {
        const auto item = value.toObject();
        Entry entry;
        if (truth(item["separator"])) {
            if (result.isEmpty() || result.last().view["kind"] == "separator")
                continue;
            entry.view = {{"kind", "separator"}};
        } else if (item.contains("submenu")) {
            entry.children = normalize(item["items"].toArray(), showUnavailable);
            if (entry.children.isEmpty())
                continue;
            entry.view = {{"kind", "submenu"},
                          {"title", item["submenu"]},
                          {"icon", item.contains("icon") ? textValue(item["icon"]) : QString()}};
        } else {
            const bool builtin = item.contains("action");
            const auto spec = builtin ? actions()[item["action"].toString()].toObject() : item;
            PowerAvailability powerState;
            if (builtin && spec.contains("native_power")) {
                entry.powerAction = spec["native_power"].toString();
                powerState = power->capability(entry.powerAction);
            } else
                entry.argv = resolve(spec, builtin || !truth(item["desktop_file"]));
            const bool enabled = !entry.argv.isEmpty() || powerState.available;
            if (!enabled && !showUnavailable)
                continue;
            const auto title = builtin ? label(item, "label", spec["title"].toString())
                                       : (item.contains("label") ? textValue(item["label"])
                                                                 : QString("Custom command"));
            entry.view = {
                {"kind", "command"},
                {"title", title},
                {"icon", label(item, "icon", builtin ? spec["icon"].toString() : "system-run")},
                {"enabled", enabled},
                {"close_before_run", item["action"] == "show_desktop"}};
            if (!entry.powerAction.isEmpty() && !powerState.available)
                entry.view["unavailable_reason"] = powerState.reason;
        }
        if (entry.view["kind"] != "separator" && !item["access_key"].toString().isEmpty())
            entry.view["access_key"] = item["access_key"].toString().toUpper();
        result.append(entry);
    }
    while (!result.isEmpty() && result.last().view["kind"] == "separator")
        result.removeLast();
    return result;
}
static QJsonArray present(const QList<Entry> &entries, const QString &prefix = {}, bool enabled = true, bool hints = true) {
    QJsonArray result;
    for (qsizetype i = 0; i < entries.size(); ++i) {
        auto view = entries[i].view;
        const auto key = prefix + QString::number(i);
        view["key"] = key;
        if (!enabled)
            view.remove("access_key");
        if (hints && view.contains("access_key"))
            view["access_hint"] = view.value("access_key");
        if (view["kind"] == "submenu")
            view["items"] = present(entries[i].children, key + '.', enabled, hints);
        result.append(view);
    }
    return result;
}
QJsonArray Model::publicMenu(const QJsonObject &config) {
    return present(normalize(config["menu"].toArray(), truth(config["show_unavailable"])), {},
                   config["access_keys_enabled"].toBool(true), config["show_access_key_hints"].toBool(true));
}
std::optional<Entry> Model::selection(const QJsonObject &config, const QString &key,
                                      const QJsonArray *expectedPresentation) {
    static const QRegularExpression pattern("^[0-9]{1,5}(?:\\.[0-9]{1,5}){0,11}$");
    if (key.size() > 128 || !pattern.match(key).hasMatch())
        return {};
    auto tree = normalize(config["menu"].toArray(), truth(config["show_unavailable"]));
    if (expectedPresentation && present(tree, {}, config["access_keys_enabled"].toBool(true),
                                        config["show_access_key_hints"].toBool(true)) != *expectedPresentation)
        return {};
    auto parts = key.split('.');
    for (qsizetype n = 0; n < parts.size(); ++n) {
        const auto i = parts[n].toInt();
        if (i >= tree.size())
            return {};
        const auto entry = tree[i];
        if (n == parts.size() - 1)
            return entry;
        if (entry.view["kind"] != "submenu")
            return {};
        tree = entry.children;
    }
    return {};
}
QStringList Model::command(const QJsonObject &config, const QString &key, const QJsonArray *expected) {
    const auto entry = selection(config, key, expected);
    return entry ? entry->argv : QStringList{};
}
bool Model::execute(const QJsonObject &config, const QString &key, const QJsonArray *expected) {
    const auto entry = selection(config, key, expected);
    if (!entry || !entry->view["enabled"].toBool()) return false;
    if (!entry->powerAction.isEmpty()) {
        power->execute(entry->powerAction);
        return true;
    }
    return launchDetached(entry->argv);
}
} // namespace Opm
