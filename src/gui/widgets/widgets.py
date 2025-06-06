from PySide6.QtWidgets import QPushButton, QWidget, QLabel, QHBoxLayout, QSizePolicy
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from typing import Optional
from pathlib import Path

class NavButton(QPushButton):
    def __init__(self, text):
        super().__init__(text)
        self.setObjectName("navButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

class LabelIcon(QWidget):
    def __init__(self, icon: Optional[QIcon] = None, text: str = ""):
        super().__init__()
        self.setObjectName("labelIcon")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.icon_label = None
        if icon:
            self.icon_label = QLabel()
            self.icon_label.setPixmap(icon.pixmap(16, 16))
            self.icon_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            layout.addWidget(self.icon_label)
        
        if not text and self.icon_label:
            self.icon_label.setHidden(True)

        self.text_label = QLabel(text)
        self.text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.text_label.setObjectName("labelText")
        layout.addWidget(self.text_label)

        layout.addStretch()
    
    def setText(self, text: str):
        if self.icon_label and self.icon_label.isHidden():
            self.icon_label.setHidden(False)
            
        self.text_label.setText(text)