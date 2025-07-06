from typing import Union, Optional, Any
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QSettings


class ConfigModel(QObject):
    languageChanged = Signal(str)
    themeChanged = Signal(str)
    gameDirectoryChanged = Signal(str)
    modsDirectoryChanged = Signal(str)
    syncMethodChanged = Signal(str)
    searchModsRecursivelyChanged = Signal(bool)
    includeModRelativePathChanged = Signal(bool)
    checkForUpdatesChanged = Signal(bool)
    spineViewerEnabledChanged = Signal(bool)
    
    DEFAULT_VALUES = {
        "language": "en-US",
        "theme": "dark",
        "sync_method": "copy",
        "search_mods_recursively": False,
        "check_for_updates": True,
        "include_mod_relative_path": False,
        "spine_viewer_enabled": True,
        "manifest_url": "https://raw.githubusercontent.com/bruhnn/BD2ModManager/refs/heads/main/src/manifest.json",
        "releases_url": "https://api.github.com/repos/bruhnn/BD2ModManager/releases"
    }

    def __init__(self, path: Union[str, Path]) -> None:
        super().__init__()
        self._path = Path(path)
        self._settings: QSettings = QSettings(
            str(self._path.resolve()), QSettings.Format.IniFormat
        )

    @property
    def game_directory(self) -> Optional[str]:
        """Returns the game directory path."""
        value = self._settings.value("game_path")
        return str(value) if value is not None else None

    def set_game_directory(self, value: str) -> None:
        """Set the game directory path."""
        if not value:
            raise ValueError("Game directory cannot be empty")
        self._settings.setValue("game_path", value)
        self.gameDirectoryChanged.emit(value)

    @property
    def mods_directory(self) -> Optional[str]:
        """Returns the staging mods directory path."""
        value = self._settings.value("staging_mods_path")
        return str(value) if value is not None else None

    def set_mods_directory(self, value: str) -> None:
        """Set the mods directory path."""
        if not value:
            raise ValueError("Mods directory cannot be empty")
        self._settings.setValue("staging_mods_path", value)
        self.modsDirectoryChanged.emit(value)

    @property
    def language(self) -> str:
        """Returns the user-defined app language."""
        return self._settings.value(
            "Interface/language", defaultValue=self.DEFAULT_VALUES.get("language"), type=str
        )

    def set_language(self, value: str) -> None:
        """Set the app language."""
        if not value:
            raise ValueError("Language cannot be empty")
        self._settings.setValue("Interface/language", value)
        self.languageChanged.emit(value)

    @property
    def theme(self) -> str:
        """Returns the app theme."""
        return self._settings.value("Interface/theme", defaultValue=self.DEFAULT_VALUES.get("theme"), type=str)

    def set_theme(self, value: str) -> None:
        """Set the app theme."""
        self._settings.setValue("Interface/theme", value)
        self.themeChanged.emit(value)

    @property
    def sync_method(self) -> str:
        """Returns the sync method."""
        return self._settings.value("sync_method", defaultValue=self.DEFAULT_VALUES.get("sync_method"), type=str)

    def set_sync_method(self, value: str) -> None:
        """Set the sync method."""
        self._settings.setValue("sync_method", value)
        self.syncMethodChanged.emit(value)

    @property
    def search_mods_recursively(self) -> bool:
        """Returns whether to search mods recursively."""
        return self._settings.value(
            "search_mods_recursively", defaultValue=self.DEFAULT_VALUES.get("search_mods_recursively"), type=bool
        )

    def set_search_mods_recursively(self, value: bool) -> None:
        """Set whether to search mods recursively."""
        self._settings.setValue("search_mods_recursively", value)
        self.searchModsRecursivelyChanged.emit(value)

    @property
    def include_mod_relative_path(self) -> bool:
        """Returns whether to include mod relative path."""
        return self._settings.value("Interface/include_mod_relative_path", defaultValue=self.DEFAULT_VALUES.get("include_mod_relative_path"), type=bool)

    def set_include_mod_relative_path(self, value: bool) -> None:
        """Set whether to include mod relative path."""
        self._settings.setValue("Interface/include_mod_relative_path", value)
        self.includeModRelativePathChanged.emit(value)

    @property
    def spine_viewer_enabled(self) -> bool:
        """Returns whether spine viewer is enabled."""
        return self._settings.value("spine_viewer_enabled", defaultValue=self.DEFAULT_VALUES.get("spine_viewer_enabled"), type=bool)

    def set_spine_viewer_enabled(self, value: bool) -> None:
        """Set whether spine viewer is enabled."""
        self._settings.setValue("spine_viewer_enabled", value)
        self.spineViewerEnabledChanged.emit(value)
        
    @property
    def check_for_updates(self) -> bool:
        """Returns whether to check for updates."""
        return self._settings.value("Update/check_for_updates", defaultValue=self.DEFAULT_VALUES.get("check_for_updates"), type=bool)

    def set_check_for_updates(self, value: bool) -> None:
        """Set whether to check for updates."""
        self._settings.setValue("check_for_updates", value)
        self.checkForUpdatesChanged.emit(value)
        
    @property
    def manifest_url(self) -> str:
        return self._settings.value("Update/manifest_url", defaultValue=self.DEFAULT_VALUES.get("manifest_url"))
    
    @property
    def releases_url(self) -> str:
        return self._settings.value("Update/releases_url", defaultValue=self.DEFAULT_VALUES.get("releases_url"))
    

    def get(self, key: str, default: Any = None, value_type: type = str) -> Any:
        """Get a configuration value by key."""
        return self._settings.value(key, defaultValue=default, type=value_type)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value by key."""
        self._settings.setValue(key, value)

    def sync(self) -> None:
        """Force synchronization of settings to storage."""
        self._settings.sync()

    def as_dict(self) -> dict:
        """Return configuration as a dictionary."""
        return {
            "game_directory": self.game_directory,
            "mods_directory": self.mods_directory,
            "search_mods_recursively": self.search_mods_recursively,
            "language": self.language,
            "theme": self.theme,
            "sync_method": self.sync_method,
            "check_for_updates": self.check_for_updates,
            "spine_viewer_enabled": self.spine_viewer_enabled,
            "include_mod_relative_path": self.include_mod_relative_path,
        }