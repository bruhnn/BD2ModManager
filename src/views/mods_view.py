from typing import Callable, Dict, List
import logging

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QTreeWidgetItem,
    QHeaderView,
    QMenu,
    QInputDialog,
    QMessageBox,
    QGridLayout,
    QDialog,
    QComboBox,
    QSizePolicy,
    QStyleOption,
    QStackedWidget,
    QSpacerItem
)
from PySide6.QtGui import (
    QDragEnterEvent,
    QShortcut,
    QKeySequence,
    QDragLeaveEvent,
    QAction,
    QPainter,
)
from PySide6.QtCore import Qt, Signal, QSettings, QByteArray, QSize, Slot

from src.models.models import BD2ModEntry, BD2ModType
from src.views.widgets import (
    DropFilesWidget,
    ModTreeItem,
    EditModfileDialog,
    ProgressModal,
    ModItemTypeStyledDelegate,
    BaseButton,
    ModItemModNameDelegate,
)
from src.themes.theme_manager import ThemeManager
from src.views.widgets.delegates import ModlistTreeWidget

CONFLICT_DATA_ROLE = Qt.ItemDataRole.UserRole + 1

logger = logging.getLogger(__name__)


class ModsView(QWidget):
    loadFinished = Signal()

    refreshRequested = Signal()
    syncRequested = Signal()
    unsyncRequested = Signal()

    openModsFolderRequested = Signal()
    openModFolderRequested = Signal(str)  # Mod Path

    addModsRequested = Signal(list)  # Mod path
    removeModsRequested = Signal(list)
    removeModRequested = Signal(str)  # mod_name
    renameModRequested = Signal(str, str)  # mod_name, New Name
    editModfileRequested = Signal(str)

    modStateChanged = Signal(str, bool)  # mod_name, Enabled State
    modBulkStateChanged = Signal(list, bool)  # list[str]

    modAuthorChanged = Signal(str, str)  # mod_name, Author Name
    modBulkAuthorChanged = Signal(list, str)  # [str], author name
    modModfileChanged = Signal(str, dict)

    showNotificationRequested = Signal(str, str, str, int)
    
    modPreviewRequested = Signal(str)  # Mod path

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("modsView")
        self.setAcceptDrops(True)

        self.settings = QSettings()

        self.progress_modal = None

        # -> -> -> HEADER

        self.header_widget = QWidget()
        self.header_widget.setObjectName("modsHeader")
        self.header_layout = QGridLayout(self.header_widget)
        self.header_layout.setContentsMargins(0, 0, 0, 12)
        self.header_layout.setSpacing(0)

        self.title_label = QLabel(self.tr("Mods"))
        self.title_label.setObjectName("modsTitleLabel")
        self.mods_count_label = QLabel(
            self.tr("{} of {} mods enabled.").format(0, 0)
        )
        self.mods_count_label.setObjectName("modsCountLabel")

        self.refresh_button = BaseButton(self.tr("Refresh"))
        self.refresh_button.setContentAlignmentCentered(True)
        self.refresh_button.setObjectName("modsButton")
        self.refresh_button.setToolTip(self.tr("Refresh the list of mods"))
        # self.refresh_button.setIcon(QIcon(":/icons/material/refresh.svg"))
        self.refresh_button.setProperty("iconName", "refresh")
        self.refresh_button.setIconSize(QSize(20, 20))
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.refresh_button.clicked.connect(self.refreshRequested.emit)

        self.header_layout.addWidget(self.title_label, 0, 0, 1, 1)
        self.header_layout.addWidget(self.mods_count_label, 1, 0, 1, 1)
        self.header_layout.setColumnStretch(1, 1)
        self.header_layout.addWidget(self.refresh_button, 0, 2, 2, 1)

        # -> -> -> TOP BAR
        self.top_bar = QWidget()
        self.top_bar.setObjectName("modsTopBar")
        self.top_bar_layout = QVBoxLayout(self.top_bar)
        self.top_bar_layout.setContentsMargins(0, 0, 0, 8)
        self.top_bar_layout.setSpacing(6)

        self.search_area = QWidget()
        self.search_layout = QHBoxLayout(self.search_area)
        self.search_layout.setContentsMargins(0, 0, 0, 0)

        self.search_field = QLineEdit(placeholderText=self.tr("Search Mods"))
        self.search_field.setObjectName("searchField")
        self.search_field.textChanged.connect(self._on_search_field_changed)

        self.search_field_icon = QAction("search_icon")
        self.search_field_icon.setProperty("iconName", "search")

        self.search_field.addAction(
            self.search_field_icon, QLineEdit.ActionPosition.LeadingPosition
        )

        self.search_clear_action = QAction("clear_search")
        self.search_clear_action.setProperty("iconName", "close")

        self.search_clear_action.triggered.connect(self.search_field.clear)
        self.search_clear_action.setVisible(False)
        self.search_field.addAction(
            self.search_clear_action, QLineEdit.ActionPosition.TrailingPosition
        )

        self.search_type = QComboBox()
        self.search_type.setObjectName("searchType")
        for label, data in [(self.tr("Mod"), "mod"), (self.tr("Character"), "character"), (self.tr("Author"), "author")]:
            self.search_type.addItem(label, data)
        self.search_type.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_type.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.search_type.currentIndexChanged.connect(self._filter_mods)

        self.search_layout.addWidget(self.search_field, 1)
        self.search_layout.addWidget(self.search_type, 0)

        self.mod_types_filter_widget = QWidget()
        self.mod_types_filter_widget.setObjectName("modTypesFilterWidget")
        self.mod_types_filter_layout = QHBoxLayout(self.mod_types_filter_widget)
        self.mod_types_filter_layout.setContentsMargins(0, 0, 0, 0)
        self.mod_types_filter_layout.setSpacing(6)

        self.filter_chip_types = {
            "idle": QPushButton("Idle"),
            "cutscene": QPushButton("Cutscene"),
            "scene": QPushButton("Scene"),
            "dating": QPushButton("Dating"),
            "npc": QPushButton("NPC"),
        }

        for btn in self.filter_chip_types.values():
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setObjectName("modTypesFilterChip")
            btn.setCheckable(True)
            btn.setChecked(False)
            btn.clicked.connect(self._filter_mods)
            self.mod_types_filter_layout.addWidget(btn)

        self.top_bar_layout.addWidget(self.search_area)
        self.top_bar_layout.addWidget(
            self.mod_types_filter_widget,
            0,
            alignment=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
        )

        # -> -> -> MOD LIST

        self.mod_list_area = QWidget()
        self.mod_list_area.setObjectName("modlistArea")
        self.mod_list_area_layout = QVBoxLayout(self.mod_list_area)
        self.mod_list_area_layout.setContentsMargins(0, 0, 0, 0)

        self.mod_list = ModlistTreeWidget()
        self.mod_list.setObjectName("modlist")
        self.mod_list.setHeaderLabels(
            [
                self.tr("Mod Name"),
                self.tr("Character"),
                self.tr("Type"),
                self.tr("Author"),
            ]
        )
        self.mod_list.setSortingEnabled(True)
        self.mod_list.setRootIsDecorated(False)
        self.mod_list.setAlternatingRowColors(True)
        self.mod_list.header().setObjectName("modlistHeader")
        self.mod_list.header().setMinimumHeight(32)
        self.mod_list.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.mod_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.mod_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.mod_list.setContentsMargins(0, 0, 0, 0)
        self.mod_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.mod_list.setSelectionMode(QHeaderView.SelectionMode.ExtendedSelection)
        # filter by character in alphabetical order
        self.mod_list.sortItems(1, Qt.SortOrder.AscendingOrder)
        self.mod_list.customContextMenuRequested.connect(self._open_context_menu)
        self.mod_list.itemChanged.connect(self._on_mod_state_changed)
        self.mod_list_resized = False
        self.mod_list.doubleClicked.connect(self._on_mod_double_click)

        self.mod_name_delegate = ModItemModNameDelegate()
        # self.mod_char_delegate = ModItemCharacterDelegate()
        self.mod_type_delegate = ModItemTypeStyledDelegate()

        self.mod_list.setItemDelegateForColumn(0, self.mod_name_delegate)
        # self.mod_list.setItemDelegateForColumn(1, self.mod_char_delegate)
        self.mod_list.setItemDelegateForColumn(2, self.mod_type_delegate)

        self.mod_list_area_layout.addWidget(self.mod_list, 1)

        # -> -> -> FOOTER BAR

        self.footer_bar = QWidget()
        self.footer_bar.setObjectName("modsFooterBar")
        self.footer_bar_layout = QHBoxLayout(self.footer_bar)
        self.footer_bar_layout.setContentsMargins(0, 8, 0, 8)

        self.info_label = QLabel()
        self.info_label.setObjectName("modsInfoLabel")

        self.actions_widget = QWidget()
        self.actions_layout = QHBoxLayout(self.actions_widget)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)

        self.open_mods_folder_button = BaseButton(self.tr("Open Mods Folder"))
        self.open_mods_folder_button.setObjectName("modsButton")
        self.open_mods_folder_button.setContentAlignmentCentered(True)
        self.open_mods_folder_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_mods_folder_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.open_mods_folder_button.setIcon(QIcon(":/icons/material/folder.svg"))
        self.open_mods_folder_button.setProperty("iconName", "folder")
        self.open_mods_folder_button.clicked.connect(self.openModsFolderRequested.emit)

        self.sync_button = BaseButton(self.tr("Sync Mods"))
        self.sync_button.setContentAlignmentCentered(True)
        self.sync_button.clicked.connect(self.syncRequested.emit)
        self.sync_button.setObjectName("modsButton")
        self.sync_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sync_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.sync_button.setIcon(QIcon(":/icons/material/sync.svg"))
        self.sync_button.setProperty("iconName", "sync")

        self.unsync_button = BaseButton(self.tr("Unsync Mods"))
        self.unsync_button.setObjectName("modsButton")
        self.unsync_button.setContentAlignmentCentered(True)
        self.unsync_button.clicked.connect(self.unsyncRequested.emit)
        self.unsync_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.unsync_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.unsync_button.setIcon(QIcon(":/icons/material/unsync.svg"))
        self.unsync_button.setProperty("iconName", "unsync")

        self.actions_layout.addWidget(self.open_mods_folder_button)
        self.actions_layout.addWidget(self.unsync_button)
        self.actions_layout.addWidget(self.sync_button)

        self.footer_bar_layout.addWidget(self.info_label)
        self.footer_bar_layout.addWidget(self.actions_widget)

        # -> -> -> SHORTCUTS
        QShortcut(QKeySequence("Ctrl+A"), self.mod_list).activated.connect(
            self.mod_list.selectAll
        )
        QShortcut(QKeySequence("Ctrl+F"), self.search_field).activated.connect(
            self.search_field.setFocus
        )
        QShortcut(QKeySequence("Ctrl+R"), self.refresh_button).activated.connect(
            self.refresh_button.click
        )
        QShortcut(QKeySequence("F2"), self).activated.connect(
            lambda: self._show_rename_input_dialog(self.mod_list.selectedItems()[0]) 
            if len(self.mod_list.selectedItems()) == 1 else ...
        )

        # -> -> -> LAYOUTS
        self.drop_widget = DropFilesWidget()
        self.drop_widget.hide()

        modview_widget = QWidget()
        modview_layout = QVBoxLayout(modview_widget)
        modview_layout.setContentsMargins(*[0] * 4)
        modview_layout.setSpacing(0)

        modview_layout.addWidget(self.drop_widget)
        modview_layout.addWidget(self.header_widget)
        modview_layout.addWidget(self.top_bar, 0)
        modview_layout.addWidget(self.mod_list_area, 1)
        modview_layout.addWidget(self.footer_bar, 0, Qt.AlignmentFlag.AlignBottom)

        self.view_stacked = QStackedWidget()
        self.view_stacked.addWidget(modview_widget)
        self.view_stacked.addWidget(self.drop_widget)

        layout = QVBoxLayout(self)
        layout.addWidget(self.view_stacked)

        self._first_time = True
        self.load_settings_state()

        self._mod_item_cache: Dict[str, ModTreeItem] = {}

    def updateIcons(self) -> None:
        self.search_field_icon.setIcon(ThemeManager.icon(self.search_field_icon))
        self.search_clear_action.setIcon(ThemeManager.icon(self.search_clear_action))

        if self.search_field_icon not in self.search_field.actions():
            self.search_field.addAction(
                self.search_field_icon, QLineEdit.ActionPosition.LeadingPosition
            )
        if self.search_clear_action not in self.search_field.actions():
            self.search_field.addAction(
                self.search_clear_action, QLineEdit.ActionPosition.TrailingPosition
            )
            self.search_clear_action.setVisible(False)

        # Update icons for the buttons
        self.refresh_button.setIcon(ThemeManager.icon(self.refresh_button))
        self.open_mods_folder_button.setIcon(
            ThemeManager.icon(self.open_mods_folder_button.property("iconName"))
        )
        self.sync_button.setIcon(
            ThemeManager.icon(self.sync_button.property("iconName"))
        )
        self.unsync_button.setIcon(
            ThemeManager.icon(self.unsync_button.property("iconName"))
        )

    def retranslateUI(self) -> None:
        self.search_field.setPlaceholderText(self.tr("Search Mods"))
        self.refresh_button.setText(self.tr("Refresh Mods"))
        self.open_mods_folder_button.setText(self.tr("Open Mods Folder"))
        self.sync_button.setText(self.tr("Sync Mods"))
        self.unsync_button.setText(self.tr("Unsync Mods"))
        self.mod_list.setHeaderLabels(
            [
                self.tr("Mod Name"),
                self.tr("Character"),
                self.tr("Type"),
                self.tr("Author"),
            ]
        )
        self.search_type.clear()
        for label, data in [(self.tr("Mod"), "mod"), (self.tr("Character"), "character"), (self.tr("Author"), "author")]:
            self.search_type.addItem(label, data)

    # --- Events
    def paintEvent(self, _) -> None:
        option = QStyleOption()
        option.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(
            self.style().PrimitiveElement.PE_Widget, option, painter, self
        )

    def showEvent(self, _) -> None:
        if self._first_time:
            self.loadFinished.emit()
            self._first_time = False

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            self.view_stacked.setCurrentIndex(1)
            # self.drop_widget.show()
            return event.acceptProposedAction()
        self.view_stacked.setCurrentIndex(0)
        # self.drop_widget.hide()
        return event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self.view_stacked.setCurrentIndex(0)
        return super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls()]
            self.addModsRequested.emit(paths)
            self.view_stacked.setCurrentIndex(0)
            # for url in event.mimeData().urls():
            #     file_path = url.toLocalFile()
            #     self.addModsRequested.emit(file_path)
            #     self.view_stacked.setCurrentIndex(0)

    # --- Signals
    def _on_search_field_changed(self) -> None:
        if len(self.search_field.text()) > 0:
            if not self.search_clear_action.isVisible():
                self.search_clear_action.setVisible(True)
        else:
            if self.search_clear_action.isVisible():
                self.search_clear_action.setVisible(False)

        self._filter_mods()

    def _on_mod_state_changed(self, item: QTreeWidgetItem):
        mod_entry = item.data(0, Qt.ItemDataRole.UserRole)
        mod_state = item.checkState(0)
        self.modStateChanged.emit(mod_entry.name, mod_state == Qt.CheckState.Checked)
        self._update_mods_count_label()
    
    def _on_mod_double_click(self, index) -> None:
        mod_entry = self.mod_list.model().index(index.row(), 0, index.parent()).data(Qt.ItemDataRole.UserRole)
        self.modPreviewRequested.emit(mod_entry.name)

    # --- Public Methods
    def save_settings_state(self) -> None:
        self.settings.beginGroup("modlist/header")
        self.settings.setValue("state", self.mod_list.header().saveState())

        for column in range(self.mod_list.columnCount()):
            self.settings.setValue(
                f"column_width_{column}", self.mod_list.columnWidth(column)
            )

        self.settings.endGroup()

    def load_settings_state(self) -> None:
        self.settings.beginGroup("modlist/header")
        modlist_header_state = self.settings.value("state")

        if isinstance(modlist_header_state, QByteArray):
            self.mod_list.header().restoreState(modlist_header_state)

        for column in range(self.mod_list.columnCount()):
            column_width = self.settings.value(f"column_width_{column}")
            if isinstance(column_width, int):
                self.mod_list.setColumnWidth(column, int(column_width))
                self.mod_list_resized = True

        self.settings.endGroup()

    # --- Private Methods
    def _open_context_menu(self, pos) -> None:
        selected_items = self.mod_list.selectedItems()
        current_item = self.mod_list.itemAt(pos)

        if not current_item:
            return

        menu = QMenu(self)
        menu.addAction(self.tr("Refresh Mods"), self.refreshRequested.emit)
        menu.addSeparator()

        if len(selected_items) > 1:
            menu.addAction(
                self.tr("Enable All"),
                lambda: self._set_items_states(selected_items, True),
            )
            menu.addAction(
                self.tr("Disable All"),
                lambda: self._set_items_states(selected_items, False),
            )
            menu.addSeparator()
            menu.addAction(
                self.tr("Set Mod Author for All"),
                lambda: self._show_bulk_author_input_dialog(selected_items),
            )
            menu.addSeparator()
            menu.addAction(
                self.tr("Delete All Mods"),
                lambda: self._confirm_mods_deletion(selected_items),
            )
        else:
            if current_item.checkState(0) == Qt.CheckState.Checked:
                menu.addAction(
                    "Disable Mod", lambda: self._set_items_states(selected_items, False)
                )
            else:
                menu.addAction(
                    "Enable Mod", lambda: self._set_items_states(selected_items, True)
                )

            menu.addAction(
                self.tr("Set Mod Author"),
                lambda: self._show_author_input_dialog(current_item),
            )

            menu.addSeparator()
            menu.addAction(
                self.tr("Rename Mod"),
                lambda: self._show_rename_input_dialog(current_item),
            )
            menu.addAction(
                self.tr("Delete Mod"), lambda: self._confirm_mod_deletion(current_item)
            )
            menu.addAction(
                self.tr("Edit Modfile"), lambda: self._edit_modfile(current_item)
            )
            menu.addSeparator()

            mod_path = current_item.data(0, Qt.ItemDataRole.UserRole).mod.path
            menu.addAction(
                self.tr("Preview Mod"), lambda: self.modPreviewRequested.emit(
                    current_item.data(0, Qt.ItemDataRole.UserRole).mod.name
                )
            )
            menu.addAction(
                self.tr("Open Mod Folder"),
                lambda: self.openModFolderRequested.emit(mod_path),
            )

        menu.exec_(self.mod_list.mapToGlobal(pos))

    def _set_items_states(self, items: list[QTreeWidgetItem], value: bool) -> None:
        state = Qt.CheckState.Checked if value else Qt.CheckState.Unchecked

        self.mod_list.blockSignals(True)
        mods = []

        for item in items:
            if item.checkState(0) != state:
                mod_entry = item.data(0, Qt.ItemDataRole.UserRole)

                self._mod_item_cache[mod_entry.name] = item  # Ensure cache is updated

                item.setCheckState(0, state)

                mods.append(mod_entry.name)

        self.mod_list.blockSignals(False)

        self.modBulkStateChanged.emit(mods, value)
        
        self._update_mods_count_label()

    def _show_confirmation_dialog(
        self,
        title: str,
        msg: str,
        on_confirm: Callable[[], None]
    ) -> None:
        reply = QMessageBox.question(
            self,
            title,
            msg,
            QMessageBox.StandardButton.No | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            on_confirm()

    def _confirm_mod_deletion(self, item: QTreeWidgetItem) -> None:
        mod = item.data(0, Qt.ItemDataRole.UserRole)
        msg = self.tr('Are you sure you want to delete the mod "{mod_name}"?').format(
            mod_name=mod.name
        )
        self._show_confirmation_dialog(
            self.tr("Delete Mod"),
            msg,
            lambda: self.removeModRequested.emit(mod.name),
        )

    def _confirm_mods_deletion(self, items: list[QTreeWidgetItem]) -> None:
        msg = self.tr("Are you sure you want to delete {count} selected mods?").format(
            count=len(items)
        )
        def on_confirm():
            mod_names = [item.data(0, Qt.ItemDataRole.UserRole).name for item in items]
            self.removeModsRequested.emit(mod_names)

        self._show_confirmation_dialog(self.tr("Delete Mods"), msg, on_confirm)

    def _show_author_input_dialog(self, item: ModTreeItem) -> None:
        mod_entry = item.data(0, Qt.ItemDataRole.UserRole)
        author, ok = QInputDialog.getText(
            self,
            self.tr("Set Mod Author"),
            self.tr("Enter the author's name:"),
            text=mod_entry.author,
        )
        if ok and author and mod_entry.author != author:
            self.modAuthorChanged.emit(mod_entry.name, author)

    def _show_bulk_author_input_dialog(self, items: list[QTreeWidgetItem]) -> None:
        author, ok = QInputDialog.getText(
            self,
            self.tr("Set Mods Author"),
            self.tr("Enter the author's name:"),
            text="",
        )
        if not ok or not author:
            return

        mods_to_update = []
        
        for item in items:
            mod_entry = item.data(0, Qt.ItemDataRole.UserRole)
            if mod_entry.author != author:
                mods_to_update.append(mod_entry.name)

        if mods_to_update:
            self.modBulkAuthorChanged.emit(mods_to_update, author)

    def _show_rename_input_dialog(self, item: QTreeWidgetItem) -> None:
        mod_entry = item.data(0, Qt.ItemDataRole.UserRole)
        new_name, ok = QInputDialog.getText(
            self,
            self.tr("Rename Mod"),
            self.tr("Enter the new name for the mod:"),
            text=mod_entry.display_name,
        )
        if ok and new_name:
            self.renameModRequested.emit(mod_entry.name, new_name)


    def show_modfile_dialog(self, mod_name: str, modfile_data: dict) -> None:
        dialog = EditModfileDialog(self, mod_name, modfile_data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.modModfileChanged.emit(mod_name, dialog.modfile_data)

    def _populate_mod_item(
        self, item: QTreeWidgetItem, mod_entry: BD2ModEntry, show_full_path: bool = False
    ) -> None:
        char_name = mod_entry.character.full_name("-") if mod_entry.character else ""

        item.setData(0, Qt.ItemDataRole.UserRole, mod_entry)
        item.setData(0, CONFLICT_DATA_ROLE, mod_entry.has_conflict)  # has conflict
        item.setData(1, Qt.ItemDataRole.UserRole, mod_entry.character)
        item.setData(2, Qt.ItemDataRole.UserRole, mod_entry.mod.type)

        mod_name = (
            mod_entry.name.replace("/", " / ")
            if show_full_path
            else mod_entry.display_name
        )

        item.setText(0, mod_name)
        item.setText(1, char_name)
        item.setText(2, mod_entry.mod.type.display_name if mod_entry.mod.type else "")
        item.setText(3, mod_entry.author or "")

        item.setFlags(
            item.flags()
            | Qt.ItemFlag.ItemIsUserCheckable
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEnabled
        )
        item.setCheckState(
            0, Qt.CheckState.Checked if mod_entry.enabled else Qt.CheckState.Unchecked
        )

        item.setTextAlignment(0, Qt.AlignmentFlag.AlignVCenter)
        item.setTextAlignment(1, Qt.AlignmentFlag.AlignVCenter)
        item.setTextAlignment(
            2, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter
        )

    def set_mods(self, mods: List[BD2ModEntry], show_full_path: bool = False) -> None:
        pos_y = self.mod_list.verticalScrollBar().value()

        self._mod_item_cache.clear()
        self.mod_list.clear()

        self.mod_list.blockSignals(True)
        try:
            for mod_entry in mods:
                item = ModTreeItem()

                self._populate_mod_item(item, mod_entry, show_full_path)
                self.mod_list.addTopLevelItem(item)

                self._mod_item_cache[mod_entry.name] = item
        except Exception as e:
            logger.error("Error populating mod list: %s", e)
            self.showNotificationRequested.emit(
                "Error", self.tr("Failed to load mods"), str(e), 5000
            )
        finally:
            self.mod_list.blockSignals(False)

        try:
            self.mod_list.verticalScrollBar().setValue(pos_y)
        except Exception as e:
            logger.warning("Failed to restore scroll position: %s", e)

        if not self.mod_list_resized:
            self.mod_list.header().resizeSections(
                QHeaderView.ResizeMode.ResizeToContents
            )

        self._filter_mods()
        self._update_mods_count_label()

    def update_mods(
        self, mod_entries: List[BD2ModEntry], show_full_path: bool = False
    ) -> None:
        self.mod_list.blockSignals(True)

        for mod_entry in mod_entries:
            mod_item = self._mod_item_cache.get(mod_entry.name)
            
            if not mod_item:
                continue
            
            self._populate_mod_item(mod_item, mod_entry, show_full_path)
            

        self.mod_list.blockSignals(False)

        self._filter_mods()
        
        self._update_mods_count_label()

    def _update_mods_count_label(self) -> None:
        enabled_mods = len(
            [
                item
                for item in self.mod_list.findItems("", Qt.MatchFlag.MatchContains, 0)
                if item.checkState(0) == Qt.CheckState.Checked
            ]
        )
        total_mods = self.mod_list.topLevelItemCount()
        self.mods_count_label.setProperty("enabledMods", enabled_mods)
        self.mods_count_label.setProperty("totalMods", total_mods)
        self.mods_count_label.setText(
            self.tr("{} of {} mods enabled.").format(enabled_mods, total_mods)
        )

    def set_info_text(self, text: str) -> None:
        self.info_label.setText(text)
        
    def _filter_mods(self) -> None:
        search_type = self.search_type.currentData(Qt.ItemDataRole.UserRole)
        search_query = self.search_field.text().lower()
        types = {
            "idle": self.filter_chip_types["idle"].isChecked(),
            "cutscene": self.filter_chip_types["cutscene"].isChecked(),
            "scene": self.filter_chip_types["scene"].isChecked(),
            "dating": self.filter_chip_types["dating"].isChecked(),
            "npc": self.filter_chip_types["npc"].isChecked(),
        }
        types = {k: v for k, v in types.items() if v}
        types_active = len(types) > 0

        for index in range(self.mod_list.topLevelItemCount()):
            mod_item = self.mod_list.topLevelItem(index)
            if not mod_item:
                continue

            mod_entry: BD2ModEntry = mod_item.data(0, Qt.ItemDataRole.UserRole)

            matches_type = True
            if types_active:
                matches_type = False
                if types.get("scene") and mod_entry.mod.type == BD2ModType.SCENE:
                    matches_type = True
                if types.get("cutscene") and mod_entry.mod.type == BD2ModType.CUTSCENE:
                    matches_type = True
                if types.get("idle") and mod_entry.mod.type == BD2ModType.IDLE:
                    matches_type = True
                if types.get("dating") and mod_entry.mod.type == BD2ModType.DATING:
                    matches_type = True
                if types.get("npc") and mod_entry.mod.type == BD2ModType.NPC:
                    matches_type = True

            data = ""
            if search_type == "mod":
                data = mod_entry.mod.name
            elif search_type == "character":
                if mod_entry.character:
                    data = mod_entry.character.full_name()
            elif search_type == "author":
                data = mod_entry.author or ""

            matches_search = search_query in data.lower()

            mod_item.setHidden(not (matches_type and matches_search))

    # --- Signals

    @Slot(QTreeWidgetItem)
    def _edit_modfile(self, item: QTreeWidgetItem) -> None:
        mod_entry = item.data(0, Qt.ItemDataRole.UserRole)
        self.editModfileRequested.emit(mod_entry.name)

    # CONFIRMATION DIALOG
    def show_confirmation_dialog(self, title: str, text: str) -> bool:
        confirmation = QMessageBox.question(
            self,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        return confirmation == QMessageBox.StandardButton.Yes

    # PROGRESS MODAL
    def create_progress_modal(self) -> ProgressModal:
        """Create a new progress modal."""
        if self.progress_modal is None:
            self.progress_modal = ProgressModal(self)
        return self.progress_modal

    def remove_mods_from_view(self, mod_names: list[str]) -> None:
        """Remove mods from the view by its name."""
        
        for mod_name in mod_names:
            mod_item = self._mod_item_cache.pop(mod_name, None)

            if mod_item:
                index = self.mod_list.indexOfTopLevelItem(mod_item)
                if index != -1:
                    self.mod_list.takeTopLevelItem(index)
                    logger.debug(f"Removed mod '{mod_name}' from view.")
                else:
                    logger.error(f"Mod '{mod_name}' not found in view during removal.")
            else:
                logger.warning(f"Mod '{mod_name}' not found in cache during removal.")
    
    def add_mods_to_view(self, mod_entries: list[BD2ModEntry], show_full_path: bool = False):
        self.mod_list.blockSignals(True)
        try:
            for mod_entry in mod_entries:
                item = ModTreeItem()

                self._populate_mod_item(item, mod_entry, show_full_path)
                
                self.mod_list.addTopLevelItem(item)

                self._mod_item_cache[mod_entry.name] = item
        except Exception as e:
            logger.error("Error adding mod to mod list: %s", e)
            self.showNotificationRequested.emit(
                "Error", self.tr("Failed to add mod"), str(e), 5000
            )
        finally:
            self.mod_list.blockSignals(False)

        self._filter_mods()
        self._update_mods_count_label()
        
    def show_error_dialog(self, title: str, details: str):

        dialog = QMessageBox(self)
        dialog.setMinimumWidth(self.parent().width() * 0.6)
        dialog.setWindowTitle("Add Mods Failed")
        dialog.setIcon(QMessageBox.Icon.Warning)

        dialog.setTextFormat(Qt.TextFormat.RichText)
        dialog.setText(f"<h3>{title}</h3>")

        dialog.setInformativeText(
            "Please see details for a list of errors.<hr>"
        )
        dialog.setDetailedText(details)
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)

        dialog.setObjectName("errorDialog")
        
        spacer = QSpacerItem(600, 0, QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Expanding)
        layout = dialog.layout()
        layout.addItem(spacer, layout.rowCount(), 0, 1, layout.columnCount())

        dialog.exec()