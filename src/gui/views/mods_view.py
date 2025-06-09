from PySide6.QtCore import Qt, Signal, QSize, QSettings, QByteArray
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QFileDialog,
    QHeaderView,
    QMenu,
    QInputDialog,
    QMessageBox,
    QStyledItemDelegate,
    QComboBox,
    QGridLayout, QToolButton
)
from PySide6.QtGui import QDragEnterEvent, QIcon, QShortcut, QKeySequence, QColor, QPalette

from pathlib import Path
from src.BD2ModManager.models import BD2ModEntry, BD2ModType

class DragFilesModal(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Drop Modal")
        # self.setFixedSize(300, 150)
        self.setObjectName("dragFilesModal")

        # Layout and widgets
        layout = QVBoxLayout()
        label = QLabel("Drop your mod files here to add them!")
        label.setObjectName("dragFilesTitle")

        layout.addWidget(label, 1, Qt.AlignmentFlag.AlignHCenter)
        
        self.setLayout(layout)
        
class ModItemStyledDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        
        has_conflict = index.data(Qt.ItemDataRole.UserRole + 1)
        
        option.palette.setColor(QPalette.Text, QColor('#ecf0f1'))
        
        if has_conflict:
            option.palette.setColor(QPalette.Text, QColor('#B4656F'))
            
            icon = QIcon(":/material/report.svg")
            
            icon_size = option.decorationSize
            
            if icon_size.width() == 0 or icon_size.height() == 0:
                icon_size = QSize(16, 16)  

            x = option.rect.right() - icon_size.width() - 8 
            y = option.rect.top() + (option.rect.height() - icon_size.height()) // 2

            icon.paint(painter, x, y, icon_size.width(), icon_size.height())


        # super().paint(painter, option, index)

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        icon_size = option.decorationSize
        if icon_size.width() == 0:
            icon_size.setWidth(16)
        size.setWidth(size.width() + icon_size.width() + 8)  # espaço extra para o ícone
        return size
        
        # painter.fillRect(option.rect, QColor("#B4656F"))

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

class FilterWidget(QWidget):
    filterChanged = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("filterWidget")
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.chip_types = {
            "idle": QToolButton(text="Idle"),
            "cutscene": QToolButton(text="Cutscene"),
            "scene": QToolButton(text="Scene"),
            "dating": QToolButton(text="Dating"),
            "npc": QToolButton(text="NPC"),
        }

        for btn in self.chip_types.values():
            btn.setCheckable(True)
            btn.setChecked(False)
            btn.clicked.connect(self.filterChanged.emit)
            btn.setObjectName("filterChip")
            layout.addWidget(btn)

    def get_types(self):
        return {
            "idle": self.chip_types["idle"].isChecked(),
            "cutscene": self.chip_types["cutscene"].isChecked(),
            "scene": self.chip_types["scene"].isChecked(),
            "dating": self.chip_types["dating"].isChecked(),
            "npc": self.chip_types["npc"].isChecked()
        }
        
        
class ModsView(QWidget):
    modsRefreshRequested = Signal() 
    modsSyncRequested = Signal()
    modsUnsyncRequested = Signal()
    
    openModsFolderRequested = Signal()
    
    addModRequested = Signal(str) # Mod path
    removeModRequested = Signal(BD2ModEntry) # Mod Name
    renameModRequested = Signal(BD2ModEntry, str) # Mod Name, New Name
    editModfileRequested = Signal(BD2ModEntry)

    modStateChanged = Signal(BD2ModEntry, bool) # Mod Name, Enabled State
    bulkModStateChanged = Signal(list, bool) # list[BD2ModEntry]
    
    modAuthorChanged = Signal(BD2ModEntry, str) # Mod Name, Author Name
    bulkModAuthorChanged = Signal(list, str) # [mod name], author name
    openModFolderRequested = Signal(str) # Mod Path
    
    launchGameRequested = Signal()

    def __init__(self, settings: QSettings):
        super().__init__()
        self.setObjectName("modsView")
        self.setAcceptDrops(True)
        
        self.settings = settings

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # Variables
        self.drop_modal = DragFilesModal()
        self.drop_modal.hide()
        layout.addWidget(self.drop_modal, 0)

        self.top_bar = QWidget()
        self.top_bar.setObjectName("topBar")
        self.top_bar_layout = QGridLayout(self.top_bar)
        self.top_bar_layout.setContentsMargins(0, 0, 0, 0)

        self.search_field = QLineEdit(placeholderText=self.tr("Search Mods"))
        self.search_field.setObjectName("searchField")
        self.search_field.addAction(QIcon(":/material/search.svg"), QLineEdit.ActionPosition.LeadingPosition)
        self.search_field.textChanged.connect(self._filter_search_changed)
        
        self.search_type = QComboBox()
        self.search_type.setObjectName("searchCombobox")
        self.search_type.addItems(("Mod", "Character", "Author"))
        self.search_type.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_type.currentIndexChanged.connect(self._filter_search_changed)

        self.refresh_button = QPushButton(self.tr("Refresh Mods"))
        self.refresh_button.setObjectName("modsViewButton")
        self.refresh_button.setToolTip(self.tr("Refresh the list of mods"))
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.refresh_button.clicked.connect(self._refresh_mods)
        self.refresh_button.setIcon(QIcon(":/material/refresh.svg"))
        
        self.start_game_button = QPushButton(self.tr("Start BrownDust II"))
        self.start_game_button.setObjectName("modsViewButton")
        self.start_game_button.setToolTip(self.tr("Launch Brown Dust 2"))
        self.start_game_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_game_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.start_game_button.setIcon(QIcon(":/material/exit_to_app.svg"))
        self.start_game_button.clicked.connect(self.launchGameRequested.emit)

        # self.add_mod_button = QPushButton(self.tr("Add Mod"))
        # self.add_mod_button.setObjectName("modsViewButton")
        # self.add_mod_button.setToolTip(self.tr("Add a new mod"))
        # self.add_mod_button.setCursor(Qt.CursorShape.PointingHandCursor)
        # self.add_mod_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.add_mod_button.setIcon(QIcon(":/material/add.svg"))
        # self.add_mod_button.clicked.connect(self._add_mod)
                
        self.filter_widget = FilterWidget()
        self.filter_widget.filterChanged.connect(self._filter_types_changed)
        self.filter_widget.hide()
        
        self.filter_icon = QPushButton()
        self.filter_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self.filter_icon.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.filter_icon.setObjectName("modsViewButton")
        self.filter_icon.setIcon(QIcon(":/material/filter_alt.svg"))
        self.filter_icon.clicked.connect(lambda: self.filter_widget.show() if self.filter_widget.isHidden() else self.filter_widget.hide())

        self.top_bar_layout.addWidget(self.filter_icon, 0, 0)
        self.top_bar_layout.addWidget(self.search_field, 0, 1)
        self.top_bar_layout.addWidget(self.search_type, 0, 2)
        self.top_bar_layout.addWidget(self.refresh_button, 0, 3)
        # self.top_bar_layout.addWidget(self.add_mod_button, 0, 4)
        self.top_bar_layout.addWidget(self.start_game_button, 0, 4)
        self.top_bar_layout.addWidget(self.filter_widget, 1, 0, 1, 4, Qt.AlignmentFlag.AlignLeft)

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
        self.mod_list.setItemDelegateForColumn(0, ModItemStyledDelegate())
        self.mod_list.sortItems(1, Qt.SortOrder.AscendingOrder) # filter by character in alphabetical order
        self.mod_list.customContextMenuRequested.connect(self.show_context_menu)
        self.mod_list.itemChanged.connect(self._mod_state_changed)
        self.mod_list_resized = False
        
        self.load_settings_state()
        
        shortcut = QShortcut(QKeySequence("Ctrl+A"), self.mod_list)
        shortcut.activated.connect(self.mod_list.selectAll)
        
        self.footer_bar = QWidget()
        self.footer_bar.setObjectName("footerBar")
        self.footer_bar_layout = QHBoxLayout(self.footer_bar)
        self.footer_bar_layout.setContentsMargins(0, 0, 0, 0)

        self.info_label = QLabel()
        self.info_label.setObjectName("infoLabel")

        self.actions_widget = QWidget()
        self.actions_layout = QHBoxLayout(self.actions_widget)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)

        self.open_mods_folder_button = QPushButton(self.tr("Open Mods Folder"))
        self.open_mods_folder_button.setObjectName("modsViewButton")
        self.open_mods_folder_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_mods_folder_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.open_mods_folder_button.setIcon(QIcon(":/material/folder.svg"))
        self.open_mods_folder_button.clicked.connect(self.openModsFolderRequested.emit)

        self.sync_button = QPushButton(self.tr("Sync Mods"))
        self.sync_button.clicked.connect(self.modsSyncRequested.emit)
        self.sync_button.setObjectName("modsViewButton")
        self.sync_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sync_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.sync_button.setIcon(QIcon(":/material/sync.svg"))

        self.unsync_button = QPushButton(self.tr("Unsync Mods"))
        self.unsync_button.clicked.connect(self.modsUnsyncRequested.emit)
        self.unsync_button.setObjectName("unsyncButton")
        self.unsync_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.unsync_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.unsync_button.setObjectName("modsViewButton")
        self.unsync_button.setIcon(QIcon(":/material/unsync.svg"))

        self.actions_layout.addWidget(self.open_mods_folder_button)
        self.actions_layout.addWidget(self.unsync_button)
        self.actions_layout.addWidget(self.sync_button)

        self.footer_bar_layout.addWidget(self.info_label)
        self.footer_bar_layout.addWidget(self.actions_widget)

        layout.addWidget(self.top_bar)
        layout.addWidget(self.mod_list)
        layout.addWidget(self.footer_bar)
        
        self._check_all_mod_conflicts()
    
    def save_settings_state(self):
        self.settings.beginGroup("modlist/header")
        self.settings.setValue("state", self.mod_list.header().saveState())
        
        for column in range(self.mod_list.columnCount()):
            self.settings.setValue(f"column_width_{column}", self.mod_list.columnWidth(column))
        
        self.settings.endGroup()
        # self.settings.setValue("modlist/HeaderGeometry", self.mod_list.header().saveGeometry())
    
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

    def retranslateUI(self):
        self.setWindowTitle(self.tr("Mods Manager"))
        self.search_field.setPlaceholderText(self.tr("Search Mods"))
        self.refresh_button.setText(self.tr("Refresh Mods"))
        # self.add_mod_button.setText(self.tr("Add Mod"))
        self.open_mods_folder_button.setText(self.tr("Open Mods Folder"))
        self.sync_button.setText(self.tr("Sync Mods"))
        self.unsync_button.setText(self.tr("Unsync Mods"))
        self.mod_list.setHeaderLabels([self.tr("Mod Name"), self.tr("Character"), self.tr("Type"), self.tr("Author")])
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            self.drop_modal.show()
            return event.acceptProposedAction()

        return event.ignore()

    def dragLeaveEvent(self, event: QDragEnterEvent) -> None:
        self.drop_modal.hide()
        return super().dragLeaveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                self.addModRequested.emit(file_path)
                self.drop_modal.hide()
    
    def show_context_menu(self, pos):
        selected_items = self.mod_list.selectedItems()
        current_item = self.mod_list.itemAt(pos)
        
        if not current_item:
            return
                
        menu = QMenu(self)
        menu.addAction(self.tr("Refresh Mods"), self._refresh_mods)
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
            
            mod_path = current_item.data(0, Qt.ItemDataRole.UserRole).path
            menu.addAction(self.tr("Open Mod Folder"), lambda: self.openModFolderRequested.emit(mod_path))

        menu.exec_(self.mod_list.mapToGlobal(pos))

    def _enable_disable_mods(self, items: list[QTreeWidgetItem], value: bool):
        state = Qt.CheckState.Checked if value else Qt.CheckState.Unchecked
        
        mods = []
        
        for item in items:
            if item.checkState(0) != state:
                mod = item.data(0, Qt.ItemDataRole.UserRole)
                mod.enabled = value
                item.setCheckState(0, state)      
                mods.append(mod) # BD2ModEntry
                
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
        if ok and author:
            for item in items:
                mod = item.data(0, Qt.ItemDataRole.UserRole)
                if mod.author != author:
                    mod.author = author
                    item.setData(0, Qt.ItemDataRole.UserRole, mod)
                    item.setText(3, author)
                    
                    mods.append(mod)
                            
        self.bulkModAuthorChanged.emit(mods, author)

    def _show_rename_input_dialog(self, item: QTreeWidgetItem):
        mod_entry = item.data(0, Qt.ItemDataRole.UserRole)
        new_name, ok = QInputDialog.getText(self, self.tr("Rename Mod"), self.tr("Enter the new name for the mod:"), text=mod_entry.mod.name)
        if ok and new_name:
            self.renameModRequested.emit(mod_entry, new_name)
            mod_entry.mod.name = new_name
            
            # Temporary until I think in something better
            self._refresh_mods()
    
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
            self._refresh_mods()
    
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
                
            self._refresh_mods()
    
    def _filter_search_changed(self):
        self._filter_mods()
    
    def _filter_types_changed(self):
        self._filter_mods()

    def _filter_mods(self):
        search_type = self.search_type.currentText()
        search_query = self.search_field.text().lower()
        types = {k: v for k, v in self.filter_widget.get_types().items() if v}
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
        
    def _refresh_mods(self):
        self.modsRefreshRequested.emit()
        self._filter_mods()

    def _add_mod(self):
        filename, _ = QFileDialog.getOpenFileName(self, self.tr("Select Modfile"), "", "*.modfile")
        if filename:
            path = str(Path(filename).parent)
            self.addModRequested.emit(path)
    
    def _edit_modfile(self, item: QTreeWidgetItem):
        mod_entry = item.data(0,  Qt.ItemDataRole.UserRole)
        self.editModfileRequested.emit(mod_entry)

    def _mod_state_changed(self, item: QTreeWidgetItem):
        mod_data = item.data(0, Qt.ItemDataRole.UserRole)
        mod_state = item.checkState(0)
        
        # TODO: add check if it is the same

        item.setData(0, Qt.ItemDataRole.UserRole, mod_data)
        self.modStateChanged.emit(mod_data, mod_state == Qt.CheckState.Checked)
    
    def _check_all_mod_conflicts(self):
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

    def load_mods(self, mods: list[BD2ModEntry]):
        self.mod_list.blockSignals(True)
        
        pos_y = self.mod_list.verticalScrollBar().value()
        self.mod_list.clear()

        for mod_entry in mods:
            char_name = mod_entry.character.full_name('-') if mod_entry.character else ""

            item = ModItem()
            item.setData(0, Qt.ItemDataRole.UserRole, mod_entry)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, False) # has conflict

            # if mod_entry.mod.relative_name:
            #     item.setText(0, mod_entry.mod.relative_name)
            # else:
            item.setText(0, mod_entry.mod.name)
                
            item.setText(1, char_name)
            item.setText(2, mod_entry.mod.type.display_name if mod_entry.mod.type else "")
            item.setText(3, mod_entry.author)
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
        self._check_all_mod_conflicts()

    def set_info_text(self, text: str):
        self.info_label.setText(text)