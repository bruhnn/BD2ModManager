from PySide6.QtCore import Qt, Signal
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
    QStyleOptionViewItem,
    QStyle,
)
from PySide6.QtGui import QDragEnterEvent, QIcon, QShortcut, QKeySequence, QColor, QBrush, QPalette



class DragFilesModal(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFixedSize(300, 120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.setStyleSheet("""
            background: rgba(30, 30, 30, 220);
            border-radius: 12px;
            border: 2px solid #888;
        """)

        self.label = QLabel(text="Drop Files")

        layout.addWidget(self.label)

        self.hide()
        self.raise_()

    
class ModItemStyledDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        has_conflict = index.data(Qt.ItemDataRole.UserRole + 1)
          
        option.palette.setColor(QPalette.Text, QColor('#ecf0f1'))
        if has_conflict:
            option.palette.setColor(QPalette.Text, QColor('#B4656F'))
            
        super().paint(painter, option, index)
        
        # painter.fillRect(option.rect, QColor("#B4656F"))
        
class ModsView(QWidget):
    modsRefreshRequested = Signal() 
    modsSyncRequested = Signal()
    modsUnsyncRequested = Signal()
    
    openModsFolderRequested = Signal()
    
    addModRequested = Signal(str) # Mod path
    removeModRequested = Signal(str) # Mod Name
    renameModRequested = Signal(str, str) # Mod Name, New Name

    modStateChanged = Signal(str, bool) # Mod Name, Enabled State
    modAuthorChanged = Signal(str, str) # Mod Name, Author Name
    openModFolderRequested = Signal(str) # Mod Path

    def __init__(self):
        super().__init__()
        self.setObjectName("modsView")
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # Variables
        self._modlist_loaded = False
        self._has_conflict_highlights = False

        self.drop_modal = DragFilesModal(self)

        self.top_bar = QWidget()
        self.top_bar.setObjectName("topBar")
        self.top_bar_layout = QHBoxLayout(self.top_bar)
        self.top_bar_layout.setContentsMargins(0, 0, 0, 0)

        self.search_field = QLineEdit(placeholderText=self.tr("Search Mods"))
        self.search_field.setObjectName("searchField")
        self.search_field.addAction(QIcon(":/material/search.svg"), QLineEdit.ActionPosition.LeadingPosition)
        self.search_field.textChanged.connect(self._filter_search)

        self.refresh_button = QPushButton(self.tr("Refresh Mods"))
        self.refresh_button.setObjectName("modsViewButton")
        self.refresh_button.setToolTip(self.tr("Refresh the list of mods"))
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.clicked.connect(self._refresh_mods)
        self.refresh_button.setIcon(QIcon(":/material/refresh.svg"))

        self.add_mod_button = QPushButton(self.tr("Add Mod"))
        self.add_mod_button.setObjectName("modsViewButton")
        self.add_mod_button.setToolTip(self.tr("Add a new mod"))
        self.add_mod_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_mod_button.setIcon(QIcon(":/material/add.svg"))
        self.add_mod_button.clicked.connect(self._add_mod)

        self.top_bar_layout.addWidget(self.search_field)
        self.top_bar_layout.addWidget(self.refresh_button)
        self.top_bar_layout.addWidget(self.add_mod_button)

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
        self.mod_list.itemChanged.connect(self._mod_state_changed)
        # self.mod_list.itemSelectionChanged.connect(self._check_mod_conflicts)
        self.mod_list.customContextMenuRequested.connect(self.show_context_menu)
        self.mod_list.setItemDelegate(ModItemStyledDelegate())
        
        shortcut = QShortcut(QKeySequence("Ctrl+A"), self.mod_list)
        shortcut.activated.connect(self.mod_list.selectAll)
        
        self.footer_bar = QWidget()
        self.footer_bar.setObjectName("footerBar")
        self.footer_bar_layout = QHBoxLayout(self.footer_bar)
        self.footer_bar_layout.setContentsMargins(0, 0, 0, 0)

        self.info_label = QLabel()

        self.actions_widget = QWidget()
        self.actions_layout = QHBoxLayout(self.actions_widget)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)

        self.open_mods_folder_button = QPushButton(self.tr("Open Mods Folder"))
        self.open_mods_folder_button.setObjectName("modsViewButton")
        self.open_mods_folder_button.setIcon(QIcon(":/material/folder.svg"))
        self.open_mods_folder_button.clicked.connect(self.openModsFolderRequested.emit)

        self.sync_button = QPushButton(self.tr("Sync Mods"))
        self.sync_button.clicked.connect(self.modsSyncRequested.emit)
        self.sync_button.setObjectName("syncButton")
        self.sync_button.setObjectName("modsViewButton")
        self.sync_button.setIcon(QIcon(":/material/sync.svg"))

        self.unsync_button = QPushButton(self.tr("Unsync Mods"))
        self.unsync_button.clicked.connect(self.modsUnsyncRequested.emit)
        self.unsync_button.setObjectName("unsyncButton")
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

    def retranslateUI(self):
        self.setWindowTitle(self.tr("Mods Manager"))
        self.search_field.setPlaceholderText(self.tr("Search Mods"))
        self.refresh_button.setText(self.tr("Refresh Mods"))
        self.add_mod_button.setText(self.tr("Add Mod"))
        self.open_mods_folder_button.setText(self.tr("Open Mods Folder"))
        self.sync_button.setText(self.tr("Sync Mods"))
        self.unsync_button.setText(self.tr("Unsync Mods"))
        self.mod_list.setHeaderLabels([self.tr("Mod Name"), self.tr("Character"), self.tr("Type"), self.tr("Author")])
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.drop_modal.width()
        h = self.drop_modal.height()
        cw = self.width()
        ch = self.height()
        x = (cw - w) // 2
        y = (ch - h) // 2
        self.drop_modal.move(x, y)

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
    
    def show_context_menu(self, pos):
        selected_items = self.mod_list.selectedItems()
        current_item = self.mod_list.itemAt(pos)
                
        menu = QMenu(self)
        menu.addAction(self.tr("Refresh Mods"), self._refresh_mods)
        menu.addSeparator()
        
        if len(selected_items) > 1:              
            menu.addAction(self.tr("Enable Mods"), lambda: self._enable_mods(selected_items))
            menu.addAction(self.tr("Disable Mods"), lambda: self._disable_mods(selected_items))
            menu.addSeparator()
            menu.addAction(self.tr("Remove Mods"), lambda: self._confirm_mods_deletion(selected_items))
        else:
            action_text = self.tr("Enable Mod")
            
            if current_item.checkState(0) == Qt.CheckState.Checked:
                action_text = self.tr("Disable Mod")
                
            menu.addAction(action_text, lambda: self._enable_or_disable_mod(selected_items))
    
            menu.addAction(self.tr("Set Mod Author"), lambda: self._show_author_input_dialog(current_item))
            menu.addAction(self.tr("Highlight conflicts"), self._highlight_mod_conflicts)
            
            if self._has_conflict_highlights:
                menu.addAction(self.tr("Remove highlights"), self._remove_hightlight_conflicts)
                
            menu.addSeparator()
            menu.addAction(self.tr("Rename Mod"), lambda: self._show_rename_input_dialog(current_item))
            menu.addAction(self.tr("Delete Mod"), lambda: self._confirm_mod_deletion(current_item))
            menu.addSeparator()
            
            mod_path = current_item.data(0, Qt.ItemDataRole.UserRole)["path"]
            menu.addAction(self.tr("Open Mod Folder"), lambda: self.openModFolderRequested.emit(mod_path))

        menu.exec_(self.mod_list.mapToGlobal(pos))
        
    def _enable_or_disable_mod(self, items: list[QTreeWidgetItem]):
        for item in items:
            mod_state = item.checkState(0) == Qt.CheckState.Checked
            item.setCheckState(0, Qt.CheckState.Unchecked if mod_state else Qt.CheckState.Checked)

    def _enable_mods(self, items: list[QTreeWidgetItem]):
        for item in items:
            if item.checkState(0) == Qt.CheckState.Unchecked:
                item.setCheckState(0, Qt.CheckState.Checked)
    
    def _disable_mods(self, items: list[QTreeWidgetItem]):
        for item in items:
            if item.checkState(0) == Qt.CheckState.Checked:
                item.setCheckState(0, Qt.CheckState.Unchecked)

    def _show_author_input_dialog(self, item: QTreeWidgetItem):
        mod = item.data(0, Qt.ItemDataRole.UserRole)
        author, ok = QInputDialog.getText(self, self.tr("Set Mod Author"), self.tr("Enter the author's name:"), text=mod.get("author", ""))
        if ok and author:
            mod["author"] = author
            item.setData(0, Qt.ItemDataRole.UserRole, mod)
            item.setText(3, author)
            self.modAuthorChanged.emit(mod["name"], author)

        return None

    def _show_rename_input_dialog(self, item: QTreeWidgetItem):
        mod = item.data(0, Qt.ItemDataRole.UserRole)
        new_name, ok = QInputDialog.getText(self, self.tr("Rename Mod"), self.tr("Enter the new name for the mod:"), text=mod.get("name", ""))
        if ok and new_name:
            old_name = mod["name"]
            mod["name"] = new_name
            item.setData(0, Qt.ItemDataRole.UserRole, mod)
            item.setText(0, new_name)
            self.renameModRequested.emit(old_name, new_name)

        return None
    
    def _confirm_mod_deletion(self, item: QTreeWidgetItem):
        mod = item.data(0, Qt.ItemDataRole.UserRole)
        msg_template = self.tr("Are you sure you want to delete the mod \"{mod_name}\"?")
        msg = msg_template.format(mod_name=mod["name"])
        reply = QMessageBox.question(
            self,
            self.tr("Delete Mod"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.removeModRequested.emit(mod["name"])
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
                self.removeModRequested.emit(mod["name"])
            self._refresh_mods()
    
    def _filter_search(self, text: str):
        for index in range(self.mod_list.topLevelItemCount()):
            mod_item = self.mod_list.topLevelItem(index)
            if not mod_item:
                continue

            mod_data = mod_item.data(0, Qt.ItemDataRole.UserRole)

            if text.lower() in mod_data.get("name").lower():
                mod_item.setHidden(False)
            else:
                mod_item.setHidden(True)

    def _refresh_mods(self):
        self.modsRefreshRequested.emit()

        if self.search_field.text():
            self._filter_search(self.search_field.text())

    def _add_mod(self):
        filename, _ = QFileDialog.getOpenFileName(self, self.tr("Select Mod"), "", "*.modfile")
        if filename:
            self.addModRequested.emit(filename)

    def _mod_state_changed(self, item: QTreeWidgetItem):
        mod_data = item.data(0, Qt.ItemDataRole.UserRole)
        mod_state = item.checkState(0)
        mod_data["enabled"] = mod_state == Qt.CheckState.Checked
        item.setData(0, Qt.ItemDataRole.UserRole, mod_data)
        self.modStateChanged.emit(
            mod_data["name"], mod_state == Qt.CheckState.Checked
        )
    
    def _remove_hightlight_conflicts(self):
        for index in range(self.mod_list.topLevelItemCount()):
            item = self.mod_list.topLevelItem(index)
            if item.data(0, Qt.ItemDataRole.UserRole + 1):
                item.setData(0, Qt.ItemDataRole.UserRole + 1, False)
        self._has_conflict_highlights = False
    
    def _highlight_mod_conflicts(self):
        for index in range(self.mod_list.topLevelItemCount()):
            item = self.mod_list.topLevelItem(index)
            if item.data(0, Qt.ItemDataRole.UserRole + 1):
                item.setData(0, Qt.ItemDataRole.UserRole + 1, False)
                
            # item.setBackground(0, QBrush())
        if len(self.mod_list.selectedItems()) > 1:
            return
        
        selected_item = self.mod_list.currentItem()
        selected_item_data = selected_item.data(0, Qt.ItemDataRole.UserRole)
                
        for index in range(self.mod_list.topLevelItemCount()):
            item = self.mod_list.topLevelItem(index)
            item_data = item.data(0, Qt.ItemDataRole.UserRole)
            
            if item_data.get("character") is None:
                continue
        
            if not item_data["enabled"]:
                continue
            
            if selected_item_data["type"] == item_data["type"] and selected_item_data["character"]["id"] == item_data["character"]["id"]:
                item.setData(0, Qt.ItemDataRole.UserRole + 1, True)
                if not self._has_conflict_highlights:
                    self._has_conflict_highlights = True
                # for col in range(item.columnCount()):
                #     item.setBackground(col, QColor('#B4656F'))
        # print(selected_item.data(0, Qt.ItemDataRole.UserRole))

    def load_mods(self, mods: list):
        pos_y = self.mod_list.verticalScrollBar().value()
        self.mod_list.clear()

        for mod in mods:
            char_name = "-"

            if mod.get("character"):
                char_name = (
                    f"{mod['character']['character']} - {mod['character']['costume']}"
                )

            item = QTreeWidgetItem()
            item.setData(0, Qt.ItemDataRole.UserRole, mod)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, False) # has conflict

            item.setText(0, mod["name"])
            item.setText(1, char_name)
            item.setText(2, mod["type"].capitalize() if mod["type"] else "-")
            item.setText(3, mod["author"])
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEnabled
            )
            item.setCheckState(
                0, Qt.CheckState.Checked if mod.get("enabled", False) else Qt.CheckState.Unchecked
            )
            item.setTextAlignment(0, Qt.AlignmentFlag.AlignVCenter)
            item.setTextAlignment(1, Qt.AlignmentFlag.AlignVCenter)
            item.setTextAlignment(2, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
            
            self.mod_list.addTopLevelItem(item)

        self.mod_list.verticalScrollBar().setValue(pos_y)
        
        if not self._modlist_loaded:
            self._modlist_loaded = True
            self.mod_list.header().resizeSections(QHeaderView.ResizeMode.ResizeToContents)