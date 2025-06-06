from PySide6.QtWidgets import QWidget, QTreeView, QVBoxLayout, QStyledItemDelegate, QStyle, QLineEdit, QPushButton, QGridLayout
from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, QSize, QRect, QRectF, QSortFilterProxyModel, Signal
from PySide6.QtGui import QPainter, QPixmap, QFont, QColor, QFontMetrics, QPen , QBrush, QIcon

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
    def __init__(self, characters: dict = {}):
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
    
    def update_characters(self, characters: dict):
        self.beginResetModel()
        self.root_node = CharacterNode() 

        for character, costumes in characters.items():
            character_node = CharacterNode(character=character, parent=self.root_node)
            character_node.add_children([
                CharacterNode(costume=costume, parent=character_node) for costume in costumes
            ])
            self.root_node.add_children(character_node)

        self.endResetModel()


class CostumeTreeDelegate(QStyledItemDelegate):
    def draw_status(self, painter, base_x, base_y, title, is_installed, font_title, font_status, spacing=64):
        # Metrics
        metrics_title = QFontMetrics(font_title)
        metrics_status = QFontMetrics(font_status)

        status_text = self.tr("Installed") if is_installed else self.tr("Not Installed")
        status_text_width = metrics_status.horizontalAdvance(self.tr("Not Installed"))
        title_width = metrics_title.horizontalAdvance(title)

        title_rect = QRect(
            base_x,
            base_y - metrics_title.height(),
            title_width,
            metrics_title.height()
        )
        status_rect = QRect(
            base_x,
            base_y,
            status_text_width,
            metrics_status.height()
        )

        painter.save()  # Save painter state here

        painter.setFont(font_title)
        painter.setPen(QColor("#fff"))
        painter.drawText(
            title_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            title
        )

        painter.setFont(font_status)
        painter.setPen(QColor("#57886C") if is_installed else QColor("#7D7D7D"))
        painter.drawText(
            status_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            status_text
        )

        painter.restore()  # Restore painter state here

        return max(title_width, status_text_width) + spacing


    def paint(self, painter, option, index):
        data = index.model().data(index, Qt.UserRole)
        
        # print(option == QStyle)
        if option.state & QStyle.StateFlag.State_MouseOver:
            option.state &= ~QStyle.State_MouseOver

        if not data:
            return

        if data.is_costume():
            costume = data.costume
            character = costume.get("character")

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
            
            img_path = f":/characters/{character.id}"

            pixmap = QPixmap(img_path)
            
            if pixmap.isNull():
                pixmap = QPixmap(":/characters/000101")
                
            pixmap = pixmap.scaled(
                img_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            painter.drawPixmap(img_rect, pixmap)
            
            # Draw Title
            font_title = QFont()
            font_title.setPointSize(12)
            font_title.setBold(True)
            font_metrics = QFontMetrics(font_title)
            title_margin_top = 12
            title_margin_left = 12
            title_rect = QRect(
                img_rect.right() + title_margin_left,
                rect.top() + title_margin_top,
                rect.width() - 90,
                font_metrics.height()
            )

            painter.save()
            painter.setFont(font_title)
            painter.setPen(QColor("#fff"))
            title = character.full_name()
            painter.drawText(
                title_rect,
                Qt.AlignLeft | Qt.AlignVCenter,
                title
            )
            painter.restore()

            # Draw Character ID
            charid_font = QFont("Segoe UI")
            charid_font.setPointSize(8)
            charid_metrics = QFontMetrics(charid_font)
            charid_rect = QRect(
                img_rect.right() + title_margin_left,
                title_rect.bottom(),
                charid_metrics.horizontalAdvance(character.id),
                charid_metrics.height()
            )

            painter.save()
            painter.setFont(charid_font)
            painter.setPen(QColor("#fff"))
            painter.drawText(
                charid_rect,
                Qt.AlignLeft | Qt.AlignVCenter,
                character.id
            )
            painter.restore()

            # Prepare fonts for status
            font_status_title = QFont()
            font_status_title.setPointSize(10)
            font_status_title.setBold(True)

            font_status = QFont()
            font_status.setPointSize(10)
            font_status.setBold(False)

            base_y = rect.bottom() - QFontMetrics(font_status).height() - 12
            start_x = img_rect.right() + 12

            offset_x = start_x
            offset_x += self.draw_status(painter, offset_x, base_y, self.tr("Cutscene"), costume.get("cutscene"), font_status_title, font_status)

            idle_val = costume.get("idle")
            if idle_val is not None:
                offset_x += self.draw_status(painter, offset_x, base_y, self.tr("Idle"), idle_val, font_status_title, font_status)

            dating_val = costume.get("dating")
            if isinstance(dating_val, bool):
                offset_x += self.draw_status(painter, offset_x, base_y, self.tr("Dating"), dating_val, font_status_title, font_status)

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
            costume_name = node.costume["character"].full_name().lower()

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
    refreshCharactersRequested = Signal()
    
    def __init__(self):
        super().__init__()
        
        self.search_input = QLineEdit(placeholderText="Search Character")
        self.search_input.setObjectName("searchField")
        
        self.refresh_button = QPushButton(text="Refresh")
        self.refresh_button.setIcon(QIcon(":/material/refresh.svg"))
        self.refresh_button.setObjectName("modsViewButton")
        self.refresh_button.clicked.connect(self.refreshCharactersRequested.emit)

        self.proxy_model = CharacterFilterProxyModel()
        self.proxy_model.setSourceModel(CharacterTreeModel())
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

        layout = QGridLayout(self)
        layout.addWidget(self.search_input, 0, 0)
        layout.addWidget(self.refresh_button, 0, 1)
        layout.addWidget(self.view, 1, 0, 2, 2)
    
    def load_characters(self, characters: dict):
        self.proxy_model.sourceModel().update_characters(characters)
        self.proxy_model.invalidateFilter()
        self.view.expandAll()
    
    def _search(self, text: str):
        self.proxy_model.set_text(text)
        self.view.expandAll()

    def retranslateUI(self):
        pass