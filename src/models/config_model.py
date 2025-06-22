from typing import Union, Optional, Any
from pathlib import Path
from configparser import ConfigParser

from PySide6.QtCore import QObject, Signal

class ConfigModel(QObject):
    onLanguageChanged = Signal(str)
    onThemeChanged = Signal(str)
    
    onGameDirectoryChanged = Signal(str)
    onModsDirectoryChanged = Signal(str)
    onSyncMethodChanged = Signal(str)
    onAskForAuthorChanged = Signal(bool)
    onSearchModsRecursivelyChanged = Signal(bool)
    
    def __init__(self, path: Union[str, Path]):
        super().__init__()
        self._path = Path(path)
        self._config_parser = ConfigParser()

        if not self._config_parser.read(self._path):
            self._create_defaults()

    @property
    def game_directory(self) -> Optional[str]:
        """
        Returns the game directory path.
        """
        return self._config_parser.get("General", "game_path", fallback=None)

    @game_directory.setter
    def game_directory(self, value: str):
        self.set("game_path", value)
        self.onGameDirectoryChanged.emit(value)

    @property
    def mods_directory(self) -> Optional[str]:
        """
        Returns the staging mods directory path.
        """
        return self._config_parser.get("General", "staging_mods_path", fallback=None)

    @mods_directory.setter
    def mods_directory(self, value: str):
        self.set("staging_mods_path", value)
        self.onModsDirectoryChanged.emit(value)

    @property
    def language(self) -> str:
        """
        Returns the user-defined app language.
        """
        return self._config_parser.get("General", "language", fallback="english")

    @language.setter
    def language(self, value: str):
        self.set("language", value)
        self.onLanguageChanged.emit(value)

    @property
    def theme(self) -> str:
        """
        Returns the app theme.
        """
        return self._config_parser.get("General", "theme", fallback="dark")

    @theme.setter
    def theme(self, value: str):
        self.set("theme", value)
        self.onThemeChanged.emit(value)

    @property
    def ask_for_author(self) -> bool:
        """
        Returns whether to ask for author.
        """
        return self._config_parser.getboolean("General", "ask_for_author", fallback=False)

    @ask_for_author.setter
    def ask_for_author(self, value: bool):
        self.set("ask_for_author", value)
        self.onAskForAuthorChanged.emit(value)

    @property
    def sync_method(self) -> str:
        """
        Returns the sync method.
        """
        return self._config_parser.get("General", "sync_method", fallback="copy")

    @sync_method.setter
    def sync_method(self, value: str):
        self.set("sync_method", value)
        self.onSyncMethodChanged.emit(value)

    @property
    def search_mods_recursively(self) -> bool:
        """
        Returns whether to search mods recursively.
        """
        return self._config_parser.getboolean("General", "search_mods_recursively", fallback=False)

    @search_mods_recursively.setter
    def search_mods_recursively(self, value: bool):
        
        self.set("search_mods_recursively", value)
        self.onSearchModsRecursivelyChanged.emit(value)

    def get(self, key: str, boolean: bool = False, default: Any = None) -> Optional[Union[str, bool]]:
        """
        Returns the value of a specific configuration key.
        """
        if boolean:
            value = self._config_parser.getboolean("General", key, fallback=None)
            return value if value is not None else False

        return self._config_parser.get("General", key, fallback=default)

    def set(self, key: str, value: Union[str, bool]):
        """
        Sets the value of a specific configuration key.
        """
        if isinstance(value, bool):
            value = str(value).lower()
        
        if "General" not in self._config_parser:
            self._config_parser.add_section("General")
            
        self._config_parser.set("General", key, value)
        
        # self.onConfigChanged.emit(key, value)

        if key == "language":
            self.onLanguageChanged.emit(value)
        elif key == "theme":
            self.onThemeChanged.emit(value)
        elif key == "game_path":
            self.onGameDirectoryChanged.emit(value)
        elif key == "staging_mods_path":
            self.onModsDirectoryChanged.emit(value)
        elif key == "sync_method":
            self.onSyncMethodChanged.emit(value)
        elif key == "ask_for_author":
            self.onAskForAuthorChanged.emit(value == "true")
        elif key == "search_mods_recursively":
            self.onSearchModsRecursivelyChanged.emit(value == "true")
        
        self._save_config()

    def _create_defaults(self):
        self._config_parser.read_dict({"General": {
            "game_path": "",
            "staging_mods_path": "",
            "language": "english",
            "theme": "dark",
            "sync_method": "copy",
            "ask_for_author": False,
            "search_mods_recursively": False
        }})

        self._save_config()

    def _save_config(self):
        with self._path.open(mode="w", encoding="UTF-8") as file:
            self._config_parser.write(file)

    def as_dict(self) -> dict:
        return {
            "game_directory": self.game_directory,
            "mods_directory": self.mods_directory,
            "search_mods_recursively": self.search_mods_recursively,
            "language": self.language,
            "theme": self.theme,
            "sync_method": self.sync_method,
            "ask_for_author": self.ask_for_author
        }