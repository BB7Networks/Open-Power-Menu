#include "model.hpp"
#include <QCoreApplication>
#include <QFile>
#include <QJsonDocument>
#include <QTextStream>
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    try {
        Opm::Model model;
        QJsonArray items;
        if (app.arguments().size() == 2) {
            QFile file(app.arguments()[1]);
            if (!file.open(QIODevice::ReadOnly)) return 2;
            items = Opm::decode(file.readAll())["menu"].toArray();
        } else {
            const auto catalog = Opm::actions();
            for (auto it = catalog.begin(); it != catalog.end(); ++it)
                if (!it.value().toObject().contains("native_power")) items.append(QJsonObject{{"action", it.key()}});
        }
        QJsonArray output;
        for (const auto &item : items) {
            // Never query/execute power operations. This test tool only resolves
            // ordinary application commands, and never launches any command.
            if (Opm::actions()[item.toObject()["action"].toString()].toObject().contains("native_power")) return 2;
            const auto rows = model.normalize(QJsonArray{item}, true);
            if (rows.isEmpty()) return 2;
            output.append(QJsonObject{{"action", item.toObject()["action"]},
                {"argv", QJsonArray::fromStringList(rows.first().argv)}, {"view", rows.first().view}});
        }
        QTextStream(stdout) << QJsonDocument(output).toJson();
    } catch (const Opm::Error &error) { QTextStream(stderr) << error.what(); return 2; }
}
