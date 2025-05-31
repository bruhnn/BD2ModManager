from typing import Union, Optional
from pathlib import Path
from configparser import ConfigParser


class BD2MMConfig:
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

    def _create_defaults(self):
        self._config_parser.read_dict({"General": {"GAME_PATH": ""}})

        self._save_config()

    def _save_config(self):
        with self._path.open(mode="w", encoding="UTF-8") as file:
            self._config_parser.write(file)
