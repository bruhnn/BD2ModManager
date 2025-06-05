from PySide6.QtWidgets import QWidget, QTreeView, QVBoxLayout, QStyledItemDelegate, QStyle, QLineEdit
from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, QSize, QRect, QRectF, QSortFilterProxyModel
from PySide6.QtGui import QPainter, QPixmap, QFont, QColor, QFontMetrics, QPen , QBrush

from typing import Any, Union


class CharacterNode:
    def __init__(self, character=None, costume: Union[dict, None] = None, parent=None):
        self.character = character
        self.costume = costume
        self.parent = parent
        self.children = []

    def is_costume(self):
        return self.costume is not None

    def add_children(self, children: Any):
        if isinstance(children, list):
            self.children.extend(children)
        else:
            self.children.append(children)

    def child_count(self):
        return len(self.children)

    def row(self):
        if self.parent is None:
            return 0
        return self.parent.children.index(self)


class CharacterTreeModel(QAbstractItemModel):
    def __init__(self, characters: dict):
        super().__init__()
        self.root_node = CharacterNode()
        for character, costumes in characters.items():
            character_node = CharacterNode(
                character=character, parent=self.root_node)
            character_node.add_children([
                CharacterNode(costume=costume, parent=character_node) for costume in costumes
            ])
            self.root_node.add_children(character_node)

    def rowCount(self, parent: QModelIndex = QModelIndex()):
        node = self.get_node(parent)
        return node.child_count()

    def columnCount(self, parent: QModelIndex = QModelIndex()):
        return 1

    def get_node(self, index: QModelIndex):
        if not index.isValid():
            return self.root_node
        return index.internalPointer()

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()):
        if not parent.isValid():
            parent_node = self.root_node
        else:
            parent_node = self.get_node(parent)

        if row < 0 or row >= parent_node.child_count():
            return QModelIndex()

        child_node = parent_node.children[row]
        return self.createIndex(row, column, child_node)

    def parent(self, index):
        node = self.get_node(index)
        if node and node.parent and node.parent != self.root_node:
            return self.createIndex(node.parent.row(), 0, node.parent)
        return QModelIndex()

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        node = self.get_node(index)
        if role == Qt.DisplayRole:
            if node.is_costume():
                char = node.costume.get("character", {})
                return f"{char.get('character', '')} - {char.get('costume', '')}"
            return node.character
        elif role == Qt.UserRole:
            return node
        return None


class CostumeTreeDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        data = index.model().data(index, Qt.UserRole)
        
        # print(option == QStyle)
        if option.state & QStyle.StateFlag.State_MouseOver:
            option.state &= ~QStyle.State_MouseOver

        if not data:
            return

        if data.is_costume():
            costume = data.costume
            character = costume.get("character", {})
            text = f"{character.get('character', '')} - {character.get('costume', '')}"

            margin = 8
            radius = 8
            rect = option.rect.adjusted(0, margin, 0, -margin)
            
            brush = QBrush(QColor("#2F3037"))
            painter.setBrush(brush)
            
            painter.setPen(QPen(QColor("#2F3037"), 1))
            painter.drawRoundedRect(QRectF(rect), radius, radius)
            
            # Imagem
            img_size = QSize(90, 90)
            img_margin = 12
            img_rect = QRect(rect.left() + img_margin, rect.top() +
                             img_margin, img_size.width(), img_size.height())
            
            img_path = f":/characters/{costume['character'].get('id', '000101')}"

            pixmap = QPixmap(img_path)
            
            if pixmap.isNull():
                pixmap = QPixmap(":/characters/000101")
                
            pixmap = pixmap.scaled(
                img_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            painter.drawPixmap(img_rect, pixmap)
            # Título
            font_title = QFont()
            font_title.setPointSize(12)
            font_title.setBold(True)
            font_metrics = QFontMetrics(font_title)
            title_margin_top = 12
            title_margin_left = 12
            title_rect = QRect(
                img_rect.right() + title_margin_left,  # Left
                rect.top() + title_margin_top,  # Top
                rect.width() - 90,  # Width
                font_metrics.height())  # Height
            painter.setFont(font_title)
            painter.setPen(QColor("#fff"))
            title = f"{costume['character']['character']} - {costume['character']['costume']}"
            painter.drawText(
                title_rect,
                Qt.AlignLeft | Qt.AlignVCenter,
                title
            )
            
            charid_font = QFont("Segoe UI")
            charid_font.setPointSize(8)
            charid_metrics = QFontMetrics(charid_font)
            charid_rect = QRect(
                img_rect.right() + title_margin_left,
                title_rect.bottom(),
                charid_metrics.horizontalAdvance(costume["character"]["id"]),
                charid_metrics.height()
            )
            painter.setFont(charid_font)
            painter.setPen(QColor("#fff"))
            painter.drawText(
                charid_rect,
                Qt.AlignLeft | Qt.AlignVCenter,
                costume["character"]["id"]
            )

            # Define cutscene text and font
            cutscene_text = self.tr("Installed") if costume.get(
                "cutscene") else self.tr("Not Installed")
            font_status = QFont()
            font_status.setPointSize(10)
            font_status.setBold(False)
            font_metrics_status = QFontMetrics(font_status)
            cutscene_text_width = font_metrics_status.horizontalAdvance(
                self.tr("Not Installed"))

            # Rectangle for cutscene status text
            cutscene_text_rect = QRect(
                img_rect.right() + 12,
                rect.bottom() - font_metrics_status.height() - 12,
                cutscene_text_width,
                font_metrics_status.height()
            )

            painter.setFont(font_status)
            if costume.get("cutscene"):
                painter.setPen(QColor("#57886C"))  # Green for installed
            else:
                painter.setPen(QColor("#7D7D7D"))  # Gray for not installed
            painter.drawText(
                cutscene_text_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                cutscene_text
            )

            # Title "Cutscene" above the status
            font_status_title = QFont()
            font_status_title.setPointSize(10)
            font_status_title.setBold(True)
            font_metrics_status_title = QFontMetrics(font_status_title)
            font_status_width = font_metrics_status_title.horizontalAdvance(
                "Cutscene")

            cutscene_title_rect = QRect(
                img_rect.right() + 12,
                cutscene_text_rect.top() - font_metrics_status_title.height(),
                font_status_width,
                font_metrics_status_title.height()
            )

            painter.setFont(font_status_title)
            painter.setPen(QColor("#fff"))
            painter.drawText(
                cutscene_title_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                "Cutscene"
            )

            # Define cutscene text and font
            idle_text = "Installed" if costume.get(
                "cutscene") else "Not Installed"
            font_status = QFont()
            font_status.setPointSize(10)
            font_status.setBold(False)
            font_metrics_status = QFontMetrics(font_status)
            idle_text_width = font_metrics_status.horizontalAdvance(
                "Not Installed")

            # Rectangle for cutscene status text
            idle_text_rect = QRect(
                cutscene_title_rect.right() + 64,
                rect.bottom() - font_metrics_status.height() - 12,
                idle_text_width,
                font_metrics_status.height()
            )

            painter.setFont(font_status)
            if costume.get("cutscene"):
                painter.setPen(QColor("#57886C"))  # Green for installed
            else:
                painter.setPen(QColor("#7D7D7D"))  # Gray for not installed
            painter.drawText(
                idle_text_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                idle_text
            )

            # Title "Cutscene" above the status
            font_status_title = QFont()
            font_status_title.setPointSize(10)
            font_status_title.setBold(True)
            font_metrics_status_title = QFontMetrics(font_status_title)
            font_status_width = font_metrics_status_title.horizontalAdvance(
                "Idle")

            idle_title_rect = QRect(
                cutscene_title_rect.right() + 64,
                idle_text_rect.top() - font_metrics_status_title.height(),
                font_status_width,
                font_metrics_status_title.height()
            )

            painter.setFont(font_status_title)
            painter.setPen(QColor("#fff"))
            painter.drawText(
                idle_title_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                "Idle"
            )
        else:
            text = data.character

            font = QFont()
            font.setPointSize(14)
            font.setBold(True)
            painter.setFont(font)

            rect = option.rect
            painter.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter, text)

    def sizeHint(self, option, index):
        data = index.model().data(index, Qt.UserRole)

        if data and not data.is_costume():
            return QSize(320, 32)

        return QSize(320, 90 + (12 * 2) + (8 * 2))

class CharacterFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_text = None
        self.setRecursiveFilteringEnabled(True)  # Important for tree models

    def filterAcceptsRow(self, source_row, source_parent):
        source_model = self.sourceModel()
        
        index = source_model.index(source_row, 0, source_parent)
        node = index.data(Qt.ItemDataRole.UserRole)

        if not node:
            print("node is false ):")
            return False
        
        if not self.search_text or self.search_text == "":
            return True
        
        text = self.search_text.lower()
        if node.is_costume():
            costume_name = f'{node.costume.get("character", {}).get("character", "").lower()} {node.costume.get("character", {}).get("costume", "").lower()}'
            if text in costume_name:
                return True
        else:
            character_name = (node.character or "").lower()

            if text in character_name:
                return True

        for i in range(source_model.rowCount(index)):
            if self.filterAcceptsRow(i, index):
                return True

        return False

    def set_text(self, text: str):
        self.search_text = text
        self.invalidateFilter()

class CharactersView(QWidget):
    def __init__(self, characters: dict):
        super().__init__()
        
        self.search_input = QLineEdit(placeholderText="Search Character")
        self.search_input.setObjectName("searchField")

        self.proxy_model = CharacterFilterProxyModel()
        self.proxy_model.setSourceModel(CharacterTreeModel(characters))
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)    
        self.search_input.textChanged.connect(self._search)

        self.view = QTreeView()
        self.view.setObjectName("charactersTreeView")
        
        self.view.setModel(self.proxy_model)
        self.view.setItemDelegate(CostumeTreeDelegate())
        self.view.setHeaderHidden(True)
        self.view.setRootIsDecorated(False)
        self.view.setItemsExpandable(False)
        self.view.setSelectionMode(QTreeView.SelectionMode.NoSelection)
        self.view.expandAll()

        layout = QVBoxLayout(self)
        layout.addWidget(self.search_input)
        layout.addWidget(self.view)
    
    def _search(self, text: str):
        self.proxy_model.set_text(text)
        self.view.expandAll()

    def retranslateUI(self):
        pass