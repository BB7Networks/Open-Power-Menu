#include <QCoreApplication>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSaveFile>
#include <QThread>
#include <unistd.h>

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    const auto args = app.arguments();
    if (args.size() == 3 && args[1] == "--config") {
        QFile launched(args[2] + ".editor-probe");
        return launched.open(QIODevice::WriteOnly) ? 0 : 3;
    }
    if (args.size() < 4)
        return 2;
    QJsonArray descriptors;
    for (int fd = 0; fd < 3; ++fd)
        descriptors.append(QFile::symLinkTarget("/proc/self/fd/" + QString::number(fd)));
    QJsonArray received;
    for (const auto &arg : args.mid(4))
        received.append(arg);
    QFile marker(args[1]);
    if (!marker.open(QIODevice::WriteOnly))
        return 3;
    marker.write(
        QJsonDocument(QJsonObject{{"pid", qint64(::getpid())},
                                  {"pgid", qint64(::getpgrp())},
                                  {"sid", qint64(::getsid(0))},
                                  {"fds", descriptors},
                                  {"args", received},
                                  {"inherited", qEnvironmentVariable("OPM_TEST_INHERITED")}})
            .toJson());
    marker.close();
    for (int count = 1; count < 2000 && !QFile::exists(args[2]); ++count) {
        QSaveFile heartbeat(args[3]);
        if (heartbeat.open(QIODevice::WriteOnly)) {
            heartbeat.write(QByteArray::number(count));
            heartbeat.commit();
        }
        QThread::msleep(10);
    }
    QFile stopped(args[2] + ".ack");
    stopped.open(QIODevice::WriteOnly);
    return 0;
}
