import re
import json
import logging
from typing import Callable, Union, Optional, Any
from pathlib import Path
from shutil import copytree, rmtree

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

# TODO: add missing logging information

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

def required_game_path(function: Callable) -> Callable:
    def wrapper(self, *args, **kwargs):
        if not self._game_directory:
            raise GameDirectoryNotSetError(
                "Game path is not set. Please set the game path first."
            )
        return function(self, *args, **kwargs)

    return wrapper


CURRENT_PATH = Path(__file__).parent
DEFAULT_MODS_DIRECTORY = CURRENT_PATH / "mods"
DATA_FOLDER = CURRENT_PATH / "data"
CHARACTERS_CSV = DATA_FOLDER / "characters_id.csv"
DATA_FILE = DATA_FOLDER / "mods.json"

# TODO: Add docstring to all methods.


class BD2ModManager:
    """Brown Dust 2 Mod Manager"""

    def __init__(self, mods_directory: Union[str, Path] = DEFAULT_MODS_DIRECTORY):
        self.characters = BD2Characters(CHARACTERS_CSV)

        self._game_directory = None
        self._staging_mods_directory = Path(mods_directory)

        if not self._staging_mods_directory.exists():
            self._staging_mods_directory.mkdir()

        if not DATA_FOLDER.exists():
            DATA_FOLDER.mkdir(exist_ok=True)

        self._mods_data = self._load_mods_data()

    @property
    def game_directory(self) -> Optional[Path]:
        """Returns the game directory if set, otherwise None."""
        return self._game_directory
    
    @property
    def staging_mods_directory(self) -> Path:
        """Returns the path to the staging mods directory."""
        return self._staging_mods_directory

    def _load_mods_data(self) -> dict:
        """Loads the mods data from the JSON file."""
        
        if not DATA_FILE.exists():
            logger.info("Data file %s does not exist. Creating an empty data file.", DATA_FILE)
            
            with DATA_FILE.open("w", encoding="UTF-8") as file:
                json.dump({}, file, indent=4)
                
            return {}

        logger.debug("Loading mods data from %s", DATA_FILE)
        
        try:
            with DATA_FILE.open("r", encoding="UTF-8") as file:
                data = json.load(file)
        except json.JSONDecodeError:
            logger.error("Invalid JSON data file. Using empty data.")
            data = {}
        
        return data

    def _save_mods_data(self) -> None:
        """Saves the mods data to the JSON file."""
        
        logger.debug("Saving mods data to %s", DATA_FILE)
        
        with DATA_FILE.open("w", encoding="UTF-8") as file:
            json.dump(self._mods_data, file, indent=4) 
        
        logger.debug("Mods data saved successfully to %s", DATA_FILE)

    def _set_mod_data(self, mod_name: str, key: str, value: Any) -> None:
        """Sets the mod data for a given mod name and key."""
        
        logger.debug("Setting mod data for %s: %s = %s", mod_name, key, value)
        
        if mod_name not in self._mods_data:
            logger.debug("Mod %s not found in mods data. Creating new entry.", mod_name)
            self._mods_data[mod_name] = {}
        
        if self._mods_data[mod_name].get(key) == value:
            logger.debug(
                "Mod %s already has %s set to %s. No changes made.", mod_name, key, value)
            return

        self._mods_data[mod_name][key] = value
        logger.debug("Mod data for %s updated: %s = %s", mod_name, key, value)
        
        self._save_mods_data()

    def set_game_directory(self, path: Union[str, Path]) -> None:
        """Sets the game directory path."""
        exe_path = Path(path) / "BrownDust II.exe"

        if not exe_path.exists():
            logger.error("The game executable does not exist at %s", exe_path)
            raise GameNotFoundError(
                f"The game executable does not exist at {exe_path}."
            )

        self._game_directory = Path(path)
        
        logger.debug("Game path set to %s", path)

    def check_game_directory(self) -> bool:
        """Returns True if the game directory contains the game executable."""
        
        if not self._game_directory:
            return False

        exe_path = Path(self._game_directory) / "BrownDust II.exe"
        
        logger.debug("Checking if game executable exists at %s", exe_path)

        if exe_path.exists():
            logger.debug("Game executable found at %s", exe_path)
            return True

        logger.warning("Game executable not found at %s", exe_path)
        
        return False
    
    def set_staging_mods_directory(self, path: Union[str, Path]) -> None:
        """Sets the staging mods directory path."""
        
        staging_path = Path(path)
        
        if not staging_path.exists():
            logger.debug("Staging mods directory does not exist. Creating: %s", staging_path)
            staging_path.mkdir(parents=True, exist_ok=True)

        self._staging_mods_directory = staging_path
        
        logger.debug("Staging mods directory set to %s", self._staging_mods_directory)
        
    def _get_mod_info(self, path: Path) -> dict:
        """Extracts mod information from the mod file in the given path."""    
        modfile = next(path.glob("*.modfile"))
        
        if modfile is None:
            logger.error("No .modfile found in %s", path)
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
        
        logger.debug(
            "Mod info extracted: name=%s, type=%s, character_id=%s, scene_id=%s, npc_id=%s",
            path.name,
            data.get("type"),
            data.get("character_id"),
            data.get("scene_id"),
            data.get("npc_id"),
        )

        return data

    def get_mods(self) -> list[dict]:
        """Returns a list of all mods found in the staging mods directory."""
        
        modfiles = self._staging_mods_directory.rglob("*.modfile")
        mods_folders = [modfile.parent for modfile in modfiles]
        
        logger.debug("Found %d mod folders.", len(mods_folders))

        mods = []

        for mod_folder in mods_folders:
            mod_info = self._get_mod_info(mod_folder)
            mod_metadata = self._mods_data.get(mod_folder.name, {})
            
            character = None
            
            if mod_info.get("character_id") is not None:
                character = self.characters.get_character_by_id(mod_info.get("character_id"))

            mod = {
                "type": mod_info.get("type"),
                "name": mod_folder.name,
                "character": character,
                "author": mod_metadata.get("author", None),
                "enabled": mod_metadata.get("enabled", False),
            }

            mods.append(mod)
        
        logger.debug("Total mods found: %d", len(mods))

        return mods

    def get_characters_mod_status(self) -> dict:
        """Returns a dictionary with characters and their mod status."""
        
        mods_installed = [
            mod
            for mod in self.get_mods()
            if mod["type"] in ("cutscene", "idle") and mod["enabled"]
        ]
        
        mods_cutscenes = {mod["character"]["id"] for mod in mods_installed if mod["type"] == "cutscene"}
        mods_idles = {mod["character"]["id"] for mod in mods_installed if mod["type"] == "idle"}

        characters_modded = {}

        for char_id, character in self.characters.characters.items():
            group = character["character"]
            characters_modded.setdefault(group, []).append({
                "character": character,
                "cutscene": char_id in mods_cutscenes,
                "idle": char_id in mods_idles,
            })

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
            logger.error("Source mod path does not exist: %s", mod_source)
            raise FileNotFoundError(f"Source mod path does not exist: {mod_source!r}")

        mod_name = name or mod_source.name
        

        staging_mod = self._staging_mods_directory / mod_name
        
        logger.debug("Adding mod: %s", mod_name)

        if staging_mod.exists():
            logger.error("Mod already exists: %s", mod_name)
            raise ModAlreadyExistsError(mod_name)

        if author:
            self._set_mod_data(mod_name, "author", author)

        if enabled:
            self._set_mod_data(mod_name, "enabled", enabled)

        logger.debug("Copying mod from %s to %s", mod_source, staging_mod)
        copytree(mod_source, staging_mod)
        logger.debug("Mod %s copied successfully.", mod_name)

    def remove_mod(self, mod_name: str) -> None:
        mod_path = self._staging_mods_directory / mod_name

        if not mod_path.exists():
            logger.error("Mod not found: %s", mod_name)
            raise ModNotFoundError()

        logger.debug("Removing mod: %s", mod_name)
        rmtree(mod_path)
        logger.debug("Mod %s removed successfully.", mod_name)

        if mod_name in self._mods_data:
            logger.debug("Removing mod data for %s", mod_name)
            self._mods_data.pop(mod_name)
            self._save_mods_data()

    def enable_mod(self, mod_name: str) -> None:
        logger.debug("Enabling mod: %s", mod_name)
        self._set_mod_data(mod_name, "enabled", True)

    def disable_mod(self, mod_name: str) -> None:
        logger.debug("Disabling mod: %s", mod_name)
        self._set_mod_data(mod_name, "enabled", False)

    def set_mod_author(self, mod_name: str, author: str) -> None:
        logger.debug("Setting author for mod %s to %s", mod_name, author)
        self._set_mod_data(mod_name, "author", author)

    @required_game_path
    def sync_mods(self, symlink: bool = False) -> None:
        if not self.is_browndustx_installed():
            raise BrownDustXNotInstalled()

        game_mods_directory = self._game_directory / r"BepInEx\plugins\BrownDustX\mods"
        
        logger.debug("Game mods directory: %s", game_mods_directory)

        if not game_mods_directory.exists():
            logger.debug("Creating game mods directory: %s", game_mods_directory)
            game_mods_directory.mkdir()
        
        if symlink and not is_running_as_admin():
            logger.error("Administrator privileges are required to use symlinks.")
            raise AdminRequiredError(
                "Administrator privileges are required to use symlinks."
            )

        modfiles = self._staging_mods_directory.rglob("*.modfile")
        mods = [modfile.parent for modfile in modfiles]
        
        logger.debug("Found %d mod files to sync.", len(mods))

        mods_installed = []

        if Path("sync.json").exists():
            logger.debug("Loading installed mods from sync.json")
            with open("sync.json", "r", encoding="UTF-8") as file:
                try:
                    mods_installed = json.load(file)
                except json.JSONDecodeError:
                    logger.error("Invalid JSON in sync.json. Using empty list.")
            

        # installed_mod_names = {mod.name for mod in mods}
        # removed_mods = [mod for mod in mods_installed if mod not in installed_mod_names]

        # for mod in removed_mods:
        #     pass

        for mod in mods:
            mod_game_path = game_mods_directory / mod.name
            mod_enabled = self._mods_data.get(mod.name, {}).get("enabled", False)

            if mod_enabled:
                logger.debug("mod %s is enabled.", mod.name)
                if not mod_game_path.exists():
                    if symlink:
                        logger.debug(
                            "Creating symlink for mod %s at %s", mod.name, mod_game_path
                        )
                        mod_game_path.symlink_to(
                            mod.resolve(), target_is_directory=True
                        )
                    else:
                        logger.debug(
                            "Copying mod %s to game mods directory: %s", mod.name, mod_game_path
                        )
                        copytree(mod, mod_game_path)

                    if mod.name not in mods_installed:
                        logger.debug("Adding mod %s to installed mods list", mod.name)
                        mods_installed.append(mod.name)
                else:
                    logger.debug("Mod %s already exists at %s", mod.name, mod_game_path)
                    if not get_folder_hash(mod) == get_folder_hash(mod_game_path):
                        logger.debug(
                            "Mod %s has changed. Updating at %s", mod.name, mod_game_path
                        )
                        if symlink:
                            logger.debug(
                                "Removing existing symlink for mod %s at %s",
                                mod.name,
                                mod_game_path,
                            )
                            mod_game_path.rmdir()
                            logger.debug(
                                "Creating new symlink for mod %s at %s",
                                mod.name,
                                mod_game_path,
                            )
                            mod_game_path.symlink_to(
                                mod.resolve(), target_is_directory=True
                            )
                        else:
                            logger.debug(
                                "Removing existing mod %s at %s", mod.name, mod_game_path
                            )
                            rmtree(mod_game_path)
                            logger.debug(
                                "Copying updated mod %s to game mods directory: %s",
                                mod.name,
                                mod_game_path,
                            )
                            copytree(mod, mod_game_path)
                    
            else:
                logger.debug("Mod %s is disabled.", mod.name)
                if mod_game_path.exists():
                    logger.debug("Removing mod %s at %s", mod.name, mod_game_path)
                    if mod_game_path.is_symlink():
                        logger.debug("Removing symlink for mod %s at %s", mod.name, mod_game_path)
                        mod_game_path.rmdir()
                    else:
                        logger.debug("Removing mod folder %s at %s", mod.name, mod_game_path)
                        rmtree(mod_game_path)
                    
                    if mod.name in mods_installed:
                        logger.debug("Removing mod %s from installed mods list", mod.name)
                        mods_installed.remove(mod.name)

        logger.debug("Syncing completed. Installed mods: %s", mods_installed)
        
        with open("sync.json", "w") as file:
            logger.debug("Saving installed mods to sync.json")
            json.dump(mods_installed, file, indent=4)

    @required_game_path
    def unsync_mods(self) -> None:
        game_mods_directory = self._game_directory / r"BepInEx\plugins\BrownDustX\mods"
        logger.debug("Unsyncing mods from game mods directory: %s", game_mods_directory)

        sync_file = Path("sync.json")
        mods_installed = []

        if sync_file.exists():
            with sync_file.open("r", encoding="UTF-8") as file:
                try:
                    mods_installed = json.load(file)
                except json.JSONDecodeError:
                    logger.error("Invalid JSON in sync.json. Using empty list.")
                    mods_installed = []

        removed_mods = []
        for mod_name in list(mods_installed):
            mod_path = game_mods_directory / mod_name
            if mod_path.exists():
                try:
                    if mod_path.is_symlink():
                        logger.debug("Removing symlink for mod %s at %s", mod_name, mod_path)
                        mod_path.unlink()
                    else:
                        logger.debug("Removing mod folder %s at %s", mod_name, mod_path)
                        rmtree(mod_path)
                    removed_mods.append(mod_name)
                except Exception as e:
                    pass
                    logger.error("Failed to remove mod %s: %s", mod_name, e)

        # Remove the mods from the installed list
        mods_installed = [mod for mod in mods_installed if mod not in removed_mods]

        with sync_file.open("w", encoding="UTF-8") as file:
            logger.debug("Saving updated installed mods to sync.json")
            json.dump(mods_installed, file, indent=4)

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
        
        logger.debug("BrownDustX version found: %s", version)
        return version
