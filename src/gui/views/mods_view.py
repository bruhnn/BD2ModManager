

from PySide6.QtGui import QDragEnterEvent
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
    QMessageBox
)
from PySide6.QtCore import Qt, Signal


class DragFilesModal(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFixedSize(300, 120)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.setStyleSheet("""
            background: rgba(30, 30, 30, 220);
            border-radius: 12px;
            border: 2px solid #888;
        """)

        self.label = QLabel(text="Drop Files")

        self.layout.addWidget(self.label)

        self.hide()
        self.raise_()


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

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.drop_modal = DragFilesModal(self)

        self.top_bar = QWidget()
        self.top_bar.setObjectName("topBar")
        self.top_bar_layout = QHBoxLayout(self.top_bar)
        self.top_bar_layout.setContentsMargins(0, 0, 0, 0)

        self.search_field = QLineEdit(placeholderText="Search Mods")
        self.search_field.textChanged.connect(self._filter_search)

        self.refresh_button = QPushButton("Refresh Mods")
        self.refresh_button.clicked.connect(self._refresh_mods)
        self.add_mod_button = QPushButton("Add Mod")
        self.add_mod_button.setObjectName("addModButton")
        self.add_mod_button.clicked.connect(self._add_mod)

        self.top_bar_layout.addWidget(self.search_field)
        self.top_bar_layout.addWidget(self.refresh_button)
        self.top_bar_layout.addWidget(self.add_mod_button)

        self.mod_list = QTreeWidget()
        self.mod_list.setObjectName("modlist")
        self.mod_list.setHeaderLabels(["Mod Name", "Character", "Type", "Author"])
        self.mod_list.setSortingEnabled(True)
        self.mod_list.setRootIsDecorated(False)
        # self.mod_list.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.mod_list.header().setObjectName("header")
        self.mod_list.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.mod_list.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.mod_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.mod_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.mod_list.setContentsMargins(0, 0, 0, 0)
        self.mod_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.mod_list.itemChanged.connect(self._mod_state_changed)
        self.mod_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.mod_list.customContextMenuRequested.connect(self.show_context_menu)

        self.footer_bar = QWidget()
        self.footer_bar.setObjectName("footerBar")
        self.footer_bar_layout = QHBoxLayout(self.footer_bar)
        self.footer_bar_layout.setContentsMargins(0, 0, 0, 0)

        self.info_label = QLabel()
        self.info_label.setObjectName("infoLabel")

        self.actions_widget = QWidget()
        self.actions_layout = QHBoxLayout(self.actions_widget)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        
        self.open_mods_folder_button = QPushButton("Open Mods Folder")
        self.open_mods_folder_button.clicked.connect(self.openModsFolderRequested.emit)

        self.sync_button = QPushButton("Sync Mods")
        self.sync_button.clicked.connect(self.modsSyncRequested.emit)
        self.sync_button.setObjectName("syncButton")
        self.unsync_button = QPushButton("Unsync Mods")
        self.unsync_button.clicked.connect(self.modsUnsyncRequested.emit)
        self.unsync_button.setObjectName("unsyncButton")

        self.actions_layout.addWidget(self.open_mods_folder_button)
        self.actions_layout.addWidget(self.unsync_button)
        self.actions_layout.addWidget(self.sync_button)

        self.footer_bar_layout.addWidget(self.info_label)
        self.footer_bar_layout.addWidget(self.actions_widget)

        self.layout.addWidget(self.top_bar)
        self.layout.addWidget(self.mod_list)
        self.layout.addWidget(self.footer_bar)

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
        current_item = self.mod_list.itemAt(pos)
        if not current_item:
            return
        
        mod = current_item.data(0, Qt.ItemDataRole.UserRole)
        
        menu = QMenu(self)
        menu.addAction("Refresh Mods", self._refresh_mods)
        menu.addSeparator()
        action_text = "Enable Mod"
        if current_item.checkState(0) == Qt.CheckState.Checked:
            action_text = "Disable Mod"
        menu.addAction(action_text, lambda: self._enable_or_disable_mod(current_item))
        menu.addAction("Set Mod Author", lambda: self._show_author_input_dialog(current_item))
        menu.addSeparator()
        menu.addAction("Rename Mod", lambda: self._show_rename_input_dialog(current_item))
        menu.addAction("Delete Mod", lambda: self._show_delete_confirmation_dialog(mod["name"]))
        menu.addSeparator()
        menu.addAction("Open Mod Folder", lambda: self.openModFolderRequested.emit(mod["path"]))

        menu.exec_(self.mod_list.mapToGlobal(pos))
        
    def _enable_or_disable_mod(self, item: QTreeWidgetItem):
        mod_state = item.checkState(0) == Qt.CheckState.Checked
        item.setCheckState(0, Qt.Unchecked if mod_state else Qt.Checked)

    def _show_author_input_dialog(self, item: QTreeWidgetItem):
        mod = item.data(0, Qt.ItemDataRole.UserRole)
        author, ok = QInputDialog.getText(self, "Set Mod Author", "Enter the author's name:", text=mod.get("author", ""))
        if ok and author:
            mod["author"] = author
            item.setData(0, Qt.ItemDataRole.UserRole, mod)
            item.setText(3, author)
            self.modAuthorChanged.emit(mod["name"], author)

        return None

    def _show_rename_input_dialog(self, item: QTreeWidgetItem):
        mod = item.data(0, Qt.ItemDataRole.UserRole)
        new_name, ok = QInputDialog.getText(self, "Rename Mod", "Enter the new name for the mod:", text=mod.get("name", ""))
        if ok and new_name:
            old_name = mod["name"]
            mod["name"] = new_name
            item.setData(0, Qt.ItemDataRole.UserRole, mod)
            item.setText(0, new_name)
            self.renameModRequested.emit(old_name, new_name)

        return None
    
    def _show_delete_confirmation_dialog(self, mod_name: str):
        reply = QMessageBox.question(
            self,
            "Delete Mod",
            f"Are you sure you want to delete the mod '{mod_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.removeModRequested.emit(mod_name)
            self._refresh_mods()
    
    def _filter_search(self, text: str):
        # TODO: @type:cutscene, @author:yuki, @character:rou

        for index in range(self.mod_list.topLevelItemCount()):
            mod_item = self.mod_list.topLevelItem(index)

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
        filename, _ = QFileDialog.getOpenFileName(self, "Select Mod", "", "*.modfile")
        if filename:
            self.addModRequested.emit(filename)

    def _mod_state_changed(self, item: QTreeWidgetItem):
        mod_data = item.data(0, Qt.ItemDataRole.UserRole)
        mod_state = item.checkState(0)
        self.modStateChanged.emit(
            mod_data["name"], mod_state == Qt.CheckState.Checked
        )

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

            item.setText(0, mod["name"])
            item.setText(1, char_name)
            item.setText(2, mod["type"].capitalize() if mod["type"] else "-")
            item.setText(3, mod["author"])
            item.setFlags(
                item.flags()
                | Qt.ItemIsUserCheckable
                | Qt.ItemIsSelectable
                | Qt.ItemIsEnabled
            )
            item.setCheckState(
                0, Qt.Checked if mod.get("enabled", False) else Qt.Unchecked
            )
            item.setTextAlignment(0, Qt.AlignVCenter)
            item.setTextAlignment(1, Qt.AlignVCenter)
            item.setTextAlignment(2, Qt.AlignVCenter | Qt.AlignHCenter)
            
            self.mod_list.addTopLevelItem(item)
                
        # Bad performance
        # for column in range(self.mod_list.columnCount()):
        #     size = self.mod_list.header().sectionSizeHint(column)
        #     if size < self.mod_list.sizeHintForColumn(column):
        #         size = self.mod_list.sizeHintForColumn(column) + 16
        #     else:
        #         size += 12
        #     self.mod_list.header().resizeSection(column, size)
        
        # Bad performance too
        # for column in range(self.mod_list.columnCount()):
        #     self.mod_list.resizeColumnToContents(column)

        self.mod_list.verticalScrollBar().setValue(pos_y)

    def set_info_text(self, text: str):
        self.info_label.setText(text)