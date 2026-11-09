#pragma once
#include <QJsonArray>
#include <QJsonObject>
namespace Opm {
constexpr int PointerLeaveMinimum = 500;
constexpr int PointerLeaveMaximum = 5000;
constexpr int PointerLeaveStep = 100;
constexpr int PointerLeaveDefault = 1200;
// Entry metadata is independent of visible indexes, labels and icons.
QString defaultAccessKey(const QJsonObject &item);
QJsonArray defaultAccessKeys(const QJsonArray &items, bool reset = false);
void validateAccessKeys(const QJsonArray &items);
int submenuHoverDelay(const QJsonObject &config);
int pointerLeaveDelay(const QJsonObject &config);
}
