#pragma once
#include <QStringList>
namespace Opm {
// Validated model output only. Never accepts a shell command string.
bool launchDetached(QStringList args);
}
