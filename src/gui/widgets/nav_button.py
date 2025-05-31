from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt


class NavButton(QPushButton):
    def __init__(self, text):
        super().__init__(text)
        self.setObjectName("navButton")
        self.setCursor(Qt.PointingHandCursor)
