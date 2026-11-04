"""Qt internal moves with one validated editor transaction per drop."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QDrag, QUndoCommand
from PySide6.QtWidgets import QAbstractItemView, QTreeWidget


class LayoutChange(QUndoCommand):
    def __init__(self, editor, before, after, label):
        super().__init__(label)
        self.editor, self.before, self.after = editor, before, after

    def undo(self):
        self.editor.apply_layout(self.before)

    def redo(self):
        self.editor.apply_layout(self.after)


class MenuTree(QTreeWidget):
    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.drag_item = None
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropOverwriteMode(False)

    def startDrag(self, supported_actions):
        if self.currentItem() is None:
            return
        # Our drop transaction owns removal/insertion; Qt's default startDrag
        # must not perform a second source removal after a successful move.
        drag = QDrag(self)
        drag.setMimeData(self.mimeData(self.selectedItems()))
        self.drag_item = self.currentItem()
        try:
            drag.exec(Qt.MoveAction)
        finally:
            self.drag_item = None
            self.setState(QAbstractItemView.NoState)
            self.viewport().update()

    def dropEvent(self, event):
        source = self.drag_item or self.currentItem()
        if event.source() is not self or source is None:
            event.ignore()
            return
        target = self.itemAt(event.position().toPoint())
        if self.drop_item(source, target, self.dropIndicatorPosition()):
            event.setDropAction(Qt.MoveAction)
            event.accept()
        else:
            event.ignore()

    def drop_item(self, source, target, position):
        root = self.invisibleRootItem()
        if target is None or position == QAbstractItemView.OnViewport:
            parent, index = root, root.childCount()
        elif position == QAbstractItemView.OnItem:
            if 'submenu' not in target.data(0, Qt.UserRole):
                return False
            parent, index = target, target.childCount()
        else:
            parent = target.parent() or root
            index = parent.indexOfChild(target) + (position == QAbstractItemView.BelowItem)
        return self.editor.relocate(source, parent, index)
