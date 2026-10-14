from PySide6.QtWidgets import QPushButton


class StudentButton(QPushButton):
    def __init__(self, name: str, parent=None):
        super().__init__(name, parent)
        self.setCursor(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(42)
