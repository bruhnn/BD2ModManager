from PySide6.QtWidgets import (
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
    QStyleOption,
    QGraphicsOpacityEffect,
    QPushButton,
)
from PySide6.QtCore import Qt, QTimer, QEvent, QPoint, QPropertyAnimation, QEasingCurve, Signal, QObject, QSize
from PySide6.QtGui import QPainter

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum, Flag, auto
import logging

from src.themes.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class NotificationPosition(Flag):
    TOP = auto()
    BOTTOM = auto()
    LEFT = auto()
    RIGHT = auto()
    HCENTER = auto()
    VCENTER = auto()

    def __or__(self, other):
        combined = super().__or__(other)
        count = bin(combined.value).count("1")
        if count > 2:
            raise ValueError("Only up to two flags can be combined")
        return combined


class NotificationType(Enum):
    SUCCESS = ("success", "star_fill")
    WARNING = ("warning", "warning")
    ERROR = ("error", "close")
    INFO = ("info", "info")

    def __init__(self, key: str, icon: str) -> None:
        self.key = key
        self.icon = icon


@dataclass
class Notification:
    title: str
    description: str
    type: NotificationType = field(default=NotificationType.SUCCESS)
    duration: int = field(default=3000)
    actions: Optional[List[Dict[str, Any]]] = field(default=None)

    def __post_init__(self) -> None:
        if not self.title and not self.description:
            raise ValueError(
                "Notification must have either title or description")
        if self.duration < 0:
            raise ValueError("Duration cannot be negative")


class NotificationWidget(QWidget):
    closed = Signal()

    def __init__(self, notification: Notification, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setSizePolicy(QSizePolicy.Policy.Maximum,
                           QSizePolicy.Policy.Maximum)
        self.setObjectName("notificationWidget")

        self._notification = notification
        self._setup_animations()
        self._create_ui()
        self._setup_timer()
        self.adjustSize()

    def _setup_animations(self) -> None:
        self.animation_duration = 300
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)

        self.opacity_animation = QPropertyAnimation(
            self.opacity_effect, b"opacity", self)
        self.opacity_animation.setDuration(self.animation_duration)
        self.opacity_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.position_animation = QPropertyAnimation(self, b"pos", self)
        self.position_animation.setDuration(self.animation_duration)
        self.position_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

    def _create_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 24, 12, 24)
        layout.setSpacing(8)

        self._add_type_icon(layout)

        content_widget = self._create_content_widget()
        content_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(content_widget, 1, Qt.AlignmentFlag.AlignVCenter)

        self._add_close_button(layout)

    def _add_type_icon(self, layout):
        try:
            self.type_label = QLabel()

            self.type_label.setPixmap(ThemeManager.icon(
                self._notification.type.icon, self._notification.type.key).pixmap(32, 32))

            self.type_label.setObjectName("notificationType")

            self.type_label.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

            layout.addWidget(self.type_label, 0)
        except Exception as e:
            logger.warning(f"Failed to add type icon: {e}")

    def _create_content_widget(self):
        """Creates the content part of the notification with title and description."""
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)

        if self._notification.title:
            title_label = QLabel(self._notification.title)
            title_label.setObjectName("notificationTitle")
            title_label.setWordWrap(False)
            title_label.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            content_layout.addWidget(title_label, 1)

        if self._notification.description:
            text_label = QLabel(self._notification.description)
            text_label.setObjectName("notificationText")
            text_label.setWordWrap(False)
            text_label.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            content_layout.addWidget(text_label)

        return content_widget

    def _add_close_button(self, layout):
        self.close_btn = QPushButton()
        self.close_btn.setIcon(ThemeManager.icon("close", "icon_color"))
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setObjectName("notificationCloseButton")
        self.close_btn.clicked.connect(self.hide_animation)
        self.close_btn.setIconSize(QSize(24, 24))
        layout.addWidget(self.close_btn)

    def _setup_timer(self) -> None:
        self.close_timer = QTimer(self)
        self.close_timer.setSingleShot(True)
        self.close_timer.setInterval(self._notification.duration)
        self.close_timer.timeout.connect(self.hide_animation)

    def paintEvent(self, event) -> None:
        option = QStyleOption()
        option.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(
            self.style().PrimitiveElement.PE_Widget, option, painter, self
        )

    def show_animation(self) -> None:
        self.setWindowOpacity(0.0)
        self.show()

        self.opacity_animation.setStartValue(0.0)
        self.opacity_animation.setEndValue(1.0)
        self.opacity_animation.start()

        if self._notification.duration > 0:
            self.close_timer.start()

    def hide_animation(self) -> None:
        self.close_btn.setEnabled(False)
        
        self.close_timer.stop()
        self.opacity_animation.setStartValue(1.0)
        self.opacity_animation.setEndValue(0.0)
        self.opacity_animation.finished.connect(self._on_hide_finished)
        self.opacity_animation.start()

    def _on_hide_finished(self) -> None:
        self.close()
        self.closed.emit()

    def move_to(self, pos: QPoint) -> None:
        if self.pos() != pos:
            self.position_animation.setStartValue(self.pos())
            self.position_animation.setEndValue(pos)
            self.position_animation.start()

    def pause_timer(self):
        if self.close_timer.isActive():
            self.close_timer.stop()

    def resume_timer(self):
        if self._notification.duration > 0:
            self.close_timer.start()

    def enterEvent(self, event):
        self.pause_timer()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.resume_timer()
        super().leaveEvent(event)


class NotificationsManager(QObject):
    notification_added = Signal(Notification)
    notification_removed = Signal()

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.notifications: List[NotificationWidget] = []

        self._position = NotificationPosition.TOP | NotificationPosition.RIGHT
        self._spacing = 5
        self._margins = {'top': 16, 'left': 16, 'right': 16, 'bottom': 16}

        self.parent().installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if watched == self.parent() and event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            self.reposition_notifications()

        return super().eventFilter(watched, event)

    def set_position(self, position: NotificationPosition) -> None:
        self._position = position
        self.reposition_notifications()

    def set_margins(self, **kwargs) -> None:
        self._margins.update(kwargs)
        self.reposition_notifications()

    def add_notification(self, title: str = "", description: str = "",
                         notification_type: str = "success", duration: int = 3000) -> bool:

        try:
            type_mapping = {nt.key: nt for nt in NotificationType}
            noti_type = type_mapping.get(
                notification_type.lower(), NotificationType.SUCCESS)

            notification = Notification(
                title=title,
                description=description,
                type=noti_type,
                duration=duration,
            )

            return self._create_notification_widget(notification)

        except Exception as e:
            logger.error(f"Failed to add notification: {e}")
            return False

    def _create_notification_widget(self, notification: Notification) -> bool:
        try:
            widget = NotificationWidget(notification, self.parent())
            widget.closed.connect(lambda: self._on_notification_closed(widget))
            widget.adjustSize()

            # Position the notification
            pos = self._calculate_initial_position(widget)
            widget.move(pos)
            widget.show_animation()

            self.notifications.append(widget)

            self.reposition_notifications()

            self.notification_added.emit(notification)
            return True

        except Exception as e:
            logger.error(f"Failed to create notification widget: {e}")
            return False

    def _calculate_initial_position(self, widget: NotificationWidget) -> QPoint:
        """Calculate initial position for new notification."""
        parent_rect = self.parent().rect()

        # Horizontal position
        if self._position & NotificationPosition.HCENTER:
            x = parent_rect.x() + (parent_rect.width() - widget.width()) // 2
        elif self._position & NotificationPosition.LEFT:
            x = parent_rect.left() + self._margins['left']
        else:  # RIGHT or default
            x = parent_rect.right() - widget.width() - self._margins['right']

        # Vertical position
        if self._position & NotificationPosition.VCENTER:
            y = parent_rect.y() + (parent_rect.height() - widget.height()) // 2
        elif self._position & NotificationPosition.TOP:
            y = parent_rect.top() + self._margins['top']
        else:  # BOTTOM
            y = parent_rect.bottom() - widget.height() - \
                self._margins['bottom']

        return QPoint(x, y)

    def _on_notification_closed(self, widget: NotificationWidget):
        try:
            self.notifications.remove(widget)
            self.notification_removed.emit()
        except ValueError:
            pass
        self.reposition_notifications()

    def reposition_notifications(self):
        if not self.notifications:
            return

        parent_rect = self.parent().rect()
        stack_upwards = bool(self._position & NotificationPosition.BOTTOM)

        # Calculate starting position
        if self._position & NotificationPosition.VCENTER:
            y_pos = parent_rect.y() + (parent_rect.height() // 2)
        elif self._position & NotificationPosition.TOP:
            y_pos = parent_rect.top() + self._margins['top']
        else:  # BOTTOM
            y_pos = parent_rect.bottom() - self._margins['bottom']

        notifications_to_position = list(
            reversed(self.notifications)) if stack_upwards else self.notifications

        for widget in notifications_to_position:
            if stack_upwards:
                y_pos -= widget.height()

            # Calculate horizontal position
            if self._position & NotificationPosition.HCENTER:
                x_pos = parent_rect.x() + (parent_rect.width() - widget.width()) // 2
            elif self._position & NotificationPosition.LEFT:
                x_pos = parent_rect.left() + self._margins['left']
            else:  # RIGHT
                x_pos = parent_rect.right() - widget.width() - \
                    self._margins['right']

            new_pos = QPoint(x_pos, y_pos)
            widget.move_to(new_pos)

            if stack_upwards:
                y_pos -= self._spacing
            else:
                y_pos += widget.height() + self._spacing

    def clear_all(self):
        for notification in self.notifications[:]:
            notification.hide_animation()

    def show_success(self, title: str, description: str = "", duration: int = 3000):
        return self.add_notification(title, description, "success", duration)

    def show_warning(self, title: str, description: str = "", duration: int = 5000):
        return self.add_notification(title, description, "warning", duration)

    def show_error(self, title: str, description: str = "", duration: int = 0):
        return self.add_notification(title, description, "error", duration)

    def show_info(self, title: str, description: str = "", duration: int = 3000):
        return self.add_notification(title, description, "info", duration)
