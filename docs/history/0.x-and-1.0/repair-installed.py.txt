#!/usr/bin/env python3
"""v0.3.3 -> v0.3.4 QML-only, backup-first repair. No launcher changes."""
from datetime import datetime
from pathlib import Path
import os
import shutil
import tempfile

HERE = Path(__file__).resolve().parent
SRC = HERE / "plasmoid/contents/ui"
DEST = Path.home() / ".local/share/plasma/plasmoids/org.openpowermenu.start/contents/ui"
FILES = ["main.qml", "SideFlyout.qml"]
OLD_MARKERS = {
    "main.qml": ["flyout.visualParent = sourceRow;", "flyout.chooseSide(sourceRow)"],
    "SideFlyout.qml": ["floating: true", "childPopup.chooseSide(row)"],
}


def repair(destination=DEST):
    updates = []
    # Preflight ALL files before making any change.
    for name in FILES:
        target = destination / name
        source = SRC / name
        if not target.is_file():
            raise RuntimeError(f"Missing installed widget file: {target}")
        old = target.read_text()
        new = source.read_text()
        if old == new:
            continue
        if not all(marker in old for marker in OLD_MARKERS[name]):
            raise RuntimeError(f"Unexpected widget version in {name}; no changes made. Use install.sh instead.")
        if "positionAtRow" not in new:
            raise RuntimeError(f"Missing positioning helper in packaged {name}; no changes made.")
        updates.append((target, new))
    if not updates:
        print("v0.3.4 widget files already installed; nothing to change.")
        return 0
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    for target, new in updates:
        backup=target.with_name(target.name+".bak-v033-"+stamp)
        shutil.copy2(target,backup)
        fd,tmp=tempfile.mkstemp(prefix=".opm034-",suffix=".qml",dir=str(target.parent))
        try:
            os.fchmod(fd,target.stat().st_mode & 0o777)
            with os.fdopen(fd,"w") as out:
                out.write(new)
            os.replace(tmp,target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        print(f"Updated {target.name}; backup: {backup}")
    print("QML only updated. Test with QML_DISABLE_DISK_CACHE=1 plasmawindowed org.openpowermenu.start")
    return len(updates)


if __name__ == "__main__":
    try:
        repair()
    except (OSError, RuntimeError) as exc:
        raise SystemExit(str(exc))
