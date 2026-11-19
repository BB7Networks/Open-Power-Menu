#pragma once
#include <QJsonObject>
#include <QStringList>
namespace Opm {
struct DesktopApplication {
    bool registered = false;
    QStringList command;
};
// KDE owns desktop launch semantics (field codes, Terminal, Path, activation).
DesktopApplication desktopApplication(const QJsonObject &candidate);
QStringList preferredApplication(const QString &action);
bool terminalSelectionAvailable(const QString &id);
int applicationPreference(const QJsonObject &candidate);
}
