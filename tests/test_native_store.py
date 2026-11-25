"""Store-only setup is useful without a backend and cannot execute an installer."""
from pathlib import Path
import os
import subprocess
import sys
import importlib.util
import pytest

ROOT=Path(__file__).resolve().parents[1]
def test_setup_has_retry_and_no_executable_engine():
    source=(ROOT/'plasmoid/contents/ui/BackendSetup.qml').read_text()
    main=(ROOT/'plasmoid/contents/ui/main.qml').read_text()
    assert 'Retry connection' in source and 'retryRequested()' in source
    assert 'widget only' in source and 'native backend' in source
    assert 'onRetryRequested: { root.fetchMenu(); root.fetchIntegration(); }' in main
    for forbidden in ('executable', 'DataSource', 'Process', 'curl ', 'wget ', 'bash '):
        assert forbidden not in source

def test_setup_loads_without_backend():
    if importlib.util.find_spec('PySide6') is None:pytest.skip('Qt test tooling unavailable')
    script='''from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlEngine, QQmlComponent
from PySide6.QtCore import QUrl
import sys
app=QGuiApplication([]); engine=QQmlEngine()
c=QQmlComponent(engine,QUrl.fromLocalFile(sys.argv[1])); obj=c.create()
assert obj is not None, str(c.errors())
count=[]; obj.retryRequested.connect(lambda: count.append(1)); obj.retryRequested.emit()
assert count==[1]
'''
    subprocess.run([sys.executable,'-c',script,str(ROOT/'plasmoid/contents/ui/BackendSetup.qml')],env={**os.environ,'QT_QPA_PLATFORM':'offscreen','QT_QUICK_BACKEND':'software'},check=True)
