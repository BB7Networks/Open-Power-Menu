"""Real QML trace attribution, including no-ops, external changes and reentrancy."""
import json
import os
from pathlib import Path
import re
import pytest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PySide6.QtQml')
from PySide6.QtCore import QObject, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtWidgets import QApplication

UI = Path(__file__).resolve().parents[1]/'plasmoid/contents/ui'


def test_trace_attribution_and_disabled_gate():
    app = QApplication.instance() or QApplication([])
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    component.setData(b'''
import QtQml
QtObject {
    id: host
    property bool expanded: true
    property bool reenter: false
    property int reads: 0
    property QtObject trace: PopupTrace {
        objectName: "trace"
        snapshot: () => { host.reads++; return {expanded: host.expanded}; }
    }
    onExpandedChanged: {
        trace.expandedChanged();
        if (!expanded && reenter) trace.setExpanded(host, true, "nested-open");
    }
    function request(value) { trace.setExpanded(host, value, "test-request"); }
}
''', QUrl.fromLocalFile(str(UI/'TraceHarness.qml')))
    host = component.create()
    assert host, [str(e) for e in component.errors()]
    trace = host.findChild(QObject, 'trace')
    records = []
    trace.recorded.connect(lambda value: records.append(json.loads(value)))
    host.request(False)
    assert not host.property('expanded') and not records and host.property('reads') == 0
    trace.setProperty('enabled', True)
    host.request(True)
    assert records[-2]['callback'] == 'root.expandedChanged'
    assert records[-2]['details']['origin'] == 'opm'
    assert records[-2]['request']['callback'] == 'test-request'
    host.request(True)  # no-op must not leave an attribution pending
    host.setProperty('expanded', False)
    assert records[-1]['details']['origin'] == 'external-to-opm'
    assert records[-1]['request'] is None
    host.setProperty('expanded', True)
    host.setProperty('reenter', True)
    host.request(False)
    assert host.property('expanded')
    assert records[-2]['request']['callback'] == 'nested-open'
    assert records[-1]['request']['callback'] == 'test-request'
    assert trace.property('currentRequest') is None
    assert all(r['time'].endswith('Z') and r['time_ms'] > 0 for r in records)
    assert [r['sequence'] for r in records] == list(range(1, len(records)+1))
    host.deleteLater(); app.processEvents()


def test_all_opm_expansion_writes_have_callback_attribution():
    source = (UI/'main.qml').read_text()
    code = re.sub(r'//[^\n]*', '', source)
    assert not re.search(r'\bexpanded\s*=(?!=)', code)
    callbacks = re.findall(r'setPowerExpanded\(false, "([^"]+)"\)', code)
    assert len(callbacks) == len(set(callbacks)) == 10
    assert 'onOriginalLauncherOpened.precedence' in callbacks
    assert 'PointerDismissal.dismissed' in callbacks
    trace = (UI/'PopupTrace.qml').read_text()
    assert not any(token in trace for token in ('requestActivate(', 'forceActiveFocus(', 'Timer {'))
