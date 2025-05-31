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
    onRefreshMods = Signal()
    onModsLoaded = Signal()
    onAddMod = Signal(str)
    onModStateChanged = Signal(str, bool)
    onSyncModsClicked = Signal()
    onUnsyncModsClicked = Signal()

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
        self.mod_list.header().setObjectName("header")
        self.mod_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.mod_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.mod_list.setContentsMargins(0, 0, 0, 0)
        self.mod_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.mod_list.itemChanged.connect(self._mod_state_changed)

        self.footer_bar = QWidget()
        self.footer_bar.setObjectName("footerBar")
        self.footer_bar_layout = QHBoxLayout(self.footer_bar)
        self.footer_bar_layout.setContentsMargins(0, 0, 0, 0)

        self.info_label = QLabel(text="")

        self.actions_widget = QWidget()
        self.actions_layout = QHBoxLayout(self.actions_widget)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        
        self.open_mods_folder = QPushButton("Open Mods Folder")

        self.sync_button = QPushButton("Sync Mods")
        self.sync_button.clicked.connect(self.onSyncModsClicked)
        self.sync_button.setObjectName("syncButton")
        self.unsync_button = QPushButton("Unsync Mods")
        self.unsync_button.clicked.connect(self.onUnsyncModsClicked)
        self.unsync_button.setObjectName("unsyncButton")

        self.actions_layout.addWidget(self.open_mods_folder)
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
                self.onAddMod.emit(file_path)

    def _filter_search(self, text: str):

        for index in range(self.mod_list.topLevelItemCount()):
            mod_item = self.mod_list.topLevelItem(index)

            mod_data = mod_item.data(0, Qt.ItemDataRole.UserRole)

            if text.lower() in mod_data.get("name").lower():
                mod_item.setHidden(False)
            else:
                mod_item.setHidden(True)

    def _refresh_mods(self):
        self.onRefreshMods.emit()

        if self.search_field.text():
            self._filter_search(self.search_field.text())

        self.info_label.setText("")
        self.info_label.setText("Mods updated.")

    def _add_mod(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select Mod", "", "*.modfile")
        if filename:
            self.onAddMod.emit(filename)

    def _mod_state_changed(self, item: QTreeWidgetItem):
        mod_data = item.data(0, Qt.ItemDataRole.UserRole)
        mod_state = item.checkState(0)
        self.onModStateChanged.emit(
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
            item.setText(2, mod["type"].capitalize())
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

        for column in range(self.mod_list.columnCount()):
            size = self.mod_list.header().sectionSizeHint(column)
            if size < self.mod_list.sizeHintForColumn(column):
                size = self.mod_list.sizeHintForColumn(column) + 16
            else:
                size += 12
            self.mod_list.header().resizeSection(column, size)

        self.info_label.setText("Mods loaded.")

        self.mod_list.verticalScrollBar().setValue(pos_y)
