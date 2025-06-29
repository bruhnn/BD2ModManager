from PySide6.QtWidgets import (
    QWidget,
    QTreeView,
    QStyledItemDelegate,
    QStyle,
    QLineEdit,
    QGridLayout,
    QSizePolicy,
    QComboBox,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
)
from PySide6.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    Qt,
    QSize,
    QRect,
    QRectF,
    QSortFilterProxyModel,
    Signal,
    Qt,
)
from PySide6.QtGui import (
    QPixmap,
    QFont,
    QFontMetrics,
    QPen,
    QBrush,
    QPainter,
    QPainterPath,
)
from src.themes.theme_manager import ThemeManager

from typing import Any, Union

from src.views.widgets import BaseButton
from src.utils.paths import app_paths


class CharacterNode:
    def __init__(
        self, character=None, costume: Union[dict, None] = None, parent=None
    ) -> None:
        self.character = character
        self.costume = costume
        self.parent = parent
        self.children = []

    def is_costume(self) -> bool:
        return self.costume is not None

    def add_children(self, children: Any) -> None:
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
            character_node = CharacterNode(character=character, parent=self.root_node)
            character_node.add_children(
                [
                    CharacterNode(costume=costume, parent=character_node)
                    for costume in costumes
                ]
            )
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
                char = node.costume.get("character")
                if char is None:
                    return "Error!"
                return char.full_name("-")
            return node.character
        elif role == Qt.UserRole:
            return node
        return None

    def update_characters(self, characters: dict):
        self.beginResetModel()
        self.root_node = CharacterNode()

        for character, costumes in characters.items():
            character_node = CharacterNode(character=character, parent=self.root_node)
            character_node.add_children(
                [
                    CharacterNode(costume=costume, parent=character_node)
                    for costume in costumes
                ]
            )
            self.root_node.add_children(character_node)

        self.endResetModel()


class CostumeTreeDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option, index):
        data = index.model().data(index, Qt.ItemDataRole.UserRole)

        card_margin = 8
        card_radius = 8
        img_size = QSize(120, 120)
        img_margin = 0
        title_margin_left = 0
        title_margin_top = 12
        status_margin_right = -16

        if option.state & QStyle.StateFlag.State_MouseOver:
            option.state &= ~QStyle.StateFlag.State_MouseOver

        if not data:
            return

        if data.is_costume():
            painter.save()

            character_card_color = ThemeManager.color("surface")

            costume = data.costume
            character = costume.get("character")

            rect = option.rect.adjusted(0, card_margin, 0, -card_margin)

            clip_path = QPainterPath()
            clip_path.addRoundedRect(QRectF(rect), card_radius, card_radius)

            painter.setClipPath(clip_path)

            painter.setBrush(QBrush(character_card_color))
            painter.setPen(
                QPen(character_card_color, 1)
            )
            painter.drawPath(clip_path)

            # Character Image

            img_rect = QRect(
                rect.left() + img_margin,
                rect.top() - img_margin,
                img_size.width(),
                img_size.height(),
            )

            # check if exists at user data first
            img_path = app_paths.user_characters_assets / f"{character.id}.png"

            if not img_path.exists():
                img_path = f":/characters/{character.id}"

            pixmap = QPixmap(img_path)

            if pixmap.isNull():
                pixmap = QPixmap(":/characters/000101")  # Default placeholder image

            pixmap = pixmap.scaled(
                img_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(img_rect, pixmap)

            painter.restore()

            # Draw Character Title (Full Name)
            font_title = QFont()
            font_title.setPointSize(12)
            font_title.setBold(True)
            font_metrics = QFontMetrics(font_title)

            title_rect = QRect(
                img_rect.right() + title_margin_left,
                rect.top() + title_margin_top,
                rect.width() - 90,
                font_metrics.height(),
            )

            painter.setFont(font_title)
            painter.setPen(ThemeManager.color("text_primary"))
            title = character.full_name("-")
            painter.drawText(
                title_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                title,
            )

            # Draw Character ID
            charid_msg = f"ID: {character.id}"
            charid_font = QFont("Segoe UI")
            charid_font.setPointSize(8)
            charid_metrics = QFontMetrics(charid_font)
            charid_rect = QRect(
                img_rect.right() + title_margin_left,
                title_rect.bottom(),
                charid_metrics.horizontalAdvance(charid_msg),
                charid_metrics.height(),
            )

            painter.setFont(charid_font)
            painter.setPen(ThemeManager.color("text_primary"))
            painter.drawText(
                charid_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                charid_msg,
            )

            statuses_to_draw = []
            if "cutscene" in costume:
                statuses_to_draw.append((self.tr("Cutscene"), costume.get("cutscene")))
            if "idle" in costume:
                statuses_to_draw.append((self.tr("Idle"), costume.get("idle")))

            if "dating" in costume and costume.get("dating") is not None:
                statuses_to_draw.append((self.tr("Dating"), costume.get("dating")))

            font_status_title = QFont()
            font_status_title.setPointSize(10)
            font_status_title.setBold(True)

            font_status = QFont()
            font_status.setPointSize(10)

            metrics_title = QFontMetrics(font_status_title)
            metrics_status = QFontMetrics(font_status)
            spacing = 64

            total_width = 0
            column_widths = []
            for i, (title, is_installed) in enumerate(statuses_to_draw):
                status_text = self.tr(
                    "Not Installed"
                )
                title_width = metrics_title.horizontalAdvance(title)
                status_width = metrics_status.horizontalAdvance(status_text)
                column_width = max(title_width, status_width)

                column_widths.append(column_width)
                total_width += column_width

            total_width += spacing * (len(statuses_to_draw) - 1)

            current_x = rect.right() - total_width + status_margin_right
            base_y = rect.top() + (rect.height() // 2)

            for i, (title, is_installed) in enumerate(statuses_to_draw):
                column_width = column_widths[i]

                column_center_x = current_x + (column_width / 2)

                self.draw_status(
                    painter,
                    column_center_x,
                    base_y,
                    title,
                    is_installed,
                    font_status_title,
                    font_status,
                )

                current_x += column_width + spacing

        else:
            text = data.character
            font = QFont()
            font.setPointSize(14)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(ThemeManager.color("text_primary"))
            painter.drawText(
                option.rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                text,
            )

    def draw_status(
        self, painter, center_x, base_y, title, is_installed, font_title, font_status
    ):
        metrics_title = QFontMetrics(font_title)
        metrics_status = QFontMetrics(font_status)

        status_text = self.tr("Installed") if is_installed else self.tr("Not Installed")
        if is_installed is None:
            status_text = "Not Available"
        title_width = metrics_title.horizontalAdvance(title)
        status_text_width = metrics_status.horizontalAdvance(status_text)

        # The width of this column is determined by the wider of the two text elements
        column_width = max(title_width, status_text_width)

        # Calculate the top-left x for the drawing rectangles to ensure they are centered on center_x
        top_left_x = center_x - (column_width / 2)

        # Define the rectangle for the title (drawn above the base_y)
        title_rect = QRect(
            int(top_left_x),
            int(base_y - metrics_title.height()),
            int(column_width),
            int(metrics_title.height()),
        )

        # Define the rectangle for the status (drawn below the base_y)
        status_rect = QRect(
            int(top_left_x),
            int(base_y),
            int(column_width),
            int(metrics_status.height()),
        )

        painter.save()

        # Draw Title Label (centered horizontally)
        painter.setFont(font_title)
        painter.setPen(ThemeManager.color("text_primary"))
        painter.drawText(
            title_rect,
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
            title,
        )

        # Draw Status Text (centered horizontally)
        painter.setFont(font_status)
        painter.setPen(
            ThemeManager.color("success")
            if is_installed
            else ThemeManager.color("text_primary")
        )
        painter.drawText(
            status_rect,
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
            status_text,
        )

        painter.restore()

    def sizeHint(self, option, index):
        data = index.model().data(index, Qt.ItemDataRole.UserRole)

        if data and not data.is_costume():
            return QSize(320, 32)

        return QSize(320, 110 + (8 * 2))


class CharacterFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_text = None
        self.filtering = {}
        self.setRecursiveFilteringEnabled(True)

    def filterAcceptsRow(self, source_row, source_parent):
        source_model = self.sourceModel()
        index = source_model.index(source_row, 0, source_parent)
        node = index.data(Qt.ItemDataRole.UserRole)

        if not node:
            return False

        # is_parent_node = source_model.hasChildren(index)

        text_to_search = self.search_text
        text_matched = True
        if text_to_search:
            text_to_search = text_to_search.lower()

            node_name = ""
            if node.is_costume():
                character = node.costume.get("character")
                if character:
                    node_name = character.full_name().lower()

                # filter by id
                if text_to_search.isnumeric():
                    node_name = character.id
            else:
                node_name = (node.character or "").lower()

            text_matched = text_to_search in node_name

        filter_values = {
            "Any": (True, False, None),
            "Installed": (True,),
            "Not Installed": (False,),
        }

        cutscene_matched = True
        idle_matched = True
        dating_matched = True

        if node.is_costume():
            if self.filtering.get("cutscene") is not None:
                cutscene_matched = (
                    node.costume["cutscene"]
                    in filter_values[self.filtering["cutscene"]]
                )
            if self.filtering.get("idle") is not None:
                idle_matched = (
                    node.costume["idle"] in filter_values[self.filtering["idle"]]
                )
            if self.filtering.get("dating") is not None:
                dating_matched = (
                    node.costume["dating"] in filter_values[self.filtering["dating"]]
                )
        else:
            return False

        return text_matched and cutscene_matched and idle_matched and dating_matched

    def set_text(self, text: str):
        self.search_text = text

    def set_filtering(self, data: dict):
        self.filtering = data


class CComboBox(QWidget):
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


class CharactersView(QWidget):
    refreshCharactersRequested = Signal()

    def __init__(self):
        super().__init__()

        self.search_input = QLineEdit(placeholderText="Search Character")
        self.search_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.search_input.setObjectName("charactersSearchField")
        self.search_input.textChanged.connect(self._search_char)

        self.refresh_button = BaseButton(self.tr("Refresh"))
        self.refresh_button.setContentAlignmentCentered(True)
        self.refresh_button.setObjectName("modsButton")
        self.refresh_button.setProperty("iconName", "refresh")
        self.refresh_button.clicked.connect(self.refreshCharactersRequested.emit)

        self.proxy_model = CharacterFilterProxyModel()
        self.proxy_model.setSourceModel(CharacterTreeModel({}))
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.view = QTreeView()
        self.view.setObjectName("charactersTreeView")
        self.view.setModel(self.proxy_model)
        self.view.setIndentation(0)
        self.view.setItemDelegate(CostumeTreeDelegate())
        self.view.setHeaderHidden(True)
        self.view.setRootIsDecorated(False)
        self.view.setItemsExpandable(False)
        self.view.setSelectionMode(QTreeView.SelectionMode.NoSelection)

        self.filters_widget = QWidget()
        self.filters_layout = QHBoxLayout(self.filters_widget)
        self.filters_layout.setContentsMargins(*[0] * 4)

        self.filters = {
            "cutscene": CComboBox("Cutscene"),
            "idle": CComboBox("Idle"),
            "dating": CComboBox("Dating"),
        }

        for _, filter_widget in self.filters.items():
            filter_widget.label.setObjectName("customComboBoxLabel")
            filter_widget.combobox.setObjectName("customComboBox")
            filter_widget.combobox.addItems(["Any", "Installed", "Not Installed"])
            filter_widget.combobox.currentIndexChanged.connect(self._filter_char)
            self.filters_layout.addWidget(filter_widget)

        layout = QGridLayout(self)
        layout.addWidget(self.search_input, 0, 0)
        layout.addWidget(self.refresh_button, 0, 1)
        layout.addWidget(self.filters_widget, 1, 0, 1, 2)
        layout.addWidget(self.view, 2, 0, 2, 2)
        layout.setRowStretch(2, 1)

    def _search_char(self, text: str):
        self.proxy_model.set_text(text)
        self.proxy_model.invalidateFilter()
        self.view.expandAll()

    def _filter_char(self):
        self.proxy_model.set_filtering(
            {
                "cutscene": self.filters["cutscene"].combobox.currentText(),
                "idle": self.filters["idle"].combobox.currentText(),
                "dating": self.filters["dating"].combobox.currentText(),
            }
        )
        self.proxy_model.invalidateFilter()
        self.view.expandAll()

    def load_characters(self, characters: dict):
        self.proxy_model.sourceModel().update_characters(characters)
        self.proxy_model.invalidateFilter()
        self.view.expandAll()

    def retranslateUI(self):
        pass

    def updateIcons(self):
        self.refresh_button.setIcon(
            ThemeManager.icon(self.refresh_button.property("iconName"))
        )
