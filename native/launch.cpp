#include "launch.hpp"
#include <QProcess>
namespace Opm {
bool launchDetached(QStringList args) {
    if (args.isEmpty())
        return false;
    QProcess process;
    process.setProgram(args.takeFirst());
    process.setArguments(args);
    process.setStandardInputFile(QProcess::nullDevice());
    process.setStandardOutputFile(QProcess::nullDevice());
    process.setStandardErrorFile(QProcess::nullDevice());
    return process.startDetached();
}
}
