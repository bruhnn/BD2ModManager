from typing import Union, Optional, Any
from pathlib import Path
from configparser import ConfigParser

class BD2MMConfigManager:
    def __init__(self, path: Union[str, Path]):
        self._path = Path(path)
        self._config_parser = ConfigParser()

        if not self._config_parser.read(self._path):
            self._create_defaults()

    @property
    def game_directory(self) -> Optional[Path]:
        """
        Returns the game directory path.
        """
        game_dir = (
            self._config_parser.get("General", "game_path", fallback=None) or None
        )
        if game_dir is not None:
            game_dir = Path(game_dir)
        return game_dir

    @game_directory.setter
    def game_directory(self, value: Union[str, Path]):
        """
        Sets the game directory path.
        """
        if isinstance(value, Path):
            value = Path(value).absolute().as_posix()

        self._config_parser.set("General", "game_path", value)
        self._save_config()
    
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
        self._save_config()

    def _create_defaults(self):
        self._config_parser.read_dict({"General": {
            "game_path": "",
            "staging_mods_path": "",
            "language": "english",
            "theme": "default",
            "sync_method": "copy",
            "ask_for_author": False,
            "search_mods_recursively": False
        }})

        self._save_config()

    def _save_config(self):
        with self._path.open(mode="w", encoding="UTF-8") as file:
            self._config_parser.write(file)
