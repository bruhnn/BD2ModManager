from PySide6.QtCore import QObject, Signal

from src.models import ConfigModel
from src.views import ConfigView


class ConfigController(QObject):
    validateGameDirectory = Signal(str)
    
    # Actions
    findAuthorsClicked = Signal()
    migrateToProfilesClicked = Signal()

    def __init__(
            self, model: ConfigModel, view: ConfigView) -> None:
        super().__init__()

        self.model = model
        self.view = view

        # View signals
        self.view.gameDirectoryChanged.connect(self._on_game_directory_changed)
        self.view.modsDirectoryChanged.connect(self._on_mods_directory_changed)
        self.view.searchModsRecursivelyChanged.connect(
            self._on_search_mods_recursively_changed)
        self.view.languageChanged.connect(self._on_language_changed)
        self.view.themeChanged.connect(self._on_theme_changed)
        self.view.syncMethodChanged.connect(self._on_sync_method_changed)
        self.view.includeModRelativePathChanged.connect(self._on_include_mod_relative_path)
        
        # View actions
        self.view.findAuthorsClicked.connect(self.findAuthorsClicked.emit)
        self.view.migrateToProfilesClicked.connect(self.migrateToProfilesClicked.emit)

        # Model Signals
        self.model.gameDirectoryChanged.connect(self.view.set_game_directory)
        self.model.modsDirectoryChanged.connect(self.view.set_mods_directory)
        self.model.searchModsRecursivelyChanged.connect(
            self.view.set_search_mods_recursively)
        self.model.languageChanged.connect(self.view.set_language)
        self.model.themeChanged.connect(self.view.set_theme)
        self.model.syncMethodChanged.connect(self.view.set_sync_method)
        self.model.includeModRelativePathChanged.connect(
            self.view.set_include_mod_relative_path)
        self.update_config()

    # --- Slots
    def _on_game_directory_changed(self, path: str) -> None:
        self.validateGameDirectory.emit(path)

    def _on_mods_directory_changed(self, path: str) -> None:
        if self.model.search_mods_recursively: 
            # Avoids UI freeze when selecting folders with many files/subfolders
            # this trigger the update view mods two times*
            self.model.set_search_mods_recursively(False)
            
        self.model.set_mods_directory(path)

    def _on_search_mods_recursively_changed(self, value: bool) -> None:
        self.model.set_search_mods_recursively(value)

    def _on_language_changed(self, language: str) -> None:
        self.model.set_language(language)

    def _on_theme_changed(self, theme: str) -> None:
        self.model.set_theme(theme)

    def _on_sync_method_changed(self, method: str) -> None:
        self.model.set_sync_method(method)

    def _on_include_mod_relative_path(self, value: bool) -> None:
        self.model.set_include_mod_relative_path(value)

    # --- Methods
    def update_config(self) -> None:
        data = self.model.as_dict()
        print(data)
        self.view.update_config(data)

    def set_game_directory(self, path: str) -> None:
        self.model.set_game_directory(path)
