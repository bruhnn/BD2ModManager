from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGroupBox, QHBoxLayout, QLineEdit, QPushButton, QSizePolicy, QSpacerItem, QComboBox, QCheckBox, QFileDialog, QGridLayout, QMessageBox
from PySide6.QtCore import Qt, Signal, QObject

from typing import Union, Any
from pathlib import Path

from src.BD2ModManager import BD2ModManager
from src.BD2ModManager.errors import GameNotFoundError
from src.gui.config import BD2MMConfigManager

class SettingsView(QWidget):
    onThemeChanged = Signal(str)
    onLanguageChanged = Signal(str)
    
    def __init__(self, config_manager: BD2ModManager, mod_manager: BD2MMConfigManager):
        super().__init__()
        self.setObjectName("settingsView")

        self.config_manager = config_manager
        self.mod_manager = mod_manager

        layout = QVBoxLayout(self)

        self.title = QLabel(text=self.tr("Settings"))
        self.title.setSizePolicy(QSizePolicy.Policy.Expanding,
                                  QSizePolicy.Policy.Fixed)
        self.title.setObjectName("settingsTitle")

        self.paths_group = self.create_group(self.tr("Paths"))

        game_directory_widget, self.game_dir_label, game_directory_button = self.create_directory_input(
            self.tr("Game Directory:"), self.config_manager.game_directory or self.tr("Not Set"))
        mods_directory_widget, self.mods_dir_label, mods_directory_button = self.create_directory_input(
            self.tr("Mods Directory:"), self.mod_manager.staging_mods_directory or self.tr("Not Set"))
        game_directory_button.clicked.connect(self.open_game_directory_dialog)
        mods_directory_button.clicked.connect(self.open_mods_directory_dialog)

        search_mods_recursively_checkbox_widget, self.search_mods_recursively_checkbox = self.create_checkbox(label=self.tr("Search mods recursively"), config_key="search_mods_recursively")
        self.paths_group.layout().addWidget(game_directory_widget)
        self.paths_group.layout().addWidget(mods_directory_widget)
        self.paths_group.layout().addWidget(search_mods_recursively_checkbox_widget)

        self.general_group = self.create_group(self.tr("General"))

        language_combobox_widget, self.language_combobox_label, self.language_combobox_combobox = self.create_combobox(self.tr("Language:"), [
            {"label": "English", "value": "english"},
            {"label": "Português (BR)", "value": "portuguese"}
        ], "language", default="english", on_change=self.onLanguageChanged.emit)

        theme_combobox_widget, self.theme_combobox_label, self.theme_combobox_combobox = self.create_combobox(self.tr("Theme:"), [
            {"label": self.tr("Dark"), "value": "dark"},
            # {"label": self.tr("Light"), "value": "light"},
        ], "theme", default="dark", on_change=self.onThemeChanged.emit)

        self.general_group.layout().addWidget(theme_combobox_widget)
        self.general_group.layout().addWidget(language_combobox_widget)

        self.synchronization_group = self.create_group(self.tr("Synchronization"))

        sync_method_widget, self.sync_method_label, self.sync_method_combobox = self.create_combobox(self.tr("Sync Method:"), [{
            "label": self.tr("Copy (Default)"),
            "value": "copy"
        }, {
            "label": self.tr("Symlink (Administrator)"),
            "value": "symlink"
        }, {
            "label": self.tr("Hardlink (Administrator)"),
            "value": "hardlink"
        }], "sync_method", default="copy")
        self.sync_method_combobox.setDisabled(True)
        
        self.synchronization_group.layout().addWidget(sync_method_widget)

        self.installation_group = self.create_group(self.tr("Installation"))

        ask_for_author_widget, self.ask_for_author_checkbox = self.create_checkbox(self.tr("Ask for author during installation"), "ask_for_author", default=True)
        self.ask_for_author_checkbox.setDisabled(True)

        self.installation_group.layout().addWidget(ask_for_author_widget)

        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.title)
        layout.addWidget(self.paths_group)
        layout.addWidget(self.general_group)
        layout.addWidget(self.installation_group)
        layout.addWidget(self.synchronization_group)

    def retranslateUI(self):
        self.title.setText(self.tr("Settings"))
        self.paths_group.setTitle(self.tr("Paths"))
        self.general_group.setTitle(self.tr("General"))
        self.installation_group.setTitle(self.tr("Installation"))
        self.synchronization_group.setTitle(self.tr("Synchronization"))
        self.search_mods_recursively_checkbox.setText(self.tr("Search mods recursively"))
        self.language_combobox_label.setText(self.tr("Language:"))
        self.theme_combobox_label.setText(self.tr("Theme:"))
        self.sync_method_label.setText(self.tr("Sync Method:"))
        self.game_dir_label.setText(self.tr("Game Directory:"))
        self.mods_dir_label.setText(self.tr("Mods Directory:"))
        self.ask_for_author_checkbox.setText(self.tr("Ask for author during installation"))
    
        

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

        layout = QGridLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(text=label)
        label.setObjectName("directoryLabel")

        input = QLineEdit(text=str(value))
        input.setReadOnly(True)
        input.setObjectName("directoryInput")

        browse_button = QPushButton(text=self.tr("Browse Folder"))
        browse_button.setObjectName("browseButton")
        browse_button.setCursor(Qt.CursorShape.PointingHandCursor)


        layout.addWidget(label, 0, 0, 1, 1, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(input, 0, 1, 1, 1)
        layout.addWidget(browse_button, 0, 2, 1, 1, Qt.AlignmentFlag.AlignRight)

        return widget, label, browse_button

    def create_combobox(self, label: str, options: list, config_key: str, default: Any = None, on_change=None):
        widget = QWidget()
        widget.setSizePolicy(QSizePolicy.Policy.Expanding,
                             QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(text=label)
        label.setObjectName("settingsLabel")

        combo = QComboBox()
        combo.setObjectName("settingsComboBox")
        
        for option in options:
            combo.addItem(option["label"], option["value"])

        if on_change:
            combo.currentIndexChanged.connect(lambda index: on_change(combo.itemData(index)))

        layout.addWidget(label, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addSpacerItem(QSpacerItem(
            32, 0, QSizePolicy.Fixed, QSizePolicy.Minimum))
        layout.addWidget(combo, 1)
        
        data = self.config_manager.get(config_key, default=default)
        index = combo.findData(data, Qt.ItemDataRole.UserRole)
        if index != -1:
            combo.setCurrentIndex(index)
            combo.currentIndexChanged.connect(lambda index: self.config_manager.set(config_key, combo.itemData(index)))

        return widget, label, combo

    def create_checkbox(self, label: QObject, config_key: str, default: bool = False):
        widget = QWidget()
        widget.setSizePolicy(QSizePolicy.Policy.Expanding,
                             QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        checkbox = QCheckBox(text=label)
        checkbox.setObjectName("settingsCheckbox")
        
        checkbox.setChecked(self.config_manager.get(config_key, boolean=True, default=default))
        checkbox.stateChanged.connect(lambda state: self.config_manager.set(config_key, checkbox.checkState() == Qt.CheckState.Checked))

        layout.addWidget(checkbox)

        return widget, checkbox

    def open_game_directory_dialog(self):
        directory = QFileDialog.getExistingDirectory(self, self.tr("Select Game Directory"), "")
        
        if directory:
            try:
                self.mod_manager.set_game_directory(directory)
            except GameNotFoundError:
                msg_box = QMessageBox()
                msg_box.setIcon(QMessageBox.Critical)
                msg_box.setWindowTitle(self.tr("Error"))
                msg_box.setText(self.tr("The selected directory does not contain the game files. Please select a valid game directory."))
                msg_box.exec_()
                return

            self.config_manager.set("game_path", directory)
            self.sender().parent().findChild(QLineEdit).setText(directory)

    def open_mods_directory_dialog(self):
        directory = QFileDialog.getExistingDirectory(self, self.tr("Select Mods Directory"), "")
        if directory:
            self.mod_manager.set_staging_mods_directory(directory)
            self.config_manager.set("staging_mods_path", directory)
            self.sender().parent().findChild(QLineEdit).setText(directory)