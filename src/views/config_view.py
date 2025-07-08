import os
from typing import Dict, List, Any
import logging

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QComboBox,
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QScrollArea,
    QFrame,
    QMessageBox
)
from PySide6.QtCore import Qt, Signal, Slot

from src.themes import ThemeManager


logger = logging.getLogger(__name__)


class DirectoryInput(QWidget):
    directoryChanged = Signal(str)

    def __init__(self, label: str, placeholder: str = "Not Set") -> None:
        super().__init__()
        self.placeholder = placeholder
        self._setup_ui(label)
        self._setup_connections()

    def _setup_ui(self, label: str) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        self._text_label = label

        self.label = QLabel(text=label)
        self.label.setObjectName("directoryInputLabel")

        self.input_field = QLineEdit(text=self.tr(self.placeholder))
        self.input_field.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.input_field.setReadOnly(True)
        self.input_field.setObjectName("directoryInputValue")
        self.input_field.setToolTip(self.tr("Selected directory path"))

        self.browse_button = QPushButton(self.tr("Browse"))
        self.browse_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )
        self.browse_button.setObjectName("directoryInputButton")
        self.browse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_button.setToolTip(self.tr("Browse for directory"))

        self.open_button = QPushButton(self.tr("Open"))
        self.open_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )
        self.open_button.setObjectName("directoryInputButton")
        self.open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_button.setEnabled(False)
        self.open_button.setToolTip(self.tr("Open directory in file explorer"))

        # Layout
        layout.addWidget(self.label, 0, 0, 1, 1)
        layout.addItem(QSpacerItem(16, 0, QSizePolicy.Policy.Fixed), 0, 1)
        layout.addWidget(self.input_field, 0, 2, 1, 1)
        layout.addWidget(self.browse_button, 0, 3, 1, 1)
        layout.addWidget(self.open_button, 0, 4, 1, 1)

        # Set column stretch to make input field expand
        layout.setColumnStretch(2, 1)

    def _setup_connections(self) -> None:
        self.browse_button.clicked.connect(self._open_directory_dialog)
        self.open_button.clicked.connect(self._open_directory)

    def _open_directory_dialog(self) -> None:
        current_path = self.input_field.text()
        if current_path == self.tr(self.placeholder):
            current_path = ""

        directory = QFileDialog.getExistingDirectory(
            self,
            self.tr("Select Directory"),
            current_path,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )

        if directory:
            self.directoryChanged.emit(directory)

    def _open_directory(self) -> None:
        path = self.input_field.text()
        if path and path != self.tr(self.placeholder) and os.path.exists(path):
            try:
                if os.name == 'nt':  # Windows
                    os.startfile(path)
                elif os.name == 'posix':  # macOS and Linux
                    os.system(f'open "{path}"' if os.uname(
                    ).sysname == 'Darwin' else f'xdg-open "{path}"')
            except Exception as e:
                logger.error(f"Failed to open directory: {e}")
                QMessageBox.warning(
                    self,
                    self.tr("Error"),
                    self.tr("Failed to open directory: {}").format(str(e))
                )

    def get_directory_path(self) -> str:
        """Get the current directory path."""
        path = self.input_field.text()
        return path if path != self.tr(self.placeholder) else ""

    def set_directory_path(self, path: str) -> None:
        """Set the directory path."""
        display_path = path or self.tr(self.placeholder)
        self.input_field.setText(display_path)
        self.input_field.setToolTip(display_path if path else "")
        self.open_button.setEnabled(bool(path and os.path.exists(path)))

    def set_label_text(self, text: str) -> None:
        """Set the label text."""
        self.label.setText(text)

    def is_valid_path(self) -> bool:
        """Check if the current path is valid."""
        path = self.get_directory_path()
        return bool(path and os.path.exists(path))

    def retranslateUI(self) -> None:
        self.label.setText(self.tr(self._text_label))
        self.input_field.setText(self.tr(self.placeholder if not self.get_directory_path() else self.get_directory_path()))
        self.input_field.setToolTip(self.tr("Selected directory path") if self.get_directory_path() else "")
        self.browse_button.setText(self.tr("Browse"))
        self.browse_button.setToolTip(self.tr("Browse for directory"))
        self.open_button.setText(self.tr("Open"))
        self.open_button.setToolTip(self.tr("Open directory in file explorer"))


class ConfigComboBox(QWidget):
    valueChanged = Signal(str)

    class _ComboBox(QComboBox):
        def wheelEvent(self, event) -> None:
            if not self.view().isVisible():
                event.ignore()
            else:
                super().wheelEvent(event)

    def __init__(self, label: str, options: List[Dict[str, Any]]) -> None:
        super().__init__()
        self.options = options
        self._setup_ui(label)

    def _setup_ui(self, label: str) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(text=label)
        self.label.setObjectName("settingsComboBoxLabel")

        self.combo = self._ComboBox()
        self.combo.setObjectName("settingsComboBox")
        self._populate_combo()

        self.combo.currentIndexChanged.connect(
            lambda index: self.valueChanged.emit(self.combo.itemData(index))
        )

        layout.addWidget(self.label, 0, 0)
        layout.addWidget(self.combo, 0, 1)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 4)

    def _populate_combo(self) -> None:
        for index, option in enumerate(self.options):
            self.combo.addItem(option["label"], option["value"])

            if option.get("disabled", False):
                item = self.combo.model().item(index)
                if item:
                    item.setEnabled(False)

            if option.get("tooltip"):
                self.combo.setItemData(
                    index, option["tooltip"], Qt.ItemDataRole.ToolTipRole)

    def get_current_value(self) -> str:
        return self.combo.currentData() or ""

    def set_current_value(self, value: str) -> None:
        index = self.combo.findData(value)
        if index != -1:
            self.combo.blockSignals(True)
            self.combo.setCurrentIndex(index)
            self.combo.blockSignals(False)

    def set_label_text(self, text: str) -> None:
        self.label.setText(text)


class SectionHeader(QWidget):
    def __init__(self, title: str) -> None:
        super().__init__()
        self._setup_ui(title)

    def _setup_ui(self, title: str) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Title label
        self.title_label = QLabel(title)
        self.title_label.setObjectName("settingsSectionTitle")
        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        # Separator line
        self.separator = QFrame()
        self.separator.setFixedHeight(1)
        self.separator.setObjectName("settingsSectionSeparator")
        self.separator.setFrameShape(QFrame.Shape.HLine)
        self.separator.setFrameShadow(QFrame.Shadow.Sunken)
        self.separator.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout.addWidget(self.title_label)
        layout.addWidget(self.separator)

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)


class ConfigCheckBox(QCheckBox):
    def __init__(self, text: str, tooltip: str = "") -> None:
        super().__init__(text)
        self.setObjectName("settingsCheckbox")
        if tooltip:
            self.setToolTip(tooltip)


# class BD2ModPreviewUpdateAlert(QWidget):
#     updateButtonClicked = Signal()

#     def __init__(self, parent: QWidget | None = None) -> None:
#         super().__init__(parent)
#         self.setObjectName("updateAlertWidget")

#         self._icon_label = QLabel()
#         self._icon_label.setObjectName("updateAlertIcon")
#         self._icon_label.setPixmap(ThemeManager.icon("cloud_download").pixmap(64, 64))

#         self._title = QLabel("An update for BD2ModPreview is available")
#         self._title.setObjectName("updateAlertTitle")

#         self._desc = QLabel()
#         self._desc.setObjectName("updateAlertDesc")
#         self._desc.setWordWrap(True)

#         self._update_btn = QPushButton("Update")
#         self._update_btn.setObjectName("updateAlertButton")
#         self._update_btn.setCursor(Qt.CursorShape.PointingHandCursor)

#         main_layout = QHBoxLayout(self)
#         main_layout.setContentsMargins(*[16]*4)
#         main_layout.setSpacing(16)

#         text_layout = QVBoxLayout()
#         text_layout.setSpacing(4)
#         text_layout.addWidget(self._title)
#         text_layout.addWidget(self._desc)

#         main_layout.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignCenter)
#         main_layout.addLayout(text_layout, 1)
#         main_layout.addWidget(self._update_btn, 0, Qt.AlignmentFlag.AlignCenter)

#         self._update_btn.clicked.connect(self.updateButtonClicked.emit)

#         self.set_version("2.3.0")

#     def set_version(self, version: str) -> None:
#         self._desc.setText(
#             f"BD2ModPreview v{version} is available. Click 'Update' to automatically install it."
#         )

#     def paintEvent(self, event) -> None:
#         option = QStyleOption()
#         option.initFrom(self)
#         painter = QPainter(self)
#         self.style().drawPrimitive(
#             self.style().PrimitiveElement.PE_Widget, option, painter, self
#         )


class ConfigView(QScrollArea):
    languageChanged = Signal(str)
    themeChanged = Signal(str)
    gameDirectoryChanged = Signal(str)
    modsDirectoryChanged = Signal(str)
    syncMethodChanged = Signal(str)
    searchModsRecursivelyChanged = Signal(bool)
    includeModRelativePathChanged = Signal(bool)
    
    autoDownloadGameDataChanged = Signal(bool)
    notifyAppUpdateChanged = Signal(bool)

    # Action signals
    findAuthorsClicked = Signal()
    migrateToProfilesClicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._config_cache: Dict[str, Any] = {}
        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self) -> None:
        self.setWidgetResizable(True)
        self.setObjectName("configView")

        # Main widget and layout
        widget = QWidget()
        widget.setObjectName("settingsView")

        self.main_layout = QVBoxLayout(widget)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(24)

        # Title
        self.title = QLabel(text=self.tr("Settings"))
        self.title.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.title.setObjectName("settingsTitle")

        # self.bd2modpreview_update =  BD2ModPreviewUpdateAlert()

        self._create_sections()
        self._layout_sections()

        self.setWidget(widget)

    def _create_sections(self) -> None:
        self._create_paths_section()
        self._create_general_section()
        self._create_synchronization_section()
        self._create_experimental_section()

    def _create_paths_section(self) -> None:
        self.paths_header = SectionHeader(self.tr("Paths"))

        self.game_directory_input = DirectoryInput(
            label=self.tr("Game Directory"),
            placeholder=self.tr("Select game installation directory")
        )

        self.mods_directory_input = DirectoryInput(
            label=self.tr("Mods Directory"),
            placeholder=self.tr("Select mods staging directory")
        )

        self.recursive_search_checkbox = ConfigCheckBox(
            self.tr("Search Mods Recursively"),
            self.tr("Search for mods in subdirectories")
        )

    def _create_general_section(self) -> None:
        self.general_header = SectionHeader(self.tr("General"))

        self.language_combobox = ConfigComboBox(
            label=self.tr("Language:"),
            options=[
                {"label": "English", "value": "en-US", "tooltip": "English (United States)"},
                {"label": "Português (BR)", "value": "pt-BR", "tooltip": "Portuguese (Brazil)"},
                {"label": "日本語", "value": "ja-JP", "tooltip": "Japanese"},
                {"label": "한국어", "value": "ko-KR", "tooltip": "Korean"},
            ],
        )

        self.theme_combobox = ConfigComboBox(
            label=self.tr("Theme:"),
            options=[{
                "label": theme,
                "value": theme
            } for theme in ThemeManager.get_available_themes()]
        )

        self.include_mod_relative_path_checkbox = ConfigCheckBox(
            self.tr("Show full mod folder paths"),
            self.tr("Display complete folder paths in mod list")
        )
        
        # self.notify_on_app_update_checkbox = ConfigCheckBox(
        #     self.tr("Notify when a new app version is available"),
        #     self.tr("Shows a notification when there's a new app update to download.") 
        # )
        
        self.auto_download_game_data_checkbox = ConfigCheckBox(
            self.tr("Automatically download new game data"),
            self.tr("Keeps content like characters, authors, and NPCs up-to-date.")
        )

    def _create_synchronization_section(self) -> None:
        self.synchronization_header = SectionHeader(self.tr("Synchronization"))

        self.sync_method_combobox = ConfigComboBox(
            label=self.tr("Sync Method:"),
            options=[
                {
                    "label": self.tr("Copy (Default)"),
                    "value": "copy",
                    "tooltip": self.tr("Copy files (slower but safer)")
                },
                {
                    "label": self.tr("Symlink (Administrator)"),
                    "value": "symlink",
                    "tooltip": self.tr("Create symbolic links (requires administrator privileges)")
                },
            ],
        )

    def _create_experimental_section(self) -> None:
        self.experimental_header = SectionHeader(
            self.tr("Experimental Features"))

        self.find_authors_button = QPushButton(self.tr("Find Authors"))
        self.find_authors_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.find_authors_button.setObjectName("modsButton")
        self.find_authors_button.setToolTip(
            self.tr("Automatically detect mod authors"))

        self.migrate_to_profiles_button = QPushButton(
            self.tr("Migrate to Profiles"))
        self.migrate_to_profiles_button.setCursor(
            Qt.CursorShape.PointingHandCursor)
        self.migrate_to_profiles_button.setObjectName("modsButton")
        self.migrate_to_profiles_button.setToolTip(
            self.tr("Convert existing setup to profile system"))

    def _layout_sections(self) -> None:
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.main_layout.addWidget(self.title)

        # self.main_layout.addWidget(self.bd2modpreview_update)

        # Paths section
        self.main_layout.addWidget(self.paths_header)
        self.main_layout.addWidget(self.game_directory_input)
        self.main_layout.addWidget(self.mods_directory_input)
        self.main_layout.addWidget(self.recursive_search_checkbox)

        # General section
        self.main_layout.addWidget(self.general_header)
        self.main_layout.addWidget(self.theme_combobox)
        self.main_layout.addWidget(self.language_combobox)
        # self.main_layout.addWidget(self.notify_on_app_update_checkbox)
        self.main_layout.addWidget(self.auto_download_game_data_checkbox)
        self.main_layout.addWidget(self.include_mod_relative_path_checkbox)

        # Synchronization section
        self.main_layout.addWidget(self.synchronization_header)
        self.main_layout.addWidget(self.sync_method_combobox)

        # Experimental section
        self.main_layout.addWidget(self.experimental_header)
        experimental_container = QWidget()
        experimental_layout = QHBoxLayout(experimental_container)
        experimental_layout.setContentsMargins(0, 0, 0, 0)
        experimental_layout.setSpacing(12)
        experimental_layout.addWidget(self.find_authors_button)
        experimental_layout.addWidget(self.migrate_to_profiles_button)
        experimental_layout.addStretch()
        self.main_layout.addWidget(experimental_container)

        # Add stretch at the end
        self.main_layout.addStretch()

    def _setup_connections(self) -> None:
        # Directory inputs
        self.game_directory_input.directoryChanged.connect(
            self.gameDirectoryChanged.emit)
        self.mods_directory_input.directoryChanged.connect(
            self.modsDirectoryChanged.emit)

        # Checkboxes
        self.recursive_search_checkbox.stateChanged.connect(
            self.searchModsRecursivelyChanged.emit)
        self.include_mod_relative_path_checkbox.stateChanged.connect(
            self.includeModRelativePathChanged.emit)
        self.auto_download_game_data_checkbox.stateChanged.connect(
            self.autoDownloadGameDataChanged.emit
        )
        # self.notify_on_app_update_checkbox.stateChanged.connect(
        #     self.notifyAppUpdateChanged.emit
        # )

        # Combo boxes
        self.language_combobox.valueChanged.connect(self.languageChanged.emit)
        self.theme_combobox.valueChanged.connect(self.themeChanged.emit)
        self.sync_method_combobox.valueChanged.connect(
            self.syncMethodChanged.emit)

        # Buttons
        self.find_authors_button.clicked.connect(self.findAuthorsClicked.emit)
        self.migrate_to_profiles_button.clicked.connect(
            self.migrateToProfilesClicked.emit)

    @Slot(dict)
    def update_config(self, config: Dict[str, Any]) -> None:
        self.set_game_directory(config.get("game_directory", ""))
        self.set_mods_directory(config.get("mods_directory", ""))
        self.set_search_mods_recursively(
            config.get("search_mods_recursively", False))
        self.set_language(config.get("language", "en_US"))
        self.set_theme(config.get("theme", "System"))
        self.set_sync_method(config.get("sync_method", "Copy"))
        self.set_include_mod_relative_path(
            config.get("include_mod_relative_path", False))

        # self.set_notify_on_app_update(
        #     config.get("notify_on_app_update", True))
        self.set_auto_download_game_data(
            config.get("auto_download_game_data", True))

    @Slot(str)
    def set_game_directory(self, path: str) -> None:
        self.game_directory_input.blockSignals(True)
        self.game_directory_input.set_directory_path(path)
        self.game_directory_input.blockSignals(False)

    @Slot(str)
    def set_mods_directory(self, path: str) -> None:
        self.mods_directory_input.blockSignals(True)
        self.mods_directory_input.set_directory_path(path)
        self.mods_directory_input.blockSignals(False)

    @Slot(bool)
    def set_search_mods_recursively(self, value: bool) -> None:
        self.recursive_search_checkbox.blockSignals(True)
        self.recursive_search_checkbox.setChecked(value)
        self.recursive_search_checkbox.blockSignals(False)

    @Slot(str)
    def set_language(self, language: str) -> None:
        self.language_combobox.blockSignals(True)
        self.language_combobox.set_current_value(language)
        self.language_combobox.blockSignals(False)

    @Slot(str)
    def set_theme(self, theme: str) -> None:
        self.theme_combobox.blockSignals(True)
        self.theme_combobox.set_current_value(theme)
        self.theme_combobox.blockSignals(False)

    @Slot(str)
    def set_sync_method(self, method: str) -> None:
        self.sync_method_combobox.blockSignals(True)
        self.sync_method_combobox.set_current_value(method)
        self.sync_method_combobox.blockSignals(False)

    @Slot(bool)
    def set_include_mod_relative_path(self, value: bool) -> None:
        self.include_mod_relative_path_checkbox.blockSignals(True)
        self.include_mod_relative_path_checkbox.setChecked(value)
        self.include_mod_relative_path_checkbox.blockSignals(False)
    
    # @Slot(bool)
    # def set_notify_on_app_update(self, value: bool) -> None:
    #     """Sets the state of the app update notification checkbox."""
    #     self.notify_on_app_update_checkbox.blockSignals(True)
    #     self.notify_on_app_update_checkbox.setChecked(value)
    #     self.notify_on_app_update_checkbox.blockSignals(False)

    @Slot(bool)
    def set_auto_download_game_data(self, value: bool) -> None:
        """Sets the state of the auto download game data checkbox."""
        self.auto_download_game_data_checkbox.blockSignals(True)
        self.auto_download_game_data_checkbox.setChecked(value)
        self.auto_download_game_data_checkbox.blockSignals(False)

    def retranslateUI(self) -> None:
        self.title.setText(self.tr("Settings"))

        # Update section headers
        self.paths_header.set_title(self.tr("Paths"))
        self.general_header.set_title(self.tr("General"))
        self.synchronization_header.set_title(self.tr("Synchronization"))
        self.experimental_header.set_title(self.tr("Experimental Features"))

        # Update input widgets
        self.game_directory_input.retranslateUI()
        self.mods_directory_input.retranslateUI()
        self.game_directory_input.set_label_text(self.tr("Game Directory"))
        self.mods_directory_input.set_label_text(self.tr("Mods Directory"))

        self.language_combobox.set_label_text(self.tr("Language:"))
        self.theme_combobox.set_label_text(self.tr("Theme:"))
        self.sync_method_combobox.set_label_text(self.tr("Sync Method:"))

        self.recursive_search_checkbox.setText(
            self.tr("Search Mods Recursively"))
        self.include_mod_relative_path_checkbox.setText(
            self.tr("Show full mod folder paths"))
        
        # self.notify_on_app_update_checkbox.setText(
        #     self.tr("Notify when a new app version is available"))
        # self.notify_on_app_update_checkbox.setToolTip(
        #     self.tr("Shows a notification when there's a new app update to download."))
        self.auto_download_game_data_checkbox.setText(
            self.tr("Automatically download new game data"))
        self.auto_download_game_data_checkbox.setToolTip(
            self.tr("Keeps content like characters, authors, and NPCs up-to-date."))

        self.find_authors_button.setText(self.tr("Find Authors"))
        self.migrate_to_profiles_button.setText(self.tr("Migrate to Profiles"))
