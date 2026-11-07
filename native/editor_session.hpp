#pragma once
#include "storage.hpp"
#include <QObject>
#include <functional>

namespace Opm {
class EditorSession : public QObject {
    Q_OBJECT
    Q_PROPERTY(QString settingsJson READ settingsJson NOTIFY changed)
    Q_PROPERTY(QString layoutJson READ layoutJson NOTIFY changed)
    Q_PROPERTY(bool dirty READ dirty NOTIFY changed)
    Q_PROPERTY(bool canUndo READ canUndo NOTIFY changed)
    Q_PROPERTY(bool canRedo READ canRedo NOTIFY changed)
    Q_PROPERTY(QString error READ error NOTIFY messageChanged)
    Q_PROPERTY(QString errorCode READ errorCode NOTIFY messageChanged)
    Q_PROPERTY(bool externalChanged READ externalChanged NOTIFY messageChanged)
    Q_PROPERTY(QString backupsJson READ backupsJson NOTIFY backupsChanged)
    Q_PROPERTY(QString backupPreview READ backupPreview NOTIFY backupsChanged)
    Q_PROPERTY(QString selectedBackupName READ selectedBackupName NOTIFY backupsChanged)
    Q_PROPERTY(bool canRestore READ canRestore NOTIFY backupsChanged)
    Q_PROPERTY(bool canDeleteBackup READ canDeleteBackup NOTIFY backupsChanged)
    Q_PROPERTY(bool selectedProtected READ selectedProtected NOTIFY backupsChanged)
    struct State {
        QJsonObject settings;
        QJsonArray nodes;
        QString selection;
    };
    Storage storage;
    Revision baseline;
    QJsonObject savedConfig;
    QList<State> history;
    int position = 0;
    QString token, message, category, loadFailure;
    bool external = false;
    std::optional<Revision> overwritePreview;
    QList<Backup> backupList;
    std::optional<Backup> selected;
    QJsonObject configuration(const State &state) const;
    void apply(State state);
    void reset(const QJsonObject &config, const Revision &revision);
    bool perform(const std::function<void()> &operation);
    void saved(const Revision &revision);

  public:
    explicit EditorSession(Storage source, QObject *parent = nullptr);
    QJsonObject configuration() const { return configuration(history[position]); }
    QString settingsJson() const;
    QString layoutJson() const;
    bool dirty() const;
    bool canUndo() const { return position > 0; }
    bool canRedo() const { return position + 1 < history.size(); }
    QString error() const { return message; }
    QString errorCode() const { return category; }
    bool externalChanged() const { return external; }
    QString backupsJson() const;
    QString backupPreview() const;
    QString selectedBackupName() const { return selected ? selected->name : QString(); }
    bool canRestore() const { return selected && selected->config && selected->snapshot; }
    bool canDeleteBackup() const { return selected && selected->snapshot.has_value(); }
    bool selectedProtected() const { return selected && selected->protectedCopy; }
    Q_INVOKABLE QString itemFields(const QString &id) const;
    Q_INVOKABLE bool preference(const QString &json);
    Q_INVOKABLE bool addItem(const QString &parentId, const QString &beforeId, const QString &json);
    Q_INVOKABLE bool editItem(const QString &id, const QString &json);
    Q_INVOKABLE bool removeItem(const QString &id);
    Q_INVOKABLE bool duplicateItem(const QString &id);
    Q_INVOKABLE bool rearrange(const QString &json);
    Q_INVOKABLE bool resetLayout();
    Q_INVOKABLE void selectItem(const QString &id);
    Q_INVOKABLE void undo();
    Q_INVOKABLE void redo();
    Q_INVOKABLE bool save();
    Q_INVOKABLE bool reload(bool discard = false);
    Q_INVOKABLE bool checkExternal();
    Q_INVOKABLE QString prepareOverwrite();
    Q_INVOKABLE bool confirmOverwrite();
    Q_INVOKABLE void refreshBackups();
    Q_INVOKABLE bool selectBackup(const QString &name);
    Q_INVOKABLE bool restoreBackup(bool discardDraft = false);
    Q_INVOKABLE bool deleteBackup(bool confirmProtected = false);

  signals:
    void changed();
    void focusItem(const QString &id);
    void messageChanged();
    void backupsChanged();
};
} // namespace Opm
