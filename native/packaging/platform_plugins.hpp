#pragma once
#include <QString>
namespace Opm::Install {
// Inspect Qt's advertised platform keys; filenames vary across Qt releases.
// Each required backend must still pass Qt's actual library/ABI load checks.
void validatePlatformPlugins(const QString &directory);
}
