from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QMenu,
    QInputDialog,
    QMessageBox,
    QGridLayout,
    QDialog,
    QComboBox,
    QSizePolicy
)
from PySide6.QtGui import QDragEnterEvent, QIcon, QShortcut, QKeySequence, QDragLeaveEvent, QAction
from PySide6.QtCore import Qt, Signal, QSettings, QByteArray, QSize

from src.utils.models import BD2ModEntry, BD2ModType

from src.widgets import DragFilesModal, ModItem, EditModfileDialog, ProgressModal
from src.widgets.widgets import ModItemTypeStyledDelegate

from src.widgets.widgets import CPushButton

from PySide6.QtWidgets import QStyleOption
from PySide6.QtGui import QPainter

from src.utils.theme_manager import ThemeManager

class ModsView(QWidget):
    modsRefreshRequested = Signal() 
    modsSyncRequested = Signal()
    modsUnsyncRequested = Signal()
    
    launchGameRequested = Signal()
    openModsFolderRequested = Signal()
    openModFolderRequested = Signal(str) # Mod Path
    
    addModRequested = Signal(str) # Mod path
    removeModRequested = Signal(BD2ModEntry) # Mod Name
    renameModRequested = Signal(BD2ModEntry, str) # Mod Name, New Name
    editModfileRequested = Signal(BD2ModEntry)

    modStateChanged = Signal(BD2ModEntry, bool) # Mod Name, Enabled State
    bulkModStateChanged = Signal(list, bool) # list[BD2ModEntry]
    modAuthorChanged = Signal(BD2ModEntry, str) # Mod Name, Author Name
    bulkModAuthorChanged = Signal(list, str) # [mod name], author name
    modModfileChanged = Signal(BD2ModEntry, dict)
    
    loaded = Signal()
    
    onSwitchProfileRequested = Signal(str)
    onCreateProfileRequested = Signal()
    
    showToastRequested = Signal(str, str, str, int)

    def __init__(self, settings: QSettings):
        super().__init__()
        self.setObjectName("modsView")
        self.setAcceptDrops(True)
        self.settings = settings

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*[0]*4)
        layout.setSpacing(0)

        self.drop_modal = DragFilesModal()
        self.drop_modal.hide()
        
        self.progress_modal = None
        
        # -> -> -> HEADER
        
        self.header_widget = QWidget()
        self.header_widget.setObjectName("modsHeader")
        self.header_layout = QGridLayout(self.header_widget)
        self.header_layout.setContentsMargins(*[12]*4)
        self.header_layout.setSpacing(0)

        self.title_label = QLabel("Mods")
        self.title_label.setObjectName("modsTitleLabel")
        self.mods_count_label = QLabel("123 of 342 mods enabled.")
        self.mods_count_label.setObjectName("modsCountLabel")
        
        self.refresh_button = CPushButton("Refresh")
        self.refresh_button.setContentAlignmentCentered(True)
        self.refresh_button.setObjectName("modsButton")
        self.refresh_button.setToolTip(self.tr("Refresh the list of mods"))
        # self.refresh_button.setIcon(QIcon(":/material/refresh.svg"))
        self.refresh_button.setProperty("iconName", "refresh")
        self.refresh_button.setIconSize(QSize(20, 20))
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.refresh_button.clicked.connect(self.modsRefreshRequested.emit)
        
        # self.header_layout.addWidget(self.title_label, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        # self.header_layout.addWidget(self.mods_count_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        # self.header_layout.addStretch()
        # self.header_layout.addWidget(self.refresh_button, alignment=Qt.AlignmentFlag.AlignRight)
        self.header_layout.addWidget(self.title_label, 0, 0, 1, 1)
        self.header_layout.addWidget(self.mods_count_label, 1, 0, 1, 1)
        self.header_layout.setColumnStretch(1, 1)
        self.header_layout.addWidget(self.refresh_button, 0, 2, 2, 1)
        # self.header_layout.setRowStretch(1, 1)
        
        # -> -> -> TOP BAR
        self.top_bar = QWidget()
        self.top_bar.setObjectName("modsTopBar")
        self.top_bar_layout = QVBoxLayout(self.top_bar)
        self.top_bar_layout.setContentsMargins(12, 0, 12, 8)
        self.top_bar_layout.setSpacing(6)

        self.search_area = QWidget()
        self.search_layout = QHBoxLayout(self.search_area)
        self.search_layout.setContentsMargins(0, 0, 0, 0)
        
        self.search_field = QLineEdit(placeholderText=self.tr("Search Mods"))
        self.search_field.setObjectName("searchField")
        self.search_field.textChanged.connect(self._search_field_changed)
        # self.search_field.addAction(QIcon(":/material/search.svg"), QLineEdit.ActionPosition.LeadingPosition)
        
        self.search_field_icon = QAction()
        self.search_field_icon.setProperty("iconName", "search")
        
        self.search_clear_action = QAction(self.search_field)
        self.search_clear_action.setProperty("iconName", "close")
        self.search_clear_action.triggered.connect(self._clear_search_field)
        self.search_clear_action.setVisible(False)
        # self.clear_search_action.setIcon(QIcon(":/material/close.svg"))
        # self.search_field.addAction(self.clear_search_action, QLineEdit.ActionPosition.TrailingPosition)
        
        self.search_type = QComboBox()
        self.search_type.setObjectName("searchType")
        self.search_type.addItems(("Mod", "Character", "Author"))
        self.search_type.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_type.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
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
        self.top_bar_layout.addWidget(self.mod_types_filter_widget, 0, alignment=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        
        # -> -> -> MOD LIST
        
        self.mod_list_area = QWidget()
        self.mod_list_area.setObjectName("modlistArea")
        self.mod_list_area_layout = QVBoxLayout(self.mod_list_area)
        self.mod_list_area_layout.setContentsMargins(12, 0, 12, 0)

        self.mod_list = QTreeWidget()
        self.mod_list.setObjectName("modlist")
        self.mod_list.setHeaderLabels([self.tr("Mod Name"), self.tr("Character"), self.tr("Type"), self.tr("Author")])
        self.mod_list.setSortingEnabled(True)
        self.mod_list.setRootIsDecorated(False)
        self.mod_list.setAlternatingRowColors(True)
        self.mod_list.header().setObjectName("modlistHeader")
        self.mod_list.header().setFixedHeight(32)
        self.mod_list.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.mod_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.mod_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.mod_list.setContentsMargins(0, 0, 0, 0)
        self.mod_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.mod_list.setSelectionMode(QHeaderView.SelectionMode.ExtendedSelection)
        # self.mod_list.setItemDelegateForColumn(0, ModItemModNameDelegate()) # mod name to show conflict icon
        # self.mod_list.setItemDelegateForColumn(1, ModItemCharacterDelegate())
        self.mod_list.setItemDelegateForColumn(2, ModItemTypeStyledDelegate())
        self.mod_list.sortItems(1, Qt.SortOrder.AscendingOrder) # filter by character in alphabetical order
        self.mod_list.customContextMenuRequested.connect(self.show_context_menu)
        self.mod_list.itemChanged.connect(self._mod_state_changed)
        self.mod_list_resized = False
        
        self.mod_list_area_layout.addWidget(self.mod_list, 1)
        
        # -> -> -> FOOTER BAR
        
        self.footer_bar = QWidget()
        self.footer_bar.setObjectName("modsFooterBar")
        self.footer_bar_layout = QHBoxLayout(self.footer_bar)
        self.footer_bar_layout.setContentsMargins(12, 8, 12, 8)

        self.info_label = QLabel()
        self.info_label.setObjectName("modsInfoLabel")

        self.actions_widget = QWidget()
        self.actions_layout = QHBoxLayout(self.actions_widget)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)

        self.open_mods_folder_button = CPushButton(self.tr("Open Mods Folder"))
        self.open_mods_folder_button.setObjectName("modsButton")
        self.open_mods_folder_button.setContentAlignmentCentered(True)
        self.open_mods_folder_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_mods_folder_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.open_mods_folder_button.setIcon(QIcon(":/material/folder.svg"))
        self.open_mods_folder_button.setProperty("iconName", "folder")
        self.open_mods_folder_button.clicked.connect(self.openModsFolderRequested.emit)

        self.sync_button = CPushButton(self.tr("Sync Mods"))
        self.sync_button.setContentAlignmentCentered(True)
        self.sync_button.clicked.connect(self.modsSyncRequested.emit)
        self.sync_button.setObjectName("modsButton")
        self.sync_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sync_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.sync_button.setIcon(QIcon(":/material/sync.svg"))
        self.sync_button.setProperty("iconName", "sync")

        self.unsync_button = CPushButton(self.tr("Unsync Mods"))
        self.unsync_button.setObjectName("modsButton")
        self.unsync_button.setContentAlignmentCentered(True)
        self.unsync_button.clicked.connect(self.modsUnsyncRequested.emit)
        self.unsync_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.unsync_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.unsync_button.setIcon(QIcon(":/material/unsync.svg"))
        self.unsync_button.setProperty("iconName", "unsync")

        self.actions_layout.addWidget(self.open_mods_folder_button)
        self.actions_layout.addWidget(self.unsync_button)
        self.actions_layout.addWidget(self.sync_button)

        self.footer_bar_layout.addWidget(self.info_label)
        self.footer_bar_layout.addWidget(self.actions_widget)
        
        # -> -> -> SHORTCUTS
        QShortcut(QKeySequence("Ctrl+A"), self.mod_list).activated.connect(self.mod_list.selectAll)
        QShortcut(QKeySequence("Ctrl+F"), self.search_field).activated.connect(self.search_field.setFocus)
        QShortcut(QKeySequence("Ctrl+R"), self.refresh_button).activated.connect(self.refresh_button.click)
        
        # -> -> -> LAYOUTS
        layout.addWidget(self.drop_modal)
        layout.addWidget(self.header_widget)
        layout.addWidget(self.top_bar, 0)
        layout.addWidget(self.mod_list_area, 1)
        layout.addWidget(self.footer_bar, 0, Qt.AlignmentFlag.AlignBottom)
        
        self._check_mods_conflicts()
        
        self._first_time = True
        self.load_settings_state()
    
    def updateIcons(self):
        for action in self.search_field.actions():
            self.search_field.removeAction(action)
        
        self.search_field_icon.setIcon(ThemeManager.icon(self.search_field_icon))
        self.search_clear_action.setIcon(ThemeManager.icon(self.search_clear_action))

        self.search_field.addAction(self.search_field_icon, QLineEdit.ActionPosition.LeadingPosition)
        self.search_field.addAction(self.search_clear_action, QLineEdit.ActionPosition.TrailingPosition)
        
        self.search_clear_action.setVisible(False)
        
        self.refresh_button.setIcon(ThemeManager.icon(self.refresh_button))
        self.open_mods_folder_button.setIcon(ThemeManager.icon(self.open_mods_folder_button.property("iconName")))
        self.sync_button.setIcon(ThemeManager.icon(self.sync_button.property("iconName")))
        self.unsync_button.setIcon(ThemeManager.icon(self.unsync_button.property("iconName")))

    def _clear_search_field(self):
        self.search_field.clear()
    
    def _search_field_changed(self):
        if len(self.search_field.text()) > 0:
            if not self.search_clear_action.isVisible():
                self.search_clear_action.setVisible(True)
        else:
            if self.search_clear_action.isVisible():
                self.search_clear_action.setVisible(False)
                
        self._filter_mods()
        
    def paintEvent(self, event):
        option = QStyleOption()
        option.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(self.style().PrimitiveElement.PE_Widget, option, painter, self)
        
    def showEvent(self, event):
        if self._first_time:
            self.loaded.emit()
            self._first_time = False
    
    def retranslateUI(self):
        self.search_field.setPlaceholderText(self.tr("Search Mods"))
        self.refresh_button.setText(self.tr("Refresh Mods"))
        self.open_mods_folder_button.setText(self.tr("Open Mods Folder"))
        self.sync_button.setText(self.tr("Sync Mods"))
        self.unsync_button.setText(self.tr("Unsync Mods"))
        self.mod_list.setHeaderLabels([self.tr("Mod Name"), self.tr("Character"), self.tr("Type"), self.tr("Author")])
    
    def save_settings_state(self):
        self.settings.beginGroup("modlist/header")
        self.settings.setValue("state", self.mod_list.header().saveState())
        
        for column in range(self.mod_list.columnCount()):
            self.settings.setValue(f"column_width_{column}", self.mod_list.columnWidth(column))
        
        self.settings.endGroup()
    
    def load_settings_state(self):
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
    
    def show_context_menu(self, pos):
        selected_items = self.mod_list.selectedItems()
        current_item = self.mod_list.itemAt(pos)
        
        if not current_item:
            return
                
        menu = QMenu(self)
        menu.addAction(self.tr("Refresh Mods"), self.modsRefreshRequested.emit)
        menu.addSeparator()
        
        if len(selected_items) > 1:            
            menu.addAction(self.tr("Enable All"), lambda: self._enable_disable_mods(selected_items, True))
            menu.addAction(self.tr("Disable All"), lambda: self._enable_disable_mods(selected_items, False))
            menu.addSeparator()
            menu.addAction(self.tr("Set Mod Author for All"), lambda: self._bulk_show_author_input_dialog(selected_items))
            menu.addSeparator()
            menu.addAction(self.tr("Remove Mods"), lambda: self._confirm_mods_deletion(selected_items))
        else:
            if current_item.checkState(0) == Qt.CheckState.Checked:
                menu.addAction("Disable Mod", lambda: self._enable_disable_mods(selected_items, False))
            else:
                menu.addAction("Enable Mod", lambda: self._enable_disable_mods(selected_items, True))
    
            menu.addAction(self.tr("Set Mod Author"), lambda: self._show_author_input_dialog(current_item))
                
            menu.addSeparator()
            menu.addAction(self.tr("Rename Mod"), lambda: self._show_rename_input_dialog(current_item))
            menu.addAction(self.tr("Delete Mod"), lambda: self._confirm_mod_deletion(current_item))
            menu.addAction(self.tr("Edit Modfile"), lambda: self._edit_modfile(current_item))
            menu.addSeparator()
            
            mod_path = current_item.data(0, Qt.ItemDataRole.UserRole).mod.path
            menu.addAction(self.tr("Open Mod Folder"), lambda: self.openModFolderRequested.emit(mod_path))

        menu.exec_(self.mod_list.mapToGlobal(pos))
    
    #
    # WIDGET EVENTS
    #
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            self.drop_modal.show()
            return event.acceptProposedAction()
        self.drop_modal.hide()
        return event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self.drop_modal.hide()
        return super().dragLeaveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                self.addModRequested.emit(file_path)
                self.drop_modal.hide()
    #
    # WIDGET EVENTS
    #
    def _enable_disable_mods(self, items: list[QTreeWidgetItem], value: bool):
        state = Qt.CheckState.Checked if value else Qt.CheckState.Unchecked
        
        mods = []
        
        self.mod_list.blockSignals(True)
        for item in items:
            if item.checkState(0) != state:
                mod = item.data(0, Qt.ItemDataRole.UserRole)
                mod.enabled = value
                item.setCheckState(0, state)      
                mods.append(mod) # BD2ModEntry
        self.mod_list.blockSignals(False)
                
        self.bulkModStateChanged.emit(mods, value)

    def _show_author_input_dialog(self, item: QTreeWidgetItem):
        mod = item.data(0, Qt.ItemDataRole.UserRole)
        author, ok = QInputDialog.getText(self, self.tr("Set Mod Author"), self.tr("Enter the author's name:"), text=mod.author)
        if ok and author:
            if mod.author != author:
                mod.author = author
                item.setData(0, Qt.ItemDataRole.UserRole, mod)
                item.setText(3, author)
                self.modAuthorChanged.emit(mod, author)
    
    def _bulk_show_author_input_dialog(self, items: list[QTreeWidgetItem]):
        author, ok = QInputDialog.getText(self, self.tr("Set Mods Author"), self.tr("Enter the author's name:"), text="")
        
        mods = []
        
        if ok:
            self.mod_list.blockSignals(True)
            
            for item in items:
                mod = item.data(0, Qt.ItemDataRole.UserRole)
                
                if mod.author != author:
                    mod.author = author
                    item.setData(0, Qt.ItemDataRole.UserRole, mod)
                    item.setText(3, author)
                    
                    mods.append(mod)
                    
            self.mod_list.blockSignals(False)  
            
            self.bulkModAuthorChanged.emit(mods, author)

    def _show_rename_input_dialog(self, item: QTreeWidgetItem):
        mod_entry = item.data(0, Qt.ItemDataRole.UserRole)
        new_name, ok = QInputDialog.getText(self, self.tr("Rename Mod"), self.tr("Enter the new name for the mod:"), text=mod_entry.mod.name)
        if ok and new_name:
            self.renameModRequested.emit(mod_entry, new_name)
    
    def _confirm_mod_deletion(self, item: QTreeWidgetItem):
        mod = item.data(0, Qt.ItemDataRole.UserRole)
        msg_template = self.tr("Are you sure you want to delete the mod \"{mod_name}\"?")
        msg = msg_template.format(mod_name=mod.mod.name)
        reply = QMessageBox.question(
            self,
            self.tr("Delete Mod"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.removeModRequested.emit(mod)
            # self._refresh_mods()
    
    def _confirm_mods_deletion(self, items: list[QTreeWidgetItem]):
        msg_template = self.tr("Are you sure you want to delete {count} selected mods?")
        msg = msg_template.format(count=len(items))
        
        reply = QMessageBox.question(
            self,
            self.tr("Delete Mods"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            for item in items:
                mod = item.data(0, Qt.ItemDataRole.UserRole)
                self.removeModRequested.emit(mod)

    def _filter_mods(self):
        search_type = self.search_type.currentText()
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
            if search_type == "Mod":
                data = mod_entry.mod.name
            elif search_type == "Character":
                if mod_entry.character:
                    data = mod_entry.character.full_name()
            elif search_type == "Author":
                data = mod_entry.author or ""
                
            matches_search = search_query in data.lower()

            mod_item.setHidden(not (matches_type and matches_search))
    
    def _mod_state_changed(self, item: QTreeWidgetItem):
        mod_data = item.data(0, Qt.ItemDataRole.UserRole)
        mod_state = item.checkState(0)
        self.modStateChanged.emit(mod_data, mod_state == Qt.CheckState.Checked)
    
    def _check_mods_conflicts(self):
        self.mod_list.blockSignals(True)
        for index in range(self.mod_list.topLevelItemCount()):
            item = self.mod_list.topLevelItem(index)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, False)
            
        mod_groups = {}
        for index in range(self.mod_list.topLevelItemCount()):
            item = self.mod_list.topLevelItem(index)
            mod_data = item.data(0, Qt.ItemDataRole.UserRole)
            
            if not mod_data.enabled:
                continue
            
            char = mod_data.character
            
            if not char:
                continue
            
            key = (mod_data.mod.type, char.id)
            
            mod_groups.setdefault(key, []).append(item)
        
        for items in mod_groups.values():
            if len(items) > 1:
                for item in items:
                    item.setData(0, Qt.ItemDataRole.UserRole + 1, True)
        
        self.mod_list.blockSignals(False)

    def update_mods(self, mods: List[BD2ModEntry]):
        pos_y = self.mod_list.verticalScrollBar().value()
        self.mod_list.clear()

        self.mod_list.blockSignals(True)
        for mod_entry in mods:
            char_name = mod_entry.character.full_name('-') if mod_entry.character else ""

            item = ModItem()
            item.setData(0, Qt.ItemDataRole.UserRole, mod_entry)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, False) # has conflict
            item.setData(1, Qt.ItemDataRole.UserRole, mod_entry.character)
            item.setData(2, Qt.ItemDataRole.UserRole, mod_entry.mod.type)
            
            if mod_entry.mod.relative_name:
                item.setText(0, mod_entry.mod.relative_name)
            else:
                item.setText(0, mod_entry.mod.name)
                
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
            item.setTextAlignment(2, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
            
            self.mod_list.addTopLevelItem(item)

        self.mod_list.blockSignals(False)
        
        self.mod_list.verticalScrollBar().setValue(pos_y)
        
        if not self.mod_list_resized:
            self.mod_list.header().resizeSections(QHeaderView.ResizeMode.ResizeToContents)
            
        self._check_mods_conflicts()
        self._filter_mods()

    
    def _edit_modfile(self, item: QTreeWidgetItem):
        mod_entry = item.data(0,  Qt.ItemDataRole.UserRole)
        self.editModfileRequested.emit(mod_entry)

    def set_info_text(self, text: str):
        self.info_label.setText(text)
    
    def show_modfile_dialog(self, mod: BD2ModEntry, modfile_data: dict):
        dialog = EditModfileDialog(self, mod.mod.name, modfile_data)
        if dialog.exec_() == QDialog.DialogCode.Accepted:
            self.modModfileChanged.emit(mod, dialog.modfile_data)
    
    def show_toast(self, title: Optional[str] = None, text: Optional[str] = None, type: Optional[str] = None, duration: int = 3000):
        
        showToastRequested.emit(title, text, type, duration)
    
    # CONFIRMATION DIALOG
    def show_confirmation_dialog(self, title: str, text: str):
        confirmation = QMessageBox.question(
            self,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        return confirmation == QMessageBox.StandardButton.Yes
    
    # PROGRESS MODAL
    def show_progress_modal(self, text: str):
        if self.progress_modal is None:
            self.progress_modal = ProgressModal(self)
            
        self.progress_modal.set_text(text)
        
        self.progress_modal.on_started()
        
        self.progress_modal.show()
    
    def update_progress_modal(self, value: int, max: int, text: Optional[str] = None):
        if self.progress_modal:
            self.progress_modal.update_progress(value, max, text)
        
    def progress_modal_started(self):
        if self.progress_modal:
            self.progress_modal.on_started()
    
    def progress_modal_finished(self):
        if self.progress_modal:
            self.progress_modal.on_finished()

    def progress_modal_error(self):
        if self.progress_modal:
            self.progress_modal.on_error()