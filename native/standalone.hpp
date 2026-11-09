#pragma once
#include "model.hpp"
#include "interaction.hpp"
#include <QElapsedTimer>
#include <QMenu>
#include <QSet>
#include <QTimer>

namespace Opm {
// All geometry is in Qt logical coordinates, including nonzero screen origins.
QPoint menuPosition(const QRect &workArea, const QSize &size, const QPoint &cursor,
                    const QString &anchor);
class Standalone : public QMenu {
    Q_OBJECT
  public:
    explicit Standalone(QJsonObject config, QString theme = {}, bool diagnostics = false,
                        std::shared_ptr<PowerManager> power = powerManager(), std::function<bool()> current = {});
    ~Standalone() override;
    int open(const QString &anchor = {});
    bool executeSelection(QAction *action);
    bool pointerTimerActive() const { return leaveTimer.isActive(); }
    bool keyboardNavigation() const { return keyboard; }
    QString errorMessage() const { return lastError; }
    static constexpr int PointerLeaveDelay = PointerLeaveDefault;
  signals:
    void diagnostic(const QString &event);
  protected:
    bool eventFilter(QObject *object, QEvent *event) override;
  private:
    const QJsonObject config;
    QString lastError;
    Model model;
    QJsonArray presentation;
    Presentation captured;
    std::function<bool()> current;
    QHash<QAction *, QString> selections, accessKeys;
    QSet<QMenu *> inside;
    QTimer leaveTimer, focusTimer;
    QElapsedTimer elapsed;
    bool keyboard = false, entered = false, wasActive = false;
    bool traceEnabled, wayland;
    const bool darkAero;
    void populate(QMenu *menu, const QJsonArray &entries);
    void updateDismissal();
    void report(const QString &event);
};
} // namespace Opm
