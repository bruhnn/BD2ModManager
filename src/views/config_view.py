from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QLineEdit, QPushButton, QSizePolicy, QSpacerItem, QComboBox, QCheckBox, QFileDialog, QGridLayout, QScrollArea, QFrame
from PySide6.QtCore import Qt, Signal

from os import startfile


class DirectoryInput(QWidget):
    onDirectoryChanged = Signal(str)

    def __init__(self, label: str):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(text=label)
        self.label.setObjectName("directoryInputLabel")

        self.input_field = QLineEdit(text=self.tr("Not Set."))
        self.input_field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.input_field.setReadOnly(True)
        self.input_field.setObjectName("directoryInputValue")

        self.browse_button = QPushButton(self.tr("Browse"))
        self.browse_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.browse_button.setObjectName("directoryInputButton")
        self.browse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_button.clicked.connect(self.open_directory_dialog)

        self.open_button = QPushButton(self.tr("Open Folder"))
        self.open_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.open_button.setObjectName("directoryInputButton")
        self.open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_button.clicked.connect(lambda: startfile(self.input_field.text()))

        layout.addWidget(self.label, 0, 0, 1, 1)
        layout.addItem(QSpacerItem(64, 0, QSizePolicy.Policy.Maximum), 0, 1)
        layout.addWidget(self.input_field, 0, 2, 1, 1)
        layout.addWidget(self.browse_button, 0, 3, 1, 1)
        layout.addWidget(self.open_button, 0, 4, 1, 1)

    def open_directory_dialog(self):
        directory = QFileDialog.getExistingDirectory(
            self, self.tr("Select Directory"), "")

        if directory:
            self.onDirectoryChanged.emit(directory)

    def set_text(self, text: str):
        self.label.setText(text)

    def set_directory_path(self, path: str):
        self.input_field.setText(path or self.tr("Not Set."))


class ConfigComboBox(QWidget):
    valueChanged = Signal(str)
    
    class ComboBox(QComboBox):
        def wheelEvent(self, event):
            if not self.view().isVisible():
                event.ignore()
            else:
                super().wheelEvent(event)

    def __init__(self, label: str, options: list):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(text=label)
        self.label.setObjectName("settingsComboBoxLabel")

        self.combo = self.ComboBox()
        # self.combo.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        self.combo.setObjectName("settingsComboBox")

        for index, option in enumerate(options):
            self.combo.addItem(option["label"], option["value"])
            if option.get("disabled", False):
                item = self.combo.model().item(index)
                if item:
                    item.setEnabled(False)

        self.combo.currentIndexChanged.connect(lambda index: self.valueChanged.emit(self.combo.itemData(index)))

        layout.addWidget(self.label, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addSpacerItem(QSpacerItem(64, 0, QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum))
        layout.addWidget(self.combo, 1)

    def set_text(self, text: str):
        self.label.setText(text)


class SectionHeader(QWidget):
    def __init__(self, title: str):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Title label
        self.title_label = QLabel(title)
        self.title_label.setObjectName("settingsSectionTitle")
        self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        # Separator line
        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setObjectName("settingsSectionSeparator")
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        layout.addWidget(self.title_label)
        layout.addWidget(separator)
    
    def set_title(self, title: str):
        self.title_label.setText(title)


class ConfigView(QScrollArea):
    onLanguageChanged = Signal(str)
    onThemeChanged = Signal(str)

    onGameDirectoryChanged = Signal(str)
    onModsDirectoryChanged = Signal(str)

    onSyncMethodChanged = Signal(str)
    onSearchModsRecursivelyChanged = Signal(bool)

    onFindAuthorsClicked = Signal()

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)

        widget = QWidget()
        widget.setObjectName("settingsView")
        
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(*[8]*4)

        self.title = QLabel(text=self.tr("Settings"))
        self.title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.title.setObjectName("settingsTitle")

        # PATHS SECTION
        self.paths_header = SectionHeader(self.tr("Paths"))
        
        self.game_directory_input = DirectoryInput(label=self.tr("Game Directory"))
        self.game_directory_input.onDirectoryChanged.connect(self.onGameDirectoryChanged.emit)
        self.mods_directory_input = DirectoryInput(label=self.tr("Mods Directory"))
        self.mods_directory_input.onDirectoryChanged.connect(self.onModsDirectoryChanged.emit)

        self.recursive_search_checkbox = QCheckBox(self.tr("Search Mods Recursively"))
        self.recursive_search_checkbox.setObjectName("settingsCheckbox")
        self.recursive_search_checkbox.stateChanged.connect(self.onSearchModsRecursivelyChanged.emit)

        # GENERAL SECTION
        self.general_header = SectionHeader(self.tr("General"))

        self.language_combobox = ConfigComboBox(
            label=self.tr("Language:"),
            options=[
                {"label": "English", "value": "english"},
                {"label": "Português (BR)", "value": "portuguese"}
            ]
        )
        self.language_combobox.valueChanged.connect(
            self.onLanguageChanged.emit)

        self.theme_combobox = ConfigComboBox(
            label=self.tr("Theme:"),
            options=[
                {"label": self.tr("Dark"), "value": "dark"},
                {"label": self.tr("Light"), "value": "light"}
            ]
        )
        self.theme_combobox.valueChanged.connect(self.onThemeChanged.emit)

        # SYNCHRONIZATION SECTION
        self.synchronization_header = SectionHeader(self.tr("Synchronization"))

        self.sync_method_combobox = ConfigComboBox(
            label=self.tr("Sync Method:"),
            options=[{
                "label": self.tr("Copy (Default)"),
                "value": "copy"
            }, {
                "label": self.tr("Symlink (Administrator)"),
                "value": "symlink"
            }, {
                "label": self.tr("Hardlink (Administrator)"),
                "value": "hardlink",
                "disabled": True
            }]
        )
        self.sync_method_combobox.valueChanged.connect(
            self.onSyncMethodChanged)

        # MODLIST SECTION
        self.modlist_header = SectionHeader(self.tr("Modlist"))
        
        self.include_folder_paths_checkbox = QCheckBox(self.tr("Include Folder Paths"))

        self.ask_for_author_checkbox = QCheckBox(self.tr("Ask for author during installation"))
        self.ask_for_author_checkbox.setDisabled(True)

        # EXPERIMENTAL SECTION
        self.experimental_header = SectionHeader("Experimental")

        self.find_authors_button = QPushButton("Find Authors")
        self.find_authors_button.setObjectName("modsViewButton")
        self.find_authors_button.clicked.connect(self.onFindAuthorsClicked.emit)

        # Add all widgets to layout
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.title)
        
        # Paths section
        layout.addWidget(self.paths_header)
        layout.addWidget(self.game_directory_input)
        layout.addWidget(self.mods_directory_input)
        layout.addWidget(self.recursive_search_checkbox)
        
        # General section
        layout.addWidget(self.general_header)
        layout.addWidget(self.theme_combobox)
        layout.addWidget(self.language_combobox)
        
        # Synchronization section
        layout.addWidget(self.synchronization_header)
        layout.addWidget(self.sync_method_combobox)
        
        # Modlist section
        layout.addWidget(self.modlist_header)
        layout.addWidget(self.include_folder_paths_checkbox)
        layout.addWidget(self.ask_for_author_checkbox)
        
        # Experimental section
        layout.addWidget(self.experimental_header)
        experimental_container = QWidget()
        experimental_layout = QHBoxLayout(experimental_container)
        experimental_layout.setContentsMargins(0, 0, 0, 0)
        experimental_layout.addWidget(self.find_authors_button)
        experimental_layout.addStretch()
        layout.addWidget(experimental_container)

        self.setWidget(widget)

    def retranslateUI(self):
        self.title.setText(self.tr("Settings"))
        self.paths_header.set_title(self.tr("Paths"))
        self.general_header.set_title(self.tr("General"))
        self.modlist_header.set_title(self.tr("Installation"))
        self.synchronization_header.set_title(self.tr("Synchronization"))
        self.recursive_search_checkbox.setText(self.tr("Search mods recursively"))
        self.language_combobox.set_text(self.tr("Language"))
        self.theme_combobox.set_text(self.tr("Theme"))
        self.sync_method_combobox.set_text(self.tr("Sync Method"))
        self.game_directory_input.set_text(self.tr("Game Directory"))
        self.mods_directory_input.set_text(self.tr("Mods Directory"))
        self.ask_for_author_checkbox.setText(self.tr("Ask for author during installation"))

    def update_config(self, config: dict):
        if "game_directory" in config:
            self.game_directory_input.set_directory_path(config["game_directory"])

        if "mods_directory" in config:
            self.mods_directory_input.set_directory_path(config["mods_directory"])

        if "search_mods_recursively" in config:
            self.recursive_search_checkbox.blockSignals(True)
            self.recursive_search_checkbox.setChecked(config["search_mods_recursively"])
            self.recursive_search_checkbox.blockSignals(False)

        if "language" in config:
            idx = self.language_combobox.combo.findData(config["language"])
            if idx != -1:
                self.language_combobox.combo.blockSignals(True)
                self.language_combobox.combo.setCurrentIndex(idx)
                self.language_combobox.combo.blockSignals(False)
                self.onLanguageChanged.emit(config["language"])

        if "theme" in config:
            idx = self.theme_combobox.combo.findData(config["theme"])
            if idx != -1:
                self.theme_combobox.combo.blockSignals(True)
                self.theme_combobox.combo.setCurrentIndex(idx)
                self.theme_combobox.combo.blockSignals(False)
                self.onThemeChanged.emit(config["theme"])

        if "sync_method" in config:
            idx = self.sync_method_combobox.combo.findData(config["sync_method"])
            if idx != -1:
                self.sync_method_combobox.combo.blockSignals(True)
                self.sync_method_combobox.combo.setCurrentIndex(idx)
                self.sync_method_combobox.combo.blockSignals(False)
                self.onSyncMethodChanged.emit(config["sync_method"])

        if "ask_for_author" in config:
            self.ask_for_author_checkbox.blockSignals(True)
            self.ask_for_author_checkbox.setChecked(bool(config["ask_for_author"]))
            self.ask_for_author_checkbox.blockSignals(False)
            # Emit your own signal here if needed
