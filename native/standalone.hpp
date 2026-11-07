#pragma once
#include "model.hpp"
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
    explicit Standalone(QJsonObject config, QString theme = {}, bool diagnostics = false);
    int open(const QString &anchor = {});
    bool executeSelection(QAction *action);
    bool pointerTimerActive() const { return leaveTimer.isActive(); }
    bool keyboardNavigation() const { return keyboard; }
    static constexpr int PointerLeaveDelay = 1200;
  signals:
    void diagnostic(const QString &event);
  protected:
    bool eventFilter(QObject *object, QEvent *event) override;
  private:
    const QJsonObject config;
    Model model;
    QJsonArray presentation;
    QHash<QAction *, QString> selections;
    QSet<QMenu *> inside;
    QTimer leaveTimer, focusTimer;
    QElapsedTimer elapsed;
    bool keyboard = false, entered = false, wasActive = false;
    bool traceEnabled, wayland;
    void populate(QMenu *menu, const QJsonArray &entries);
    void updateDismissal();
    void report(const QString &event);
};
} // namespace Opm
