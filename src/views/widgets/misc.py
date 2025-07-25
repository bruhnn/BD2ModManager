from typing import Optional
from PySide6.QtWidgets import QLabel, QWidget, QHBoxLayout, QSizePolicy, QVBoxLayout, QComboBox
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QPalette, QIcon

from src.themes import ThemeManager


class PulsingLabel(QLabel):
    def __init__(self, text, parent=None) -> None:
        super().__init__(text, parent)
        self._hue = 0.0
        self._brightness = 0.5
        self._is_increasing = False
        self._base_color = QColor("#34d399")

        # Setup the timer
        self._timer = QTimer(self)
        self._timer.setInterval(16)

    def showEvent(self, event) -> None:
        self._timer.timeout.connect(self._update_pulsing_animation)
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def _update_pulsing_animation(self) -> None:
        step = 0.01
        if self._is_increasing:
            self._brightness += step
            if self._brightness >= 1.0:
                self._brightness = 1.0
                self._is_increasing = False
        else:
            self._brightness -= step
            if self._brightness <= 0.5:
                self._brightness = 0.5
                self._is_increasing = True

        color = ThemeManager.color("update_available_color", "#34d399")
        color.setAlphaF(self._brightness)
        rgba = color.name(QColor.NameFormat.HexArgb)
        self.setStyleSheet(f"color: {rgba};")

    def _update_rainbow_color(self) -> None:
        self._hue += 0.002
        if self._hue > 1.0:
            self._hue -= 1.0

        color = QColor.fromHsvF(self._hue, 1.0, 1.0)

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.WindowText, color)
        self.setPalette(palette)


class LabelIcon(QWidget):
    def __init__(self, icon: Optional[QIcon] = None, text: str = "") -> None:
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
            self.icon_label.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
            )
            layout.addWidget(self.icon_label)

        if not text and self.icon_label:
            self.icon_label.setHidden(True)

        self.text_label = QLabel(text)
        self.text_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.text_label.setObjectName("labelText")
        layout.addWidget(self.text_label)

        layout.addStretch()

    def setText(self, text: str) -> None:
        if self.icon_label and self.icon_label.isHidden():
            self.icon_label.setHidden(False)

        self.text_label.setText(text)

class LabelComboBox(QWidget):
    def __init__(self, label: str):
        super().__init__()

        self._label = QLabel(label)
        self._combobox = QComboBox()

        layout = QVBoxLayout(self)

        layout.addWidget(self._label)
        layout.addWidget(self._combobox)

    @property
    def label(self):
        return self._label

    @property
    def combobox(self):
        return self._combobox