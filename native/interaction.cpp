#include "interaction.hpp"
#include "model.hpp"
#include <QHash>
#include <QSet>
#include <cmath>
namespace Opm {
QString defaultAccessKey(const QJsonObject &item) {
    static const QHash<QString, QString> keys{
        {"applications", "P"}, {"power", "O"}, {"logs", "V"}, {"system", "Y"},
        {"hardware", "M"}, {"network", "W"}, {"disks", "K"}, {"terminal", "I"},
        {"monitor", "T"}, {"settings", "N"}, {"files", "E"}, {"run", "R"},
        {"show_desktop", "D"}, {"shutdown", "U"}, {"reboot", "R"}, {"sleep", "S"},
        {"hibernate", "H"}, {"logout", "I"}, {"lock", "L"}};
    if (item.contains("action"))
        return keys.value(item["action"].toString());
    if (item.contains("submenu")) {
        QSet<QString> power;
        for (const auto &child : item["items"].toArray()) {
            const auto action = child.toObject()["action"].toString();
            if (QStringList{"shutdown", "reboot", "logout", "lock", "sleep", "hibernate"}.contains(action))
                power.insert(action);
        }
        // Identify an existing power group by its actions, never its translated title.
        if (power.contains("shutdown") && power.size() >= 2)
            return "U";
    }
    return {};
}
QJsonArray defaultAccessKeys(const QJsonArray &items, bool reset) {
    QSet<QString> reserved;
    QHash<QString, int> candidates;
    for (const auto &value : items) {
        const auto item = value.toObject();
        if (!reset && item.contains("access_key"))
            reserved.insert(item["access_key"].toString().toUpper());
        else
            ++candidates[defaultAccessKey(item)];
    }
    QJsonArray result;
    for (const auto &value : items) {
        auto item = value.toObject();
        if (item.contains("submenu"))
            item["items"] = defaultAccessKeys(item["items"].toArray(), reset);
        if (reset)
            item.remove("access_key");
        if (!item.contains("access_key") && !item.value("separator").toBool()) {
            const auto key = defaultAccessKey(item);
            if (!key.isEmpty() && !reserved.contains(key) && candidates.value(key) == 1)
                item["access_key"] = key;
            // Ambiguous presets stay unbound; migration never overwrites explicit choices.
        }
        result.append(item);
    }
    return result;
}
void validateAccessKeys(const QJsonArray &items) {
    QSet<QString> seen;
    for (const auto &value : items) {
        const auto item = value.toObject();
        if (item.contains("access_key")) {
            const auto key = item["access_key"];
            const auto text = key.toString().toUpper();
            if (!key.isString() || (text.size() != 0 &&
                (text.size() != 1 || !QStringLiteral("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789").contains(text))))
                throw Error("Access keys must be one letter A–Z or digit 0–9, or empty", "invalid");
            if (!text.isEmpty() && seen.contains(text))
                throw Error("Access key " + text + " is already assigned in this menu level", "access-key-collision");
            if (!text.isEmpty())
                seen.insert(text);
        }
        if (item.contains("submenu"))
            validateAccessKeys(item["items"].toArray());
    }
}
int submenuHoverDelay(const QJsonObject &config) {
    const auto value = config.value("submenu_hover_delay_ms");
    if (value.isUndefined()) return -1;
    const double n = value.toDouble(-2);
    if (!value.isDouble() || !std::isfinite(n) || std::floor(n) != n ||
        (n != -1 && (n < 0 || n > 600 || int(n) % 100)))
        throw Error("Submenu hover delay must be -1 (system), 0, or 100–600 ms in 100 ms steps", "invalid");
    return int(n);
}
int pointerLeaveDelay(const QJsonObject &config) {
    const auto value = config.value("auto_close_delay_ms");
    if (value.isUndefined())
        return PointerLeaveDefault;
    const auto number = value.toDouble(-1);
    if (!value.isDouble() || !std::isfinite(number) || std::floor(number) != number ||
        number < PointerLeaveMinimum || number > PointerLeaveMaximum || int(number) % PointerLeaveStep)
        throw Error("Automatic-close delay must be 500–5000 ms in 100 ms steps", "invalid");
    return int(number);
}
}
