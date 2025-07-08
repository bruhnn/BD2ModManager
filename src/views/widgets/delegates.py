from PySide6.QtWidgets import QTreeWidgetItem, QStyledItemDelegate, QTreeWidget
from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QPainter, QColor, QFontMetrics, QBrush, QPalette, QMouseEvent

from src.themes.theme_manager import ThemeManager
from src.models.models import BD2ModType


class ModlistTreeWidget(QTreeWidget):
    """
    This qtreewidget avoids triggering double click event when pressing the checkbox
    """

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        pos = event.pos()
        item = self.itemAt(pos)

        if item:
            # Check which column was clicked
            column = self.columnAt(pos.x())

            if column == 0:
                item_rect = self.visualItemRect(item)

                checkbox_width = 20

                # Check if the  click is within the checkbox area
                if pos.x() < (item_rect.left() + checkbox_width):
                    event.accept()
                    return

        super().mouseDoubleClickEvent(event)


class ModTreeItem(QTreeWidgetItem):
    """
    Delegate for sorting the character column.

    Ensures that rows without a character value are sorted to the bottom
    when sorting in ascending order.
    """

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


class ModItemTypeStyledDelegate(QStyledItemDelegate):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.padding = 4
        self.radius = 16

    def paint(self, painter: QPainter, option, index) -> None:
        super().paint(painter, option, index)
        text = index.data(Qt.ItemDataRole.DisplayRole)
        mod_type: BD2ModType = index.data(Qt.ItemDataRole.UserRole)
        
        if not mod_type:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color_scheme = {
            "bg_color": 
                ThemeManager.color(f"mod_type_{mod_type.name.lower()}_bg"),
            "text_color": 
                ThemeManager.color(f"mod_type_{mod_type.name.lower()}_text")
        }
        
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        font = option.font
        font.setPointSize(8)
        font.setBold(True)

        font_metrics = QFontMetrics(font)
        text_rect = font_metrics.boundingRect(
            option.rect, Qt.AlignmentFlag.AlignCenter, str(text)
        )

        bg_width = text_rect.width() + 4 * self.padding
        bg_height = text_rect.height() + 2 * self.padding

        x = option.rect.x() + (option.rect.width() - bg_width) / 2
        y = option.rect.y() + (option.rect.height() - bg_height) / 2

        bg_rect = QRectF(int(x), int(y), int(bg_width), int(bg_height))
        radius = min(bg_rect.width(), bg_rect.height()) / 2

        painter.setBrush(QBrush(color_scheme["bg_color"]))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(bg_rect, radius, radius)

        painter.setFont(font)
        painter.setPen(color_scheme["text_color"])
        painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter, text)

        painter.restore()


class ModItemModNameDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index) -> None:
        super().paint(painter, option, index)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        has_conflict = index.data(Qt.ItemDataRole.UserRole + 1)

        option.palette.setColor(QPalette.ColorRole.Text, QColor("#ecf0f1"))

        if has_conflict:
            option.palette.setColor(QPalette.ColorRole.Text, QColor("#B4656F"))

            icon = ThemeManager.icon("report")

            icon_size = option.decorationSize

            if icon_size.width() == 0 or icon_size.height() == 0:
                icon_size = QSize(16, 16)

            x = option.rect.right() - icon_size.width() - 8
            y = option.rect.top() + (option.rect.height() - icon_size.height()) // 2

            icon.paint(painter, x, y, icon_size.width(), icon_size.height())

    def sizeHint(self, option, index) -> QSize:
        size = super().sizeHint(option, index)
        icon_size = option.decorationSize
        if icon_size.width() == 0:
            icon_size.setWidth(16)
        # espaço extra para o ícone
        size.setWidth(size.width() + icon_size.width() + 8)
        return size


# class ModItemCharacterDelegate(QStyledItemDelegate):
#     """
#     This delegate adds the character's face on character column
#     """
#     PADDING_HORIZONTAL = 0
#     PADDING_VERTICAL = 0
#     ICON_SIZE = 64

#     def paint(self, painter: QPainter, option: 'QStyleOptionViewItem', index: 'QModelIndex'):
#         character = index.data(Qt.ItemDataRole.UserRole)
#         display_text = index.data(Qt.ItemDataRole.DisplayRole)

#         painter.setRenderHint(QPainter.RenderHint.Antialiasing)

#         if not character:
#             super().paint(painter, option, index)
#             return

#         current_option = QStyleOptionViewItem(option)
#         self.initStyleOption(current_option, index)

#         original_text = current_option.text
#         current_option.text = ""

#         widget = current_option.widget
#         style = widget.style() if widget else QApplication.style()
#         style.drawControl(QStyle.ControlElement.CE_ItemViewItem,
#                           current_option, painter, widget)

#         current_option.text = original_text

#         pixmap = QPixmap(f":/characters/faces/{character.id}")

#         scaled_pixmap = pixmap.scaledToHeight(
#             self.ICON_SIZE,)

#         cell_rect = current_option.rect

#         icon_rect = QRect(
#             cell_rect.left() + self.PADDING_HORIZONTAL,
#             cell_rect.top() + (cell_rect.height() - self.ICON_SIZE) // 2,
#             scaled_pixmap.width(),
#             scaled_pixmap.height(),
#         )

#         text_rect = QRect(
#             icon_rect.right() + self.PADDING_HORIZONTAL,
#             cell_rect.top(),
#             cell_rect.width() - icon_rect.width() - (3 * self.PADDING_HORIZONTAL),
#             cell_rect.height()
#         )

#         painter.save()

#         if not pixmap.isNull():
#             painter.save()
#             path = QPainterPath()
#             path.addEllipse(icon_rect)
#             painter.setClipPath(path)
#             painter.drawPixmap(icon_rect, pixmap)

#             painter.restore()  # Restore painter state to remove clip path

#         if display_text:

#             if current_option.state & QStyle.StateFlag.State_Selected:
#                 painter.setPen(
#                     current_option.palette.highlightedText().color())
#             else:
#                 painter.setPen(current_option.palette.text().color())

#             painter.drawText(
#                 text_rect,
#                 int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
#                 display_text
#             )

#         painter.restore()

#     def sizeHint(self, option, index) -> 'QSize':
#         size = super().sizeHint(option, index)
#         required_height = self.ICON_SIZE + (2 * self.PADDING_VERTICAL)
#         if size.height() < required_height:
#             size.setHeight(required_height)
#         return size
