"""A wrapping editor toolbar with history actions aligned to its right edge."""
from math import ceil
from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLayout, QWidget


class EditorToolbar(QWidget):
    def __init__(self, editing, history, parent=None):
        super().__init__(parent)
        self.setObjectName('layoutToolbar')
        self.editing = editing
        self.history = QWidget(self)
        self.history.setObjectName('layoutHistoryControls')
        row = QHBoxLayout(self.history)
        row.setContentsMargins(0, 0, 0, 0)
        for button in history:
            row.addWidget(button)
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(6)
        self.grid.setSizeConstraint(QLayout.SetNoConstraint)
        self._signature = None
        self.reflow()

    def minimumSizeHint(self):
        return QSize(max(self.history.sizeHint().width(), max(b.sizeHint().width() for b in self.editing)), 1)

    def reflow(self):
        widths = tuple(button.sizeHint().width() for button in self.editing)
        history_width = self.history.sizeHint().width()
        signature = (self.width(), widths, history_width)
        if signature == self._signature:
            return
        self._signature = signature
        for widget in self.editing + [self.history]:
            self.grid.removeWidget(widget)
        for column in range(len(self.editing) + 2):
            self.grid.setColumnStretch(column, 0)
        if sum(widths) + history_width + 6 * (len(widths) + 1) <= self.width():
            for column, widget in enumerate(self.editing):
                self.grid.addWidget(widget, 0, column)
            self.grid.setColumnStretch(len(widths), 1)
            self.grid.addWidget(self.history, 0, len(widths) + 1, Qt.AlignRight)
        else:
            columns = max(1, min(len(widths), (self.width() + 6) // (max(widths) + 6)))
            for index, widget in enumerate(self.editing):
                self.grid.addWidget(widget, index // columns, index % columns)
            self.grid.addWidget(self.history, ceil(len(widths) / columns), 0, 1, columns, Qt.AlignRight)
        self.updateGeometry()

    def resizeEvent(self, event):
        self.reflow()
        super().resizeEvent(event)

    def event(self, event):
        if event.type() == QEvent.LayoutRequest and hasattr(self, '_signature'):
            self.reflow()
        return super().event(event)
