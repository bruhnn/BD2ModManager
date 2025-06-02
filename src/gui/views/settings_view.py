from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGroupBox, QHBoxLayout, QLineEdit, QPushButton, QSizePolicy, QSpacerItem, QComboBox, QCheckBox, QFileDialog
from PySide6.QtCore import Qt, Signal

from typing import Union, Any
from pathlib import Path

from src.BD2ModManager import BD2ModManager
from src.BD2ModManager.errors import GameNotFoundError
from src.gui.config import BD2MMConfigManager

class SettingsView(QWidget):
    def __init__(self, config_manager: BD2ModManager, mod_manager: BD2MMConfigManager):
        super().__init__()
        self.setObjectName("settingsView")

        self.config_manager = config_manager
        self.mod_manager = mod_manager

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel(text="Settings")
        title.setSizePolicy(QSizePolicy.Policy.Expanding,
                            QSizePolicy.Policy.Fixed)
        title.setObjectName("settingsTitle")

        paths_group = self.create_group("Paths")

        game_directory_widget, game_directory_button = self.create_directory_input(
            "Game Directory:", self.config_manager.game_directory or "Not Set")
        mods_directory_widget, mods_directory_button = self.create_directory_input(
            "Mods Directory:", self.mod_manager.staging_mods_directory or "Not Set")
        game_directory_button.clicked.connect(self.open_game_directory_dialog)
        mods_directory_button.clicked.connect(self.open_mods_directory_dialog)

        search_mods_recursively_checkbox_widget = self.create_checkbox(label="Search mods recursively", config_key="search_mods_recursively")

        paths_group.layout().addWidget(game_directory_widget)
        paths_group.layout().addWidget(mods_directory_widget)
        paths_group.layout().addWidget(search_mods_recursively_checkbox_widget)

        general_group = self.create_group("General")

        language_combobox_widget = self.create_combobox("Language:", [
            {"label": "English", "value": "english"},
            {"label": "Português (BR)", "value": "portuguese"},
            {"label": "한국어", "value": "korean"},
            {"label": "日本語", "value": "japanese"},
            {"label": "简体中文", "value": "chinese_simplified"},
            {"label": "繁體中文", "value": "chinese_traditional"}
        ], "language", default="english")

        theme_combobox_widget = self.create_combobox("Theme:", [
            {"label": "System Default", "value": "default"},
            {"label": "Light", "value": "light"},
            {"label": "Dark", "value": "dark"},
        ], "theme", default="default")

        general_group.layout().addWidget(theme_combobox_widget)
        general_group.layout().addWidget(language_combobox_widget)

        synchronization_group = self.create_group("Synchronization")

        sync_method_widget = self.create_combobox("Sync Method:", [{
            "label": "Copy (Default)",
            "value": "copy"
        }, {
            "label": "Symlink (Administrator)",
            "value": "symlink"
        }, {
            "label": "Hardlink (Administrator)",
            "value": "hardlink"
        }], "sync_method", default="copy")

        synchronization_group.layout().addWidget(sync_method_widget)

        installation_group = self.create_group("Installation")

        ask_for_author_widget = self.create_checkbox("Ask for author during installation", "ask_for_author", default=True)

        installation_group.layout().addWidget(ask_for_author_widget)

        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(title)
        layout.addWidget(paths_group)
        layout.addWidget(general_group)
        layout.addWidget(installation_group)
        layout.addWidget(synchronization_group)

    def create_group(self, title: str):
        group = QGroupBox(title)
        group.setObjectName("settingsGroup")
        group.setSizePolicy(QSizePolicy.Policy.Expanding,
                            QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 8, 12, 8)  # margens maiores

        return group

    def create_directory_input(self, label: str, value: Union[str, Path]):
        widget = QWidget()
        widget.setSizePolicy(QSizePolicy.Policy.Expanding,
                             QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(text=label)

        value = QLineEdit(text=str(value))
        value.setReadOnly(True)

        select_btn = QPushButton(text="Select Folder")

        layout.addWidget(label, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addSpacerItem(QSpacerItem(
            32, 0, QSizePolicy.Fixed, QSizePolicy.Minimum))
        layout.addWidget(value, 1)
        layout.addWidget(select_btn, 0, Qt.AlignmentFlag.AlignRight)

        return widget, select_btn

    def create_combobox(self, label: str, options: list, config_key: str, default: Any = None):
        widget = QWidget()
        widget.setSizePolicy(QSizePolicy.Policy.Expanding,
                             QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(text=label)

        combo = QComboBox()
        for option in options:
            combo.addItem(option["label"], option["value"])

        layout.addWidget(label, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addSpacerItem(QSpacerItem(
            32, 0, QSizePolicy.Fixed, QSizePolicy.Minimum))
        layout.addWidget(combo, 1)
        
        data = self.config_manager.get(config_key, default=default)
        index = combo.findData(data, Qt.ItemDataRole.UserRole)
        if index != -1:
            combo.setCurrentIndex(index)
            combo.currentIndexChanged.connect(lambda index: self.config_manager.set(config_key, combo.itemData(index)))

        return widget

    def create_checkbox(self, label: str, config_key: str, default: bool = False):
        widget = QWidget()
        widget.setSizePolicy(QSizePolicy.Policy.Expanding,
                             QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        checkbox = QCheckBox(text=label)
        
        checkbox.setChecked(self.config_manager.get(config_key, boolean=True, default=default))
        checkbox.stateChanged.connect(lambda state: self.config_manager.set(config_key, checkbox.checkState() == Qt.CheckState.Checked))

        layout.addWidget(checkbox)

        return widget

    def open_game_directory_dialog(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Game Directory", "")
        if directory:
            try:
                self.mod_manager.set_game_directory(directory)
            except GameNotFoundError:
                raise GameNotFoundError("The selected directory does not contain the game files. Please select a valid game directory.")
                
            self.config_manager.game_directory = directory
            self.sender().parent().findChild(QLineEdit).setText(directory)

    def open_mods_directory_dialog(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Mods Directory", "")
        if directory:
            self.mod_manager.set_staging_mods_directory(directory)
            self.config_manager.set("staging_mods_path", directory)
            self.sender().parent().findChild(QLineEdit).setText(directory)