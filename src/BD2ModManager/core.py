import re
import json
from typing import Callable, Union, Optional, Any
from pathlib import Path
from shutil import copytree, rmtree

from .config import BD2MMConfig
from .utils import is_running_as_admin
from .utils.characters import BD2Characters
from .utils.files import get_folder_hash
from .errors import (
    GameNotFoundError,
    ModInvalidError,
    GameDirectoryNotSetError,
    ModAlreadyExistsError,
    ModNotFoundError,
    BrownDustXNotInstalled,
    AdminRequiredError,
)


def required_game_path(function: Callable) -> Callable:
    def wrapper(self, *args, **kwargs):
        if not self._game_directory:
            raise GameDirectoryNotSetError(
                "Game path is not set. Please set the game path first."
            )
        return function(self, *args, **kwargs)

    return wrapper


CURRENT_PATH = Path(__file__).parent
CONFIG_FILE = CURRENT_PATH / "BD2ModManager.ini"
DEFAULT_MODS_DIRECTORY = CURRENT_PATH / "mods"
CHARACTERS_CSV = CURRENT_PATH / "utils" / "data" / "characters.csv"

DATA_FOLDER = CURRENT_PATH / "data"
DATA_FILE = DATA_FOLDER / "mods.json"

# TODO: Add docstring to all methods.


class BD2ModManager:
    """Brown Dust 2 Mod Manager"""

    def __init__(self, mods_directory: Union[str, Path] = DEFAULT_MODS_DIRECTORY):
        self.config = BD2MMConfig(path=CONFIG_FILE)
        self.characters = BD2Characters(CHARACTERS_CSV)

        self._game_directory = self.config.game_directory
        self.staging_mods_directory = Path(mods_directory)

        if not self.staging_mods_directory.exists():
            self.staging_mods_directory.mkdir()

        if not DATA_FOLDER.exists():
            DATA_FOLDER.mkdir(exist_ok=True)

        self._mods_data = self._load_mods_data()

    @property
    def game_directory(self) -> Path:
        return self._game_directory

    def _load_mods_data(self) -> dict:
        if not DATA_FILE.exists():
            with DATA_FILE.open("w", encoding="UTF-8") as file:
                json.dump({}, file, indent=4)
            return {}

        
        try:
            with DATA_FILE.open("r", encoding="UTF-8") as file:
                data = json.load(file)
        except json.JSONDecodeError:
            data = {}
        
        return data

    def _save_mods_data(self) -> None:
        with DATA_FILE.open("w", encoding="UTF-8") as file:
            json.dump(self._mods_data, file, indent=4)

    def _set_mod_data(self, mod_name: str, key: str, value: Any) -> None:
        if mod_name not in self._mods_data:
            self._mods_data[mod_name] = {}

        if self._mods_data[mod_name].get(key) == value:
            return

        self._mods_data[mod_name][key] = value
        self._save_mods_data()

    def set_game_directory(self, path: Union[str, Path]) -> None:
        exe_path = Path(path) / "BrownDust II.exe"

        if not exe_path.exists():
            raise GameNotFoundError(
                f"The game executable does not exist at {exe_path}."
            )

        self._game_directory = Path(path)
        self.config.game_directory = path

    def get_game_directory(self) -> Optional[Path]:
        if not self._game_directory:
            return

        exe_path = Path(self._game_directory) / "BrownDust II.exe"

        if exe_path.exists():
            return self._game_directory

    def _get_mod_info(self, path: Path) -> dict:
        modfile = next(path.glob("*.modfile"))

        if modfile is None:
            raise ModInvalidError(f"No .modfile found in {path}")

        type_patterns = {
            "idle": re.compile(r"^char(\d+)\.modfile$", re.I),
            "cutscene": re.compile(r"cutscene_char(\d+)\.modfile$", re.I),
            "scene": re.compile(r"specialillust(\d+)\.modfile$", re.I),
            "npc": re.compile(r"^npc(\d+)\.modfile$"),
            "dating": re.compile(r"^illust_dating(\d+)\.modfile$"),
        }

        mod_type = None
        mod_id = None

        for type, pattern in type_patterns.items():
            match = pattern.match(modfile.name)
            if match:
                mod_type = type
                mod_id = match.group(1)

        data = {"type": mod_type}

        if mod_type in ("idle", "cutscene"):
            data["character_id"] = mod_id
        elif mod_type == "scene":
            data["scene_id"] = mod_id
        elif mod_type == "npc":
            data["npc_id"] = mod_id

        return data

    def get_mods(self) -> list[dict]:
        modfiles = self.staging_mods_directory.rglob("*.modfile")
        mods_folders = [modfile.parent for modfile in modfiles]

        mods = []

        for mod_folder in mods_folders:
            mod_info = self._get_mod_info(mod_folder)

            mod_metadata = self._mods_data.get(mod_folder.name, {})

            mod = {
                "type": mod_info.get("type"),
                "name": mod_folder.name,
                "character": self.characters.get_character_by_id(
                    mod_info.get("character_id")
                )
                if mod_info.get("character_id") is not None
                else {},
                "author": mod_metadata.get("author", None),
                "enabled": mod_metadata.get("enabled", False),
            }

            mods.append(mod)

        return mods

    def get_characters_mods_status(self) -> dict:
        mods = [
            mod
            for mod in self.get_mods()
            if mod["type"] in ("cutscene", "idle") and mod["enabled"]
        ]

        mods_cutscenes = [
            mod["character"]["id"] for mod in mods if mod["type"] == "cutscene"
        ]
        mods_idles = [mod["character"]["id"] for mod in mods if mod["type"] == "idle"]
        characters_modded = {}

        for char_id, character in self.characters.characters.items():
            if not characters_modded.get(character["character"]):
                characters_modded[character["character"]] = []

            characters_modded[character["character"]].append(
                {
                    "character": character,
                    "cutscene": char_id in mods_cutscenes,
                    "idle": char_id in mods_idles,
                }
            )

        return characters_modded

    def add_mod(
        self,
        *,
        path: Union[str, Path],
        name: Optional[str] = None,
        author: Optional[str] = None,
        enabled: bool = False,
    ) -> None:
        mod_source = Path(path)

        if not mod_source.exists():
            raise FileNotFoundError(f"Source mod path does not exist: {mod_source!r}")

        mod_name = name or mod_source.name

        staging_mod = self.staging_mods_directory / mod_name

        if staging_mod.exists():
            raise ModAlreadyExistsError(mod_name)

        if author:
            self._set_mod_data(mod_name, "author", author)

        if enabled:
            self._set_mod_data(mod_name, "enabled", enabled)

        copytree(mod_source, staging_mod)

    def remove_mod(self, mod_name: str) -> None:
        mod_path = self.staging_mods_directory / mod_name

        if not mod_path.exists():
            raise ModNotFoundError()

        rmtree(mod_path)

        if mod_name in self._mods_data:
            self._mods_data.pop(mod_name)
            self._save_mods_data()

    def enable_mod(self, mod_name: str) -> None:
        self._set_mod_data(mod_name, "enabled", True)

    def disable_mod(self, mod_name: str) -> None:
        self._set_mod_data(mod_name, "enabled", False)

    def set_mod_author(self, mod_name: str, author: str) -> None:
        self._set_mod_data(mod_name, "author", author)

    @required_game_path
    def sync_mods(self, symlink: bool = False) -> None:
        if not self.is_browndustx_installed():
            raise BrownDustXNotInstalled()

        game_mods_directory = self._game_directory / r"BepInEx\plugins\BrownDustX\mods"

        if not game_mods_directory.exists():
            game_mods_directory.mkdir()

        if symlink and not is_running_as_admin():
            raise AdminRequiredError(
                "Administrator privileges are required to use symlinks."
            )

        modfiles = self.staging_mods_directory.rglob("*.modfile")
        mods = [modfile.parent for modfile in modfiles]

        mods_installed = []

        if Path("sync.json").exists():
            with open("sync.json", "r", encoding="UTF-8") as file:
                try:
                    mods_installed = json.load(file)
                except json.JSONDecodeError:
                    pass

        installed_mod_names = {mod.name for mod in mods}
        removed_mods = [mod for mod in mods_installed if mod not in installed_mod_names]

        for mod in removed_mods:
            pass

        for mod in mods:
            mod_game_path = game_mods_directory / mod.name
            mod_enabled = self._mods_data.get(mod.name, {}).get("enabled", False)

            if mod_enabled:
                if not mod_game_path.exists():
                    if symlink:
                        mod_game_path.symlink_to(
                            mod.resolve(), target_is_directory=True
                        )
                    else:
                        copytree(mod, mod_game_path)

                    if mod.name not in mods_installed:
                        mods_installed.append(mod.name)
                else:
                    if not get_folder_hash(mod) == get_folder_hash(mod_game_path):
                        if symlink:
                            mod_game_path.rmdir()
                            mod_game_path.symlink_to(
                                mod.resolve(), target_is_directory=True
                            )
                        else:
                            rmtree(mod_game_path)
                            copytree(mod, mod_game_path)
            else:
                if mod_game_path.exists():
                    if mod_game_path.is_symlink():
                        mod_game_path.rmdir()
                    else:
                        rmtree(mod_game_path)
                    
                    if mod.name in mods_installed:
                        mods_installed.remove(mod.name)

        with open("sync.json", "w") as file:
            json.dump(mods_installed, file, indent=4)

    @required_game_path
    def unsync_mods(self) -> None:
        game_mods_directory = self._game_directory / r"BepInEx\plugins\BrownDustX\mods"

        mods_installed = []

        if Path("sync.txt").exists():
            with open("sync.txt", "r") as file:
                mods_installed = [line.strip("\n") for line in file.readlines()]

        for mod in mods_installed:
            if (game_mods_directory / mod).is_symlink():
                (game_mods_directory / mod).rmdir()
            else:
                rmtree(game_mods_directory / mod)
            mods_installed.remove(mod)

        with open("sync.txt", "w") as file:
            file.write("\n".join(mods_installed))

    @required_game_path
    def is_browndustx_installed(self) -> bool:
        return Path(
            self._game_directory
            / r"BepInEx\plugins\BrownDustX\lynesth.bd2.browndustx.dll"
        ).exists()

    @required_game_path
    def get_browndustx_version(self) -> str:
        path = Path(self._game_directory / r"BepInEx\config\lynesth.bd2.browndustx.cfg")
        version = None
        if path.exists():
            with path.open("r", encoding="UTF-8") as file:
                version = file.readline().split()[8]
        return version
