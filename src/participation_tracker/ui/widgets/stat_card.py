from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class StatCard(QFrame):
    def __init__(self, title: str, value: str = "0"):
        super().__init__()
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("font-size: 25px; font-weight: 750; color: #4F46E5;")
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 12px; color: #64748B;")
        layout.addWidget(self.value_label)
        layout.addWidget(self.title_label)

    def set_value(self, value: str | int):
        self.value_label.setText(str(value))
