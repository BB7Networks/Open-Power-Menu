#pragma once
#include <QJsonObject>
#include <QStringList>
#include <functional>
namespace Opm::Install {
struct PackageQuery { int exitCode = -1; QString output; bool completed = false; };
using PackageRunner = std::function<PackageQuery(const QString &, const QStringList &)>;
using PackageFinder = std::function<bool(const QString &)>;
QJsonObject dependencyReview(PackageRunner runner = {}, PackageFinder finder = {});
QString dependencyGuidance(const QJsonObject &review);
// Optional, post-commit work. This never throws into the installation transaction.
void offerDependencyReview(const QString &dataRoot, bool upgradedLegacy, std::function<QJsonObject()> discover = {});
void reviewDependencies(const QString &dataRoot, bool dismiss = false);
}
