#include "storage.hpp"
#include <QDateTime>
#include <QDebug>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QRegularExpression>
#include <QTimeZone>
#include <QUuid>
#include <algorithm>
#include <cerrno>
#include <chrono>
#include <cstring>
#include <dirent.h>
#include <fcntl.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>

namespace Opm {
namespace {
[[noreturn]] void fail(const char *operation) {
    throw Error(QString::fromLatin1(operation) + ": " +
                QString::fromLocal8Bit(std::strerror(errno)));
}
class Fd {
    int value;

  public:
    explicit Fd(int v = -1) : value(v) {}
    ~Fd() {
        if (value >= 0)
            ::close(value);
    }
    Fd(const Fd &) = delete;
    Fd &operator=(const Fd &) = delete;
    Fd(Fd &&other) noexcept : value(other.value) { other.value = -1; }
    void reset(int next) {
        if (value >= 0)
            ::close(value);
        value = next;
    }
    operator int() const { return value; }
};
Fd parent(const QString &target, bool create) {
    Fd directory(::open("/", O_RDONLY | O_DIRECTORY | O_CLOEXEC));
    if (directory < 0)
        fail("Open root directory");
    const auto parts = QFileInfo(target).absolutePath().split('/', Qt::SkipEmptyParts);
    for (const auto &part : parts) {
        const auto name = QFile::encodeName(part);
        if (create && ::mkdirat(directory, name.constData(), 0700) && errno != EEXIST)
            fail("Create configuration directory");
        const int next =
            ::openat(directory, name.constData(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        if (next < 0) {
            if (!create && errno == ENOENT)
                return Fd();
            fail("Open configuration directory without symlinks");
        }
        directory.reset(next);
    }
    return directory;
}
Revision readAt(int directory, const QByteArray &name) {
    Fd file(::openat(directory, name.constData(), O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC));
    if (file < 0) {
        if (errno == ENOENT)
            return {};
        fail("Open configuration without symlinks");
    }
    struct stat info{};
    if (::fstat(file, &info))
        fail("Inspect configuration");
    if (!S_ISREG(info.st_mode))
        throw Error("Configuration must be a regular file");
    if (info.st_size > MaxConfigBytes)
        throw Error("Configuration exceeds the 4 MiB limit", "too-large");
    QByteArray content;
    char buffer[16384];
    while (true) {
        const auto count = ::read(
            file, buffer, std::min<qint64>(sizeof(buffer), MaxConfigBytes + 1 - content.size()));
        if (count < 0) {
            if (errno == EINTR)
                continue;
            fail("Read configuration");
        }
        if (count == 0)
            break;
        content.append(buffer, count);
        if (content.size() > MaxConfigBytes)
            throw Error("Configuration exceeds the 4 MiB limit", "too-large");
    }
    return {content, info.st_dev, info.st_ino};
}
void writeNew(int directory, const QByteArray &name, const QByteArray &bytes) {
    Fd file(::openat(directory, name.constData(),
                     O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600));
    if (file < 0)
        fail("Create private configuration file");
    try {
        qsizetype offset = 0;
        while (offset < bytes.size()) {
            auto count = ::write(file, bytes.constData() + offset, bytes.size() - offset);
            if (count < 0) {
                if (errno == EINTR)
                    continue;
                fail("Write configuration");
            }
            if (count == 0)
                throw Error("Configuration write made no progress");
            offset += count;
        }
        if (::fsync(file))
            fail("Sync configuration");
    } catch (...) {
        ::unlinkat(directory, name.constData(), 0);
        throw;
    }
}
QByteArray backupName(const QByteArray &name) {
    using namespace std::chrono;
    const auto us = duration_cast<microseconds>(system_clock::now().time_since_epoch()).count();
    const auto stamp = QDateTime::fromSecsSinceEpoch(us / 1000000, QTimeZone("UTC"))
                           .toString("yyyyMMdd'T'HHmmss") +
                       QString::number(us % 1000000).rightJustified(6, '0') + 'Z';
    return name + ".bak-" + stamp.toLatin1();
}
void prune(int directory, const QByteArray &name, int keep) {
    if (keep == 0)
        return;
    // fdopendir owns a duplicate descriptor, leaving the pinned writer usable.
    const int copy = ::fcntl(directory, F_DUPFD_CLOEXEC, 0);
    DIR *stream = copy >= 0 ? ::fdopendir(copy) : nullptr;
    if (!stream) {
        if (copy >= 0)
            ::close(copy);
        qWarning("Could not inspect automatic backup history");
        return;
    }
    QList<QByteArray> names;
    const QRegularExpression pattern("^" + QRegularExpression::escape(QString::fromUtf8(name)) +
                                     "\\.bak-[0-9]{8}T[0-9]{12}Z$");
    while (auto *entry = ::readdir(stream)) {
        const QByteArray candidate(entry->d_name);
        struct stat info{};
        if (pattern.match(QString::fromUtf8(candidate)).hasMatch() &&
            !::fstatat(directory, candidate.constData(), &info, AT_SYMLINK_NOFOLLOW) &&
            S_ISREG(info.st_mode))
            names.append(candidate);
    }
    ::closedir(stream);
    std::sort(names.begin(), names.end(), std::greater<QByteArray>());
    for (qsizetype i = keep; i < names.size(); ++i)
        if (::unlinkat(directory, names[i].constData(), 0))
            qWarning("Could not prune an old automatic backup");
}
} // namespace
Storage::Storage(QString file) {
    if (file.isEmpty()) {
        auto home = qEnvironmentVariable("XDG_CONFIG_HOME");
        if (home.isEmpty())
            home = QDir::homePath() + "/.config";
        file = home + "/open-power-menu/menu.json";
    }
    target = QFileInfo(file).absoluteFilePath();
}
Revision Storage::revision() const {
    auto directory = parent(target, false);
    if (directory < 0)
        return {};
    return readAt(directory, QFile::encodeName(QFileInfo(target).fileName()));
}
void Storage::save(const QJsonObject &config, const Revision &expected) const {
    validate(config);
    const auto payload = QJsonDocument(config).toJson(QJsonDocument::Indented);
    if (payload.size() > MaxConfigBytes)
        throw Error("Configuration exceeds the 4 MiB limit", "too-large");
    auto directory = parent(target, true);
    Fd lock(::openat(directory, ".menu.lock",
                     O_CREAT | O_RDWR | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC, 0600));
    if (lock < 0)
        fail("Open configuration lock");
    struct stat info{};
    if (::fstat(lock, &info))
        fail("Inspect configuration lock");
    if (!S_ISREG(info.st_mode))
        throw Error("Configuration lock must be a regular file");
    // Don't freeze the D-Bus event loop indefinitely behind another editor.
    if (::flock(lock, LOCK_EX | LOCK_NB)) {
        if (errno == EWOULDBLOCK)
            throw Error("Another editor is saving; retry this draft", "busy");
        fail("Lock configuration");
    }
    const auto name = QFile::encodeName(QFileInfo(target).fileName());
    const auto current = readAt(directory, name);
    if (current != expected)
        throw Error("menu.json changed elsewhere; your draft is retained", "conflict");
    const auto temporary =
        ".menu-" + QUuid::createUuid().toString(QUuid::Id128).toLatin1() + ".tmp";
    writeNew(directory, temporary, payload);
    try {
        const auto retention = config["backup_retention"].toInt();
        if (current.content && retention > 0)
            writeNew(directory, backupName(name), *current.content);
        if (readAt(directory, name) != current)
            throw Error("menu.json changed during saving; your draft is retained", "conflict");
        if (::renameat(directory, temporary.constData(), directory, name.constData()))
            fail("Replace configuration atomically");
        if (::fsync(directory))
            qWarning("Configuration saved; directory sync failed");
        prune(directory, name, retention);
    } catch (...) {
        ::unlinkat(directory, temporary.constData(), 0);
        throw;
    }
}
} // namespace Opm
