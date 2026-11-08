"""Real QML leave timer; native cross-window hover delivery needs Plasma."""
import os
from pathlib import Path
import pytest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
pytest.importorskip('PySide6.QtQuick')
from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlEngine, QQmlComponent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

@pytest.fixture
def policy():
    app=QApplication.instance() or QApplication([])
    engine=QQmlEngine()
    source=Path(__file__).resolve().parents[1]/'plasmoid/contents/ui/PointerDismissal.qml'
    component=QQmlComponent(engine,QUrl.fromLocalFile(str(source)))
    obj=component.create()
    assert obj, [str(e) for e in component.errors()]
    assert obj.property('delay')==1200
    obj.setProperty('delay',40)
    calls=[]
    obj.dismissed.connect(lambda: calls.append(True))
    yield obj,calls
    obj.deleteLater(); app.processEvents()


def leave(obj):
    obj.setProperty('menuOpen',True)
    obj.setProperty('pointerInside',True)
    obj.setProperty('pointerInside',False)


def test_disabled_default_then_expiry(policy):
    obj,calls=policy
    leave(obj);QTest.qWait(70);assert not calls
    obj.setProperty('enabled',True)
    QTest.qWait(70);assert calls==[True]


def test_reentry_root_to_child_and_stationary_pointer(policy):
    obj,calls=policy; obj.setProperty('enabled',True)
    leave(obj);QTest.qWait(10)
    obj.setProperty('pointerInside',True) # enter child before crossing grace expires
    QTest.qWait(70);assert not calls and not obj.property('pending')
    obj.setProperty('pointerInside',False);QTest.qWait(70);assert calls==[True]


@pytest.mark.parametrize('protection',['keyboard','editing','closed','disabled'])
def test_cancel_during_protected_interaction(policy,protection):
    obj,calls=policy;obj.setProperty('enabled',True);leave(obj)
    if protection=='keyboard': obj.keyboardUsed()
    elif protection=='editing': obj.setProperty('protectedInteraction',True)
    elif protection=='closed': obj.setProperty('menuOpen',False)
    else: obj.setProperty('enabled',False)
    QTest.qWait(70);assert not calls and not obj.property('pending')
    if protection=='keyboard':
        obj.pointerMoved();QTest.qWait(70);assert calls==[True]


def test_open_outside_waits_until_first_pointer_visit(policy):
    obj,calls=policy;obj.setProperty('enabled',True);obj.setProperty('menuOpen',True)
    QTest.qWait(70);assert not calls
    leave(obj);QTest.qWait(70);assert calls==[True]


@pytest.mark.parametrize('enabled', [False, True])
def test_standalone_menu_leave_policy(monkeypatch, enabled):
    """Exercise the shipped QMenu event filter and its real timer."""
    from PySide6.QtCore import QEvent, QPointF, QTimer, Qt
    from PySide6.QtGui import QEnterEvent, QMouseEvent
    from PySide6.QtWidgets import QMenu
    from openpowermenu import gui
    from openpowermenu.core import DEFAULT_CONFIG

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(gui, 'normalized_menu', lambda *args: [
        {'kind': 'submenu', 'title': 'Tools', 'icon': '', 'items': []}])
    checks = []
    timers = []

    def inspect(event, **details):
        if event != 'show-requested':
            return
        menu = next(w for w in app.topLevelWidgets()
                    if isinstance(w, QMenu) and w.objectName() == 'OpenPowerMenu'
                    and w.isVisible())
        child = menu.actions()[0].menu()
        timer = next(t for t in menu.findChildren(QTimer) if t.interval() == 1200)
        timers.append(timer)
        timer.setInterval(40)

        def send(target, kind):
            if kind == QEvent.Enter:
                event = QEnterEvent(QPointF(1, 1), QPointF(1, 1), QPointF(1, 1))
            elif kind == QEvent.MouseMove:
                event = QMouseEvent(kind, QPointF(1, 1), QPointF(1, 1),
                                    Qt.NoButton, Qt.NoButton, Qt.NoModifier)
            else:
                event = QEvent(kind)
            app.sendEvent(target, event)

        send(menu, QEvent.Enter)
        send(menu, QEvent.Leave)
        child.show()
        send(child, QEvent.Enter)
        QTest.qWait(70)
        checks.append(menu.isVisible())  # child protects the whole menu
        QTest.keyPress(child, Qt.Key_Down)
        send(child, QEvent.Leave)
        QTest.qWait(70)
        checks.append(menu.isVisible())  # keyboard navigation protects it
        # Re-enter with the pointer to resume mouse navigation, then leave.
        send(child, QEvent.Enter)
        send(child, QEvent.MouseMove)
        send(child, QEvent.Leave)
        QTest.qWait(70)
        checks.append(menu.isVisible() is (not enabled))
        child.close()
        menu.close()

    cfg = {**DEFAULT_CONFIG, 'auto_close_on_pointer_leave': enabled}
    assert gui.launch_menu(cfg, diagnostic=inspect) == 0
    assert checks == [True, True, True]
    assert timers and not timers[0].isActive()


def test_delay_change_restarts_full_grace_period(policy):
    obj, calls = policy
    obj.setProperty('enabled', True)
    leave(obj)
    QTest.qWait(20)
    obj.setProperty('delay', 100)
    QTest.qWait(40)
    assert calls == []
    QTest.qWait(90)
    assert calls == [True]


def test_rapid_reopening_cancels_old_timer(policy):
    obj, calls = policy
    obj.setProperty('enabled', True)
    for _ in range(8):
        leave(obj)
        obj.setProperty('menuOpen', False)
        obj.setProperty('menuOpen', True)
    QTest.qWait(70)
    assert calls == []
