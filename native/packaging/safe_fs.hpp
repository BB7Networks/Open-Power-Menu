#pragma once
#include "model.hpp"
#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <algorithm>
#include <cerrno>
#include <cstring>
#include <dirent.h>
#include <fcntl.h>
#include <linux/fs.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>
namespace Opm::Install {
inline void need(bool ok, const QString &what) {
    if (!ok)
        throw Error(what + ": " + QString::fromLocal8Bit(strerror(errno)));
}
struct Fd {
    int n = -1;
    explicit Fd(int fd = -1) : n(fd) {}
    Fd(const Fd &) = delete;
    Fd(Fd &&o) noexcept : n(o.n) { o.n = -1; }
    ~Fd() {
        if (n >= 0)
            ::close(n);
    }
    operator int() const { return n; }
};
inline QByteArray name(const QString &s) {
    if (s.isEmpty() || s == "." || s == ".." || s.contains('/') || s.contains(QChar(0)))
        throw Error("Unsafe component name");
    return QFile::encodeName(s);
}
inline void inspect(const struct stat &s, bool source = false) {
    if ((s.st_uid != getuid() && !(source && s.st_uid == 0)) || (s.st_mode & 0022) ||
        (!S_ISDIR(s.st_mode) && (!S_ISREG(s.st_mode) || s.st_nlink != 1)))
        throw Error("Unsafe owner, permissions, symlink, special file or hard link");
}
inline Fd directory(const QString &path, bool create = false, bool source = false) {
    if (!path.startsWith('/') || QDir::cleanPath(path) != path || path.contains(QChar(0)))
        throw Error("Use a clean absolute installation path");
    Fd fd(open("/", O_RDONLY | O_DIRECTORY | O_CLOEXEC));
    for (const auto &part : path.split('/', Qt::SkipEmptyParts)) {
        const auto p = name(part);
        if (create)
            need(mkdirat(fd, p, 0700) == 0 || errno == EEXIST, "Create directory");
        Fd next(openat(fd, p, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC));
        need(next >= 0, "Open directory without symlinks");
        struct stat st{};
        need(fstat(next, &st) == 0, "Inspect directory");
        if ((st.st_uid != getuid() && st.st_uid != 0) ||
            ((st.st_mode & 0022) && !(st.st_uid == 0 && (st.st_mode & S_ISVTX))))
            throw Error("Unsafe installation ancestor");
        std::swap(fd.n, next.n);
    }
    struct stat st{};
    need(fstat(fd, &st) == 0, "Inspect root");
    inspect(st, source);
    return fd;
}
inline bool exists(int fd, const QString &s) {
    struct stat st{};
    if (fstatat(fd, name(s), &st, AT_SYMLINK_NOFOLLOW) == 0)
        return true;
    need(errno == ENOENT, "Inspect entry");
    return false;
}
inline QStringList entries(int fd) {
    Fd copy(openat(fd, ".", O_RDONLY | O_DIRECTORY | O_CLOEXEC));
    need(copy >= 0, "List directory");
    DIR *dir = fdopendir(copy.n);
    need(dir, "List directory");
    copy.n = -1;
    QStringList out;
    while (true) {
        errno = 0;
        auto *entry = readdir(dir);
        if (!entry) {
            const int error = errno;
            closedir(dir);
            errno = error;
            need(error == 0, "Read directory entries");
            break;
        }
        QString n = QFile::decodeName(entry->d_name);
        if (n != "." && n != "..")
            out << n;
        if (out.size() > 20000) {
            closedir(dir);
            throw Error("Installation directory limit");
        }
    }
    out.sort();
    return out;
}
inline Fd child(int fd, const QString &s, bool source = false) {
    Fd out(openat(fd, name(s), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC));
    need(out >= 0, "Open child directory");
    struct stat st{};
    need(fstat(out, &st) == 0, "Inspect child");
    inspect(st, source);
    return out;
}
inline QByteArray read(int fd, const QString &s, bool source = false) {
    Fd f(openat(fd, name(s), O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC));
    need(f >= 0, "Read file");
    struct stat st{};
    need(fstat(f, &st) == 0, "Inspect file");
    inspect(st, source);
    if (!S_ISREG(st.st_mode) || st.st_size > 128 * 1024 * 1024)
        throw Error("Invalid or oversized installation file");
    QByteArray data;
    char buf[65536];
    ssize_t count;
    while ((count = ::read(f, buf, sizeof(buf))) > 0) {
        data.append(buf, count);
        if (data.size() > 128 * 1024 * 1024)
            throw Error("Oversized file");
    }
    need(count == 0, "Read file content");
    return data;
}
inline void write(int fd, const QString &s, const QByteArray &data, int mode = 0600) {
    Fd f(openat(fd, name(s), O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, mode));
    need(f >= 0, "Create file exclusively");
    qsizetype offset = 0;
    while (offset < data.size()) {
        auto n = ::write(f, data.constData() + offset, data.size() - offset);
        need(n > 0, "Write file");
        offset += n;
    }
    need(fsync(f) == 0, "Sync file");
    need(fsync(fd) == 0, "Sync parent");
}
inline void mkdir(int fd, const QString &s) {
    need(mkdirat(fd, name(s), 0700) == 0, "Create directory");
    need(fsync(fd) == 0, "Sync directory");
}
inline void move(int a, const QString &from, int b, const QString &to, bool replace = false) {
    need(syscall(SYS_renameat2, a, name(from).constData(), b, name(to).constData(),
                 replace ? 0 : RENAME_NOREPLACE) == 0,
         "Rename component");
    need(fsync(a) == 0 && fsync(b) == 0, "Sync rename");
}
inline void remove(int fd, const QString &s) {
    if (!exists(fd, s))
        return;
    struct stat st{};
    need(fstatat(fd, name(s), &st, AT_SYMLINK_NOFOLLOW) == 0, "Inspect removal");
    inspect(st);
    if (S_ISDIR(st.st_mode)) {
        auto d = child(fd, s);
        for (const auto &n : entries(d))
            remove(d, n);
    }
    need(unlinkat(fd, name(s), S_ISDIR(st.st_mode) ? AT_REMOVEDIR : 0) == 0, "Remove component");
    need(fsync(fd) == 0, "Sync removal");
}
inline void copy(int src, const QString &s, int dst, const QString &d, bool source = false,
                 int depth = 0) {
    if (depth > 40)
        throw Error("Installation nesting limit");
    struct stat st{};
    need(fstatat(src, name(s), &st, AT_SYMLINK_NOFOLLOW) == 0, "Inspect copy");
    inspect(st, source);
    if (S_ISDIR(st.st_mode)) {
        mkdir(dst, d);
        auto a = child(src, s, source);
        auto b = child(dst, d);
        for (const auto &n : entries(a))
            copy(a, n, b, n, source, depth + 1);
    } else
        write(dst, d, read(src, s, source), (st.st_mode & 0111) ? 0700 : 0600);
}
inline void inventory(int fd, QJsonObject &out, const QString &prefix = {}, bool source = false,
                      int depth = 0) {
    if (depth > 40 || out.size() > 20000)
        throw Error("Installation tree limit");
    for (const auto &s : entries(fd)) {
        if (out.size() >= 20000)
            throw Error("Installation tree limit");
        struct stat st{};
        need(fstatat(fd, name(s), &st, AT_SYMLINK_NOFOLLOW) == 0, "Inspect inventory");
        inspect(st, source);
        if (S_ISDIR(st.st_mode)) {
            out[prefix + s + '/'] = "directory";
            auto c = child(fd, s, source);
            inventory(c, out, prefix + s + '/', source, depth + 1);
        } else
            out[prefix + s] =
                QString::fromLatin1(
                    QCryptographicHash::hash(read(fd, s, source), QCryptographicHash::Sha256)
                        .toHex()) +
                ((st.st_mode & 0111) ? ":x" : ":r");
    }
}
inline QString digest(int fd, const QString &s) {
    if (!exists(fd, s))
        return {};
    struct stat st{};
    need(fstatat(fd, name(s), &st, AT_SYMLINK_NOFOLLOW) == 0, "Inspect digest");
    inspect(st);
    QByteArray data;
    if (S_ISDIR(st.st_mode)) {
        auto c = child(fd, s);
        QJsonObject tree;
        inventory(c, tree);
        data = QJsonDocument(tree).toJson(QJsonDocument::Compact);
    } else
        data = read(fd, s) + ((st.st_mode & 0111) ? ":x" : ":r");
    return QString::fromLatin1(QCryptographicHash::hash(data, QCryptographicHash::Sha256).toHex());
}
inline QJsonObject json(int fd, const QString &s) {
    return parseJson(read(fd, s), true).object();
}
inline void replaceJson(int fd, const QString &s, const QJsonObject &o) {
    // Only installer-owned journal/receipt names under the held transaction lock.
    const auto temp = s + ".new";
    if (exists(fd, temp))
        remove(fd, temp);
    write(fd, temp, QJsonDocument(o).toJson());
    move(fd, temp, fd, s, true);
}
} // namespace Opm::Install
