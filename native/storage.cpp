#include "storage.hpp"
#include <QCryptographicHash>
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
#include <functional>
#include <sys/file.h>
#include <sys/stat.h>
#include <tuple>
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
Revision writeNew(int directory, const QByteArray &name, const QByteArray &bytes) {
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
        struct stat info{};
        if (::fstat(file, &info))
            fail("Inspect saved configuration");
        return {bytes, info.st_dev, info.st_ino};
    } catch (...) {
        ::unlinkat(directory, name.constData(), 0);
        throw;
    }
}
QByteArray backupName(const QByteArray &name, const QByteArray &suffix = ".bak-") {
    using namespace std::chrono;
    const auto us = duration_cast<microseconds>(system_clock::now().time_since_epoch()).count();
    const auto stamp = QDateTime::fromSecsSinceEpoch(us / 1000000, QTimeZone("UTC"))
                           .toString("yyyyMMdd'T'HHmmss") +
                       QString::number(us % 1000000).rightJustified(6, '0') + 'Z';
    return name + suffix + stamp.toLatin1();
}
void prune(int directory, const QByteArray &name, int keep, const QString &protectedName = {}) {
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
        if (QString::fromUtf8(names[i]) != protectedName &&
            ::unlinkat(directory, names[i].constData(), 0))
            qWarning("Could not prune an old automatic backup");
}

Fd writerLock(int directory) {
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
    return lock;
}
bool backupNameAllowed(const QByteArray &base, const QString &name) {
    return !name.isEmpty() && !name.contains('/') && !name.contains(QChar(0)) &&
           (name.startsWith(QString::fromUtf8(base) + ".bak-") ||
            name.startsWith(QString::fromUtf8(base) + ".pre-restore-") ||
            name.startsWith(QString::fromUtf8(base) + ".pre-overwrite-"));
}
bool protectedBackup(const QByteArray &base, const QString &name) {
    return name.startsWith(QString::fromUtf8(base) + ".pre-restore-") ||
           name.startsWith(QString::fromUtf8(base) + ".pre-overwrite-");
}
struct BackupRead {
    BackupSnapshot snapshot;
    std::optional<QByteArray> bytes;
};
BackupRead readBackup(int directory, const QString &name) {
    struct stat parentInfo{};
    if (::fstat(directory, &parentInfo))
        fail("Inspect backup directory");
    if (parentInfo.st_uid != ::getuid() || (parentInfo.st_mode & 0022))
        throw Error("The backup directory must be owned by you and not writable by other users",
                    "unsafe");
    const auto fileName = QFile::encodeName(name);
    Fd file(
        ::openat(directory, fileName.constData(), O_RDONLY | O_NONBLOCK | O_NOFOLLOW | O_CLOEXEC));
    if (file < 0)
        fail("Open selected backup without symlinks");
    const auto fingerprint = [&](const struct stat &info) {
        if (!S_ISREG(info.st_mode) || info.st_uid != ::getuid() || info.st_nlink != 1)
            throw Error("Only your own regular backup files are supported; links are refused",
                        "unsafe");
        BackupSnapshot value;
        value.name = name;
        value.directoryDevice = parentInfo.st_dev;
        value.directoryInode = parentInfo.st_ino;
        value.device = info.st_dev;
        value.inode = info.st_ino;
        value.size = info.st_size;
        value.modifiedNs = qint64(info.st_mtim.tv_sec) * 1000000000 + info.st_mtim.tv_nsec;
        value.changedNs = qint64(info.st_ctim.tv_sec) * 1000000000 + info.st_ctim.tv_nsec;
        return value;
    };
    struct stat info{};
    if (::fstat(file, &info))
        fail("Inspect backup");
    auto before = fingerprint(info);
    std::optional<QByteArray> bytes;
    if (info.st_size <= MaxConfigBytes) {
        bytes = QByteArray();
        char buffer[16384];
        while (true) {
            const auto count = ::read(
                file, buffer, std::min<qint64>(sizeof(buffer), MaxConfigBytes + 1 - bytes->size()));
            if (count < 0) {
                if (errno == EINTR)
                    continue;
                fail("Read backup");
            }
            if (count == 0)
                break;
            bytes->append(buffer, count);
            if (bytes->size() > MaxConfigBytes)
                throw Error("Backup changed during preview", "conflict");
        }
    }
    if (::fstat(file, &info))
        fail("Recheck backup");
    if (fingerprint(info) != before)
        throw Error("Backup changed during preview; refresh it", "conflict");
    if (::fstatat(directory, fileName.constData(), &info, AT_SYMLINK_NOFOLLOW) ||
        fingerprint(info) != before)
        throw Error("Backup changed during preview; refresh it", "conflict");
    if (bytes)
        before.digest = QCryptographicHash::hash(*bytes, QCryptographicHash::Sha256);
    return {before, bytes};
}
Backup previewAt(int directory, const QByteArray &base, const QString &name) {
    if (!backupNameAllowed(base, name))
        throw Error("Select a backup inside the configuration directory", "invalid");
    Backup result;
    result.name = name;
    result.protectedCopy = protectedBackup(base, name);
    struct stat info{};
    if (!::fstatat(directory, QFile::encodeName(name).constData(), &info, AT_SYMLINK_NOFOLLOW)) {
        result.size = info.st_size;
        result.modified = QDateTime::fromMSecsSinceEpoch(qint64(info.st_mtim.tv_sec) * 1000 +
                                                         info.st_mtim.tv_nsec / 1000000);
    }
    try {
        const auto read = readBackup(directory, name);
        result.snapshot = read.snapshot;
        if (!read.bytes)
            throw Error("Backup exceeds the 4 MiB limit; it can be deleted but not restored",
                        "too-large");
        result.config = decode(read.bytes);
        result.valid = true;
    } catch (const Error &error) {
        result.error = QString::fromUtf8(error.what());
    }
    return result;
}
Revision writeAt(int directory, const QByteArray &name, const QJsonObject &config,
                 const Revision &expected, const QByteArray &recoverySuffix = {},
                 const QString &protectedName = {}, const std::function<void()> &checkSource = {}) {
    validate(config);
    const auto payload = QJsonDocument(config).toJson(QJsonDocument::Indented);
    if (payload.size() > MaxConfigBytes)
        throw Error("Configuration exceeds the 4 MiB limit", "too-large");
    const auto current = readAt(directory, name);
    if (current != expected)
        throw Error("menu.json changed elsewhere; your draft is retained", "conflict");
    const auto temporary =
        ".menu-" + QUuid::createUuid().toString(QUuid::Id128).toLatin1() + ".tmp";
    const auto saved = writeNew(directory, temporary, payload);
    try {
        const auto retention = config["backup_retention"].toInt();
        if (current.content && (retention > 0 || !recoverySuffix.isEmpty()))
            writeNew(
                directory,
                backupName(name, recoverySuffix.isEmpty() ? QByteArray(".bak-") : recoverySuffix),
                *current.content);
        if (checkSource)
            checkSource();
        if (readAt(directory, name) != current)
            throw Error("menu.json changed during saving; your draft is retained", "conflict");
        if (::renameat(directory, temporary.constData(), directory, name.constData()))
            fail("Replace configuration atomically");
        if (::fsync(directory))
            qWarning("Configuration saved; directory sync failed");
        prune(directory, name, retention, protectedName);
        return saved;
    } catch (...) {
        ::unlinkat(directory, temporary.constData(), 0);
        throw;
    }
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
Revision Storage::save(const QJsonObject &config, const Revision &expected,
                       SaveReason reason) const {
    validate(config);
    auto directory = parent(target, true);
    const auto lock = writerLock(directory);
    return writeAt(directory, QFile::encodeName(QFileInfo(target).fileName()), config, expected,
                   reason == SaveReason::Overwrite ? QByteArray(".pre-overwrite-") : QByteArray());
}
bool BackupSnapshot::operator==(const BackupSnapshot &other) const {
    return std::tie(name, directoryDevice, directoryInode, device, inode, size, modifiedNs,
                    changedNs, digest) ==
           std::tie(other.name, other.directoryDevice, other.directoryInode, other.device,
                    other.inode, other.size, other.modifiedNs, other.changedNs, other.digest);
}
QList<Backup> Storage::backups() const {
    auto directory = parent(target, false);
    if (directory < 0)
        return {};
    const auto base = QFile::encodeName(QFileInfo(target).fileName());
    const int copy = ::fcntl(directory, F_DUPFD_CLOEXEC, 0);
    DIR *stream = copy >= 0 ? ::fdopendir(copy) : nullptr;
    if (!stream) {
        if (copy >= 0)
            ::close(copy);
        fail("List configuration backups");
    }
    QStringList names;
    while (auto *entry = ::readdir(stream)) {
        const auto name = QFile::decodeName(entry->d_name);
        if (backupNameAllowed(base, name))
            names.append(name);
    }
    ::closedir(stream);
    QList<Backup> result;
    for (const auto &name : names) {
        auto backup = previewAt(directory, base, name);
        // Keep history metadata only. A large retention limit must not retain
        // every decoded configuration in the editor's memory.
        backup.config.reset();
        result.append(std::move(backup));
    }
    std::sort(result.begin(), result.end(), [](const Backup &a, const Backup &b) {
        return a.modified == b.modified ? a.name > b.name : a.modified > b.modified;
    });
    return result;
}
Backup Storage::preview(const QString &name) const {
    auto directory = parent(target, false);
    if (directory < 0)
        throw Error("The backup directory is unavailable", "missing");
    return previewAt(directory, QFile::encodeName(QFileInfo(target).fileName()), name);
}
Revision Storage::restore(const BackupSnapshot &source, const Revision &expected) const {
    const auto base = QFile::encodeName(QFileInfo(target).fileName());
    if (!backupNameAllowed(base, source.name))
        throw Error("Select and preview a configuration backup", "invalid");
    auto directory = parent(target, false);
    if (directory < 0)
        throw Error("The backup directory is unavailable", "missing");
    const auto lock = writerLock(directory);
    const auto read = readBackup(directory, source.name);
    if (read.snapshot != source)
        throw Error("The selected backup changed; preview it again", "conflict");
    if (!read.bytes)
        throw Error("Backup exceeds the 4 MiB limit", "too-large");
    const auto config = decode(read.bytes);
    return writeAt(directory, base, config, expected, ".pre-restore-", source.name, [&] {
        if (readBackup(directory, source.name).snapshot != source)
            throw Error("The selected backup changed during restoration; preview it again",
                        "conflict");
    });
}
void Storage::removeBackup(const BackupSnapshot &source, bool confirmProtected) const {
    const auto base = QFile::encodeName(QFileInfo(target).fileName());
    if (!backupNameAllowed(base, source.name))
        throw Error("Select and preview a configuration backup", "invalid");
    if (protectedBackup(base, source.name) && !confirmProtected)
        throw Error("Confirm deletion of this protected recovery copy", "protected");
    auto directory = parent(target, false);
    if (directory < 0)
        throw Error("The backup directory is unavailable", "missing");
    const auto lock = writerLock(directory);
    if (readBackup(directory, source.name).snapshot != source)
        throw Error("The selected backup changed; preview it again", "conflict");
    if (::unlinkat(directory, QFile::encodeName(source.name).constData(), 0))
        fail("Delete selected backup");
    if (::fsync(directory))
        qWarning("Backup deleted; directory sync failed");
}
} // namespace Opm
