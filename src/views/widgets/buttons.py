from PySide6.QtWidgets import (
    QPushButton,
    QStyleOptionButton,
)
from PySide6.QtCore import Qt, QEvent, QRect, QSize
from PySide6.QtGui import QPainter

# class _(QFrame):
#     clicked = Signal()

#     def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
#         super().__init__(parent)
#         self.setObjectName("navigationButton")
#         self.setCursor(Qt.CursorShape.PointingHandCursor)

#         self._is_active = False
#         self._is_pressed = False

#         self.original_text = text

#         layout = QHBoxLayout(self)
#         layout.setContentsMargins(0, 0, 0, 0)
#         layout.setSpacing(10)

#         self.text_label = QLabel(text)
#         self.text_label.setObjectName("navigationButtonTextLabel")
#         layout.addWidget(self.text_label)

#         # self.count_label = QLabel()
#         # self.count_label.setObjectName("navigationButtonCountLabel")
#         # self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#         # layout.addWidget(self.count_label)

#         # if count is not None:
#         #     self.set_count(count)
#         # else:
#         #     self.count_label.hide()

#         layout.addStretch(1)

#         self.setLayout(layout)

#     def text(self) -> str:
#         return self.text_label.text()

#     # def set_count(self, count: int):
#     #     self.count_label.setText(str(count))
#     #     self.count_label.setVisible(True)

#     def set_active(self, is_active: bool):
#         self._is_active = is_active
#         self.setProperty("active", is_active)
#         self.style().unpolish(self)
#         self.style().polish(self)

#     def mousePressEvent(self, event: QEvent):
#         if event.button() == Qt.MouseButton.LeftButton:
#             self._is_pressed = True
#         super().mousePressEvent(event)

#     def mouseReleaseEvent(self, event: QEvent):
#         if event.button() == Qt.MouseButton.LeftButton and self._is_pressed:
#             self._is_pressed = False
#             # Check if the mouse was released inside the widget's bounds
#             if self.rect().contains(event.pos()):
#                 self.clicked.emit()
#         super().mouseReleaseEvent(event)


class BaseButton(QPushButton):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setIconSize(QSize(24, 24))
        self._icon_margin = 8
        self._is_centered = False

    def setIconSpacing(self, value: int) -> None:
        self._icon_margin = value

    def setContentAlignmentCentered(self, value: bool) -> None:
        self._is_centered = value

    def paintEvent(self, event: QEvent) -> None:
        option = QStyleOptionButton()
        self.initStyleOption(option)

        icon_size = self.iconSize()
        icon_margin = self._icon_margin

        with QPainter(self) as painter:
            self.style().drawControl(
                self.style().ControlElement.CE_PushButtonBevel, option, painter, self
            )

            if self._is_centered:
                text_metrics = painter.fontMetrics()
                text_width = text_metrics.horizontalAdvance(self.text())

                total_width = 0
                if not self.icon().isNull():
                    total_width += icon_size.width()
                    total_width += icon_margin
                total_width += text_width

                # Starting X to center the whole block
                start_x = (self.width() - total_width) // 2
                center_y = self.height() // 2

                # Draw icon (if exists)
                if not self.icon().isNull():
                    icon_rect = QRect(
                        start_x,
                        center_y - icon_size.height() // 2,
                        icon_size.width(),
                        icon_size.height(),
                    )
                    self.icon().paint(painter, icon_rect, Qt.AlignmentFlag.AlignCenter)
                    start_x += icon_size.width() + icon_margin

                # Draw text
                text_rect = QRect(start_x, 0, text_width, self.height())
                painter.drawText(
                    text_rect,
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    self.text(),
                )
            else:
                # Draw icon
                if not self.icon().isNull():
                    icon_rect = QRect(
                        icon_margin,
                        (self.height() - icon_size.height()) // 2,
                        icon_size.width(),
                        icon_size.height(),
                    )
                    self.icon().paint(painter, icon_rect, Qt.AlignmentFlag.AlignCenter)

                # Draw text right of the icon
                text_rect = QRect(
                    icon_size.width() + icon_margin + 8,
                    0,
                    self.width() - icon_size.width() - icon_margin - 16,
                    self.height(),
                )

                painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, self.text())


class NavigationButton(BaseButton):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._is_active = False

    def set_active(self, is_active: bool) -> None:
        self._is_active = is_active
        self.setProperty("active", is_active)
        self.style().unpolish(self)
        self.style().polish(self)
