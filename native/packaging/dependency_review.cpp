#include "dependency_review.hpp"
#include "safe_fs.hpp"
#include <QProcess>
#include <QProcessEnvironment>
#include <QRegularExpression>
#include <QStandardPaths>
#include <QTextStream>
namespace Opm::Install {
QJsonObject dependencyReview(PackageRunner run, PackageFinder find) {
    if (!find) find = [](const QString &name) { return !QStandardPaths::findExecutable(name).isEmpty(); };
    if (!run) run = [](const QString &program, const QStringList &args) {
        QProcess process;
        auto env = QProcessEnvironment::systemEnvironment();
        env.insert("LC_ALL", "C");
        process.setProcessEnvironment(env);
        process.setStandardInputFile(QProcess::nullDevice());
        process.start(program, args);
        if (!process.waitForFinished(3000)) {
            process.kill(); process.waitForFinished(1000); return PackageQuery{};
        }
        return PackageQuery{process.exitCode(), QString::fromUtf8(process.readAllStandardOutput()).left(65536),
                            process.exitStatus() == QProcess::NormalExit};
    };
    QJsonObject report{{"manager", "unsupported"}, {"installed", false}, {"complete", false},
                       {"recommendation", "Keep PySide6"}};
    QJsonArray packages;
    if (find("pacman")) {
        report["manager"] = "pacman";
        const auto query = run("pacman", {"-Qi", "pyside6"});
        report["complete"] = query.completed && (query.exitCode == 0 || query.exitCode == 1);
        if (query.completed && query.exitCode == 0) {
            report["installed"] = true;
            const auto field = [&](const QString &name) {
                const QRegularExpression pattern("(?:^|\\n)" + name + "[ \\t]*:[ \\t]*([^\\n]*)");
                return pattern.match(query.output).captured(1).trimmed();
            };
            const auto required = field("Required By"), optional = field("Optional For"), reason = field("Install Reason");
            const bool complete = !required.isEmpty() && !optional.isEmpty() && !reason.isEmpty();
            report["complete"] = complete;
            packages.append(QJsonObject{{"name", "pyside6"}, {"install_reason", reason},
                                         {"required_by", required}, {"optional_for", optional}});
            report["review_command"] = "pacman -Qi pyside6";
        }
    } else if (find("dpkg-query")) {
        report["manager"] = "dpkg/apt";
        const auto query = run("dpkg-query", {"-W", "-f=${db:Status-Status}\\t${binary:Package}\\n", "python3-pyside6.*"});
        bool complete = query.completed && (query.exitCode == 0 || query.exitCode == 1);
        const QRegularExpression package("^python3-pyside6\\.[a-z0-9+.-]+(?::[a-z0-9]+)?$");
        QStringList installed;
        for (const auto &line : query.output.split('\n')) {
            const auto fields = line.split('\t');
            if (fields.size() != 2 || fields[0] != "installed") continue;
            const auto name = fields[1];
            if (!package.match(name).hasMatch()) { complete = false; continue; }
            installed.append(name);
            QJsonObject item{{"name", name}};
            if (find("apt-cache") && find("apt-mark")) {
                const auto manual = run("apt-mark", {"showmanual", name});
                const auto required = run("apt-cache", {"rdepends", "--installed", "--important", name});
                const auto optional = run("apt-cache", {"rdepends", "--installed", name});
                complete = complete && manual.completed && !manual.exitCode && required.completed && !required.exitCode && optional.completed && !optional.exitCode;
                item["install_reason"] = manual.completed && !manual.exitCode
                    ? (manual.output.split('\n').contains(name) ? "Explicitly installed" : "Automatic dependency") : "Unknown";
                item["required_by"] = required.output.trimmed();
                item["optional_for"] = optional.output.trimmed();
            } else complete = false;
            packages.append(item);
        }
        report["installed"] = !installed.isEmpty();
        report["complete"] = complete;
        if (!installed.isEmpty())
            report["review_command"] = "apt-get --simulate remove " + installed.join(' ');
    }
    report["packages"] = packages;
    return report;
}
QString dependencyGuidance(const QJsonObject &review) {
    QString text = "Open Power Menu 2.1 runs natively using C++/Qt; Python and PySide6 are not required.\n";
    text += review["installed"].toBool() ? "System PySide6 packages were detected.\n" : "No system PySide6 package was confirmed.\n";
    text += "Keep PySide6 (recommended). Other applications, pip installs and virtual environments may use it; no reverse dependencies is not proof that removal is safe.\n";
    text += "Rollback to OPM 1.0.1 needs its original Python/PySide6 runtime. Restore that runtime before rollback if it was removed.\n";
    if (!review["complete"].toBool()) text += "Package information is incomplete. Keep PySide6.\n";
    text += "Read-only findings:\n" + QString::fromUtf8(QJsonDocument(review).toJson());
    if (review.contains("review_command")) text += "Manual review only (OPM never runs a removal transaction):\n" + review["review_command"].toString() + '\n';
    text += "Instructions: https://github.com/BB7Networks/Open-Power-Menu/blob/feature/native-architecture-v1.1/docs/DEPENDENCY-CLEANUP.md\n";
    return text;
}
static Fd stateDirectory(const QString &root) {
    return directory(root + "/open-power-menu-recovery/dependency-review", true);
}
void reviewDependencies(const QString &root, bool dismiss) {
    if (dismiss) {
        auto state = stateDirectory(root);
        replaceJson(state, "native-2.1.json", {{"suppressed", true}, {"shown", true}});
        QTextStream(stdout) << "Dependency cleanup reminders disabled. PySide6 kept.\n";
    } else QTextStream(stdout) << dependencyGuidance(dependencyReview());
}
void offerDependencyReview(const QString &root, bool upgradedLegacy, std::function<QJsonObject()> discover) {
    if (!upgradedLegacy) return;
    try {
        auto state = stateDirectory(root);
        if (exists(state, "native-2.1.json")) {
            const auto saved = json(state, "native-2.1.json");
            if (saved["shown"].toBool() || saved["suppressed"].toBool()) return;
        }
        const auto review = discover ? discover() : dependencyReview();
        if (!review["installed"].toBool()) return;
        // Persist before presenting; ordinary reinstalls/minor upgrades never repeat it.
        replaceJson(state, "native-2.1.json", {{"shown", true}, {"suppressed", false}});
        auto out = QTextStream(stdout);
        out << "Open Power Menu 2.1 installed successfully.\n"
            << "PySide6 is installed but no longer needed by OPM. Other applications and rollback to 1.0.1 may require it.\n"
            << "Keep PySide6 — default and recommended. No packages will be removed.\n";
        if (isatty(STDIN_FILENO) && isatty(STDOUT_FILENO)) {
            out << "[K] Keep PySide6  [R] Review dependency cleanup  [D] Don't show this again: " << Qt::flush;
            const auto answer = QTextStream(stdin).readLine().trimmed().toUpper();
            if (answer == "R") out << dependencyGuidance(review);
            if (answer == "D") replaceJson(state, "native-2.1.json", {{"shown", true}, {"suppressed", true}});
        } else out << "Review later: open-power-menu --review-dependencies\n";
    } catch (const std::exception &error) {
        QTextStream(stderr) << "Optional dependency review unavailable; native installation succeeded. " << error.what() << '\n';
    }
}
}
