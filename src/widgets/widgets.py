from PySide6.QtWidgets import QPushButton, QWidget, QLabel, QHBoxLayout, QSizePolicy, QVBoxLayout, QStyledItemDelegate, QTreeWidgetItem, QDialog, QTextEdit, QStyle, QStyleOptionViewItem, QProgressBar, QStyleOptionButton
from PySide6.QtCore import Qt, Signal, QRect, QSize, QRectF
from PySide6.QtGui import QIcon, QColor, QPalette, QPainter, QKeyEvent, QPixmap, QFontMetrics, QBrush

from typing import Optional
import json

from PySide6.QtWidgets import (
    QApplication,
    QFrame,
)
from PySide6.QtCore import QEvent
from PySide6.QtGui import QPainterPath

from src.utils.models import BD2ModType


class NavigationButton(QFrame):
    clicked = Signal()

    def __init__(self, text: str, count: int = None, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("navigationButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._is_active = False
        self._is_pressed = False

        self.original_text = text

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.text_label = QLabel(text)
        self.text_label.setObjectName("navigationButtonTextLabel")
        layout.addWidget(self.text_label)

        self.count_label = QLabel()
        self.count_label.setObjectName("navigationButtonCountLabel")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.count_label)

        if count is not None:
            self.set_count(count)
        else:
            self.count_label.hide()

        layout.addStretch(1)

        self.setLayout(layout)

    def text(self) -> str:
        return self.text_label.text()

    def set_count(self, count: int):
        self.count_label.setText(str(count))
        self.count_label.setVisible(True)

    def set_active(self, is_active: bool):
        self._is_active = is_active
        self.setProperty("active", is_active)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event: QEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_pressed = True
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._is_pressed:
            self._is_pressed = False
            # Check if the mouse was released inside the widget's bounds
            if self.rect().contains(event.pos()):
                self.clicked.emit()
        super().mouseReleaseEvent(event)


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
            self.icon_label.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            layout.addWidget(self.icon_label)

        if not text and self.icon_label:
            self.icon_label.setHidden(True)

        self.text_label = QLabel(text)
        self.text_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.text_label.setObjectName("labelText")
        layout.addWidget(self.text_label)

        layout.addStretch()

    def setText(self, text: str):
        if self.icon_label and self.icon_label.isHidden():
            self.icon_label.setHidden(False)

        self.text_label.setText(text)


class DragFilesModal(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Drop Modal")
        self.setObjectName("dragFilesModal")

        layout = QVBoxLayout()
        label = QLabel("Drop your mod files here to add them!")
        label.setObjectName("dragFilesTitle")

        layout.addWidget(label, 1, Qt.AlignmentFlag.AlignHCenter)

        self.setLayout(layout)


class ModItemModNameDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        print("a")

        has_conflict = index.data(Qt.ItemDataRole.UserRole + 1)

        option.palette.setColor(QPalette.ColorRole.Text, QColor('#ecf0f1'))

        if has_conflict:
            option.palette.setColor(QPalette.ColorRole.Text, QColor('#B4656F'))

            icon = QIcon(":/material/report.svg")

            icon_size = option.decorationSize

            if icon_size.width() == 0 or icon_size.height() == 0:
                icon_size = QSize(16, 16)

            x = option.rect.right() - icon_size.width() - 8
            y = option.rect.top() + (option.rect.height() - icon_size.height()) // 2

            icon.paint(painter, x, y, icon_size.width(), icon_size.height())

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        icon_size = option.decorationSize
        if icon_size.width() == 0:
            icon_size.setWidth(16)
        # espaço extra para o ícone
        size.setWidth(size.width() + icon_size.width() + 8)
        return size


class ModItemCharacterDelegate(QStyledItemDelegate):
    PADDING_HORIZONTAL = 8
    PADDING_VERTICAL = 2
    ICON_SIZE = 64

    def paint(self, painter: QPainter, option: 'QStyleOptionViewItem', index: 'QModelIndex'):
        character = index.data(Qt.ItemDataRole.UserRole)
        display_text = index.data(Qt.ItemDataRole.DisplayRole)

        if not character:
            super().paint(painter, option, index)
            return

        current_option = QStyleOptionViewItem(option)
        self.initStyleOption(current_option, index)

        original_text = current_option.text
        current_option.text = ""

        widget = current_option.widget
        style = widget.style() if widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem,
                          current_option, painter, widget)

        current_option.text = original_text

        pixmap = QPixmap(f":/characters/faces/{character.id}")
        scaled_pixmap = pixmap.scaledToHeight(
            self.ICON_SIZE, mode=Qt.TransformationMode.SmoothTransformation)

        cell_rect = current_option.rect

        icon_rect = QRect(
            cell_rect.left() + self.PADDING_HORIZONTAL,
            cell_rect.top() + (cell_rect.height() - self.ICON_SIZE) // 2,
            scaled_pixmap.width(),
            scaled_pixmap.height(),
        )

        text_rect = QRect(
            icon_rect.right() + self.PADDING_HORIZONTAL,
            cell_rect.top(),
            cell_rect.width() - icon_rect.width() - (3 * self.PADDING_HORIZONTAL),
            cell_rect.height()
        )

        painter.save()

        if not pixmap.isNull():
            painter.save()
            path = QPainterPath()
            path.addEllipse(icon_rect)
            painter.setClipPath(path)
            painter.drawPixmap(icon_rect, pixmap)

            painter.restore()  # Restore painter state to remove clip path

        if display_text:
           
            if current_option.state & QStyle.StateFlag.State_Selected:
                painter.setPen(
                    current_option.palette.highlightedText().color())
            else:
                painter.setPen(current_option.palette.text().color())

            painter.drawText(
                text_rect,
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                display_text
            )

        painter.restore()

    def sizeHint(self, option, index) -> 'QSize':
        size = super().sizeHint(option, index)
        required_height = self.ICON_SIZE + (2 * self.PADDING_VERTICAL)
        if size.height() < required_height:
            size.setHeight(required_height)
        return size


class ModItemTypeStyledDelegate(QStyledItemDelegate):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.padding = 4
        self.radius = 16

    def paint(self, painter: QPainter, option, index): 
        super().paint(painter, option, index)
        text = index.data(Qt.ItemDataRole.DisplayRole)
        mod_type = index.data(Qt.ItemDataRole.UserRole)

        # TODO: move this to ThemeManager
        colors = {
            BD2ModType.IDLE: {
                "text_color": QColor("#7BDE82"), # Bright Green
                "bg_color": QColor("#2A4235")    # Dark Green
            },
            BD2ModType.CUTSCENE: {
                "text_color": QColor("#A5A9F4"), # Light Lavender
                "bg_color": QColor("#3A3D6F")    # Dark Blue/Indigo
            },
            BD2ModType.DATING: {
                "text_color": QColor("#D0A0F5"), # Light Purple
                "bg_color": QColor("#4D3867")    # Dark Purple
            },
            BD2ModType.NPC: {
                "text_color": QColor("#CCCCCC"), # Light Grey
                "bg_color": QColor("#3C444D")    # Slate Grey
            },
            BD2ModType.SCENE: {
                "text_color": QColor("#F0B97D"), # Light Orange
                "bg_color": QColor("#5D4037")    # Dark Brown-Orange
            },
            "default": {
                "text_color": QColor("#FFFFFF"),
                "bg_color": QColor("#222222")
            }
        }

        color_scheme = colors.get(mod_type, colors["default"])

        painter.save()
        
        font = option.font
        font.setPointSize(8)
        font.setBold(True)

        font_metrics = QFontMetrics(font)
        text_rect = font_metrics.boundingRect(
            option.rect, Qt.AlignmentFlag.AlignCenter, str(text))

        bg_width = text_rect.width() + 4 * self.padding
        bg_height = text_rect.height() + 2 * self.padding

        x = option.rect.x() + (option.rect.width() - bg_width) / 2
        y = option.rect.y() + (option.rect.height() - bg_height) / 2

        bg_rect = QRectF(x, y, bg_width, bg_height)

        painter.setBrush(QBrush(color_scheme["bg_color"]))
        painter.setPen(Qt.PenStyle.NoPen)  # No border
        painter.drawRoundedRect(bg_rect, bg_rect.height() / 2, bg_rect.height() / 2)

        painter.setFont(font)
        painter.setPen(color_scheme["text_color"])
        painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter, text)

        painter.restore()


class ModItem(QTreeWidgetItem):
    def __lt__(self, other):
        column = self.treeWidget().sortColumn()

        if column == 1:  # Character
            self_text = self.text(1)
            other_text = other.text(1)

            if self_text == "" and other_text != "":
                return False

            if self_text != "" and other_text == "":
                return True

            return self_text.lower() < other_text.lower()

        return self.text(column).lower() < other.text(column).lower()


class EditModfileDialog(QDialog):
    def __init__(self, parent=None, title=None, data=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Modfile")

        self.modfile_data = data

        layout = QVBoxLayout(self)

        title = QLabel(text=title)
        self.error_label = QLabel()

        self.data_input = QTextEdit(json.dumps(
            data, indent=4, separators=(",", ": ")))
        self.data_input.setObjectName("editModFileData")

        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save)

        actions_layout.addWidget(save_btn)
        actions_layout.addWidget(close_btn)

        layout.addWidget(title)
        layout.addWidget(self.data_input, 1)
        layout.addWidget(self.error_label)
        layout.addWidget(actions_widget, alignment=Qt.AlignmentFlag.AlignRight)

    def save(self):
        # check if is a json valid
        data = None
        try:
            data = json.loads(self.data_input.toPlainText())
        except json.JSONDecodeError:
            self.error_label.setText("Invalid JSON!")
            return

        self.modfile_data = data

        self.accept()


class ProgressModal(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setObjectName("progressModal")

        self.setMinimumWidth(250)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setTextVisible(False)

        self.button = QPushButton(self)
        self.button.clicked.connect(self.accept)
        self.button.setDisabled(True)
        self.button.setObjectName("progressModalButton")

        self.progress_text = QLabel()

        layout.addWidget(self.label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.progress_text)
        layout.addWidget(self.button)

        self.hide()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            return event.ignore()

        return super().keyPressEvent(event)

    def on_started(self):
        self.button.setDisabled(True)
        self.button.setText("Wait...")
        self.progress_bar.setValue(0)

    def on_finished(self):
        self.button.setDisabled(False)
        self.button.setText("Done!")

        self.progress_bar.setMaximum(1)
        self.progress_bar.setValue(1)

    def on_error(self):
        self.button.setDisabled(False)
        self.button.setText("Error!")
        self.progress_bar.setValue(self.progress_bar.maximum() + 1)

    def set_text(self, text: str):
        self.label.setText(text)

    def update_progress(self, value: int, max: int, text: Optional[str] = None):
        self.progress_bar.setMaximum(max)
        self.progress_bar.setValue(value)

        if text:
            self.progress_text.setText(text)


class CPushButton(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setIconSize(QSize(24, 24))
        self._is_active = False
        self._icon_margin = 8
        self._is_centered = False

    def setIconSpacing(self, value: int):
        self._icon_margin = value

    def setContentAlignmentCentered(self, value: bool):
        self._is_centered = True

    def paintEvent(self, event):
        option = QStyleOptionButton()
        self.initStyleOption(option)

        icon_size = self.iconSize()
        icon_margin = self._icon_margin

        with QPainter(self) as painter:
            self.style().drawControl(
                self.style().ControlElement.CE_PushButtonBevel, option, painter, self)

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
                        icon_size.height()
                    )
                    self.icon().paint(painter, icon_rect, Qt.AlignmentFlag.AlignCenter)
                    start_x += icon_size.width() + icon_margin

                # Draw text
                text_rect = QRect(
                    start_x,
                    0,
                    text_width,
                    self.height()
                )
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter |
                                 Qt.AlignmentFlag.AlignLeft, self.text())
            else:
                # Draw icon
                if not self.icon().isNull():
                    icon_rect = QRect(
                        icon_margin,
                        (self.height() - icon_size.height()) // 2,
                        icon_size.width(), icon_size.height())
                    self.icon().paint(painter, icon_rect, Qt.AlignmentFlag.AlignCenter)

                # Draw text right of the icon
                text_rect = QRect(
                    icon_size.width() + icon_margin + 8,
                    0,
                    self.width() - icon_size.width() - icon_margin - 16,
                    self.height())

                painter.drawText(
                    text_rect, Qt.AlignmentFlag.AlignVCenter, self.text())

    def set_active(self, is_active: bool):
        self._is_active = is_active
        self.setProperty("active", is_active)
        self.style().unpolish(self)
        self.style().polish(self)
