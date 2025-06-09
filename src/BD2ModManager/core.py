import sys
import json
import logging
from typing import Callable, Union, Optional, Any, Dict
from pathlib import Path
from shutil import copytree, rmtree, ReadError
import pefile
import tempfile

from .utils import is_running_as_admin
from .utils.files import get_folder_hash, is_filename_valid, is_compressed_file, extract_file
from .utils.detect_author import get_author_by_folder, load_authors
from .bd2_data import BD2Data
from .errors import *

from .models import BD2Mod, BD2ModEntry, BD2ModType
from .utils.paths import AUTHORS_CSV, CHARACTERS_CSV, DATA_FOLDER, DATINGS_CSV, SCENES_CSV, NPCS_CSV, BUNDLE_PATH, CURRENT_PATH, IS_BUNDLED

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def required_game_path(function: Callable) -> Callable:
    def wrapper(self, *args, **kwargs):
        if not self.game_directory:
            raise GameDirectoryNotSetError(
                "Game path is not set. Please set the game path first."
            )
        return function(self, *args, **kwargs)

    return wrapper


class BD2ModManager:
    """Brown Dust 2 Mod Manager"""

    def __init__(self, mods_directory: Union[str, Path], data_file: Optional[Union[str, Path]] = None):
        self.game_data = BD2Data(
            CHARACTERS_CSV, DATINGS_CSV, SCENES_CSV, NPCS_CSV)

        self._game_directory = None
        self._staging_mods_directory = Path(mods_directory)
        self._data_file = Path(data_file) if data_file else DATA_FOLDER / "mods.json"

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

    def _create_empty_mods_data(self) -> None:
        logger.info("Creating an empty data file.")
        
        self._data_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with self._data_file.open("w", encoding="UTF-8") as file:
                json.dump({}, file, indent=4)
        except (OSError, IOError) as e:
            logger.error("Failed to create data file %s: %s", self._data_file, e)
        
        logger.debug("Created empty data file at %s", self._data_file)

    def _load_mods_data(self) -> dict:
        """Loads the mods data from the JSON file."""

        if not self._data_file.exists():
            logger.info("Data file %s does not exist.", self._data_file)
            
            self._create_empty_mods_data()
            
            return {}

        logger.debug("Loading mods data from %s", self._data_file)

        try:
            with self._data_file.open("r", encoding="UTF-8") as file:
                data = json.load(file)
            
            if not isinstance(data, dict):
                logger.warning("Data file contains non-dict data (type: %s). Using empty data.", type(data).__name__)
                return {}
        except json.JSONDecodeError:
            logger.error("Invalid JSON data file. Using empty data.")
            data = {}
        except (OSError, IOError) as e:
            logger.error("Failed to read data file %s: %s", self._data_file, e)
            
            self._create_empty_mods_data()
            
            return {}
            
        logger.debug("Successfully loaded mods data: %d entries", len(data))

        return data

    def _save_mods_data(self) -> None:
        """Saves the mods data to the JSON file."""

        logger.debug("Saving mods data to %s", self._data_file)
        
        self._data_file.parent.mkdir(exist_ok=True, parents=True)

        try:
            with self._data_file.open("w", encoding="UTF-8") as file:
                json.dump(self._mods_data, file, indent=4)
        except (OSError, IOError) as error:
            return logger.error("Failed to save mods data to %s: %s", self._data_file, error)

        logger.debug("Mods data saved successfully to %s", self._data_file)

    def _set_mod_data(self, mod_name: str, key: str, value: Any) -> bool:
        """Sets the mod data for a given mod name and key."""

        logger.debug("Setting mod data for %s: %s = %s", mod_name, key, value)

        if mod_name not in self._mods_data:
            logger.debug("Mod %s not found in mods data. Creating new entry.", mod_name)
            self._mods_data[mod_name] = {}
        
        if self._mods_data[mod_name].get(key) == value:
            logger.debug("Mod %s already has %s set to %s. No changes made.", mod_name, key, value)
            return False

        old_value = self._mods_data.get(key)
        self._mods_data[mod_name][key] = value
        
        logger.debug("Mod data for %s updated: %s changed from %s to %s", mod_name, key, old_value, value)

        self._save_mods_data()
        
        return True

    def _bulk_set_mod_data(self, mod_names: list[str], key: str, value: Any):
        """Sets the mulitples mod data for a given list of mod names."""
        logger.debug("Starting bulk update: setting %s = %s for %d mods", key, value, len(mod_names))
        
        for mod_name in mod_names:
            if mod_name not in self._mods_data:
                logger.debug("Mod %s not found in mods data. Creating new entry.", mod_name)
                self._mods_data[mod_name] = {}

            # Check if change is needed
            if self._mods_data[mod_name].get(key) == value:
                logger.debug("Mod %s already has %s set to %s. No changes made.", mod_name, key, value)
                continue

            # Update the value
            old_value = self._mods_data[mod_name].get(key)
            self._mods_data[mod_name][key] = value
            
            logger.debug("Mod data for %s updated: %s changed from %s to %s",
                        mod_name, key, old_value, value)

        self._save_mods_data()

    def set_game_directory(self, path: Union[str, Path]) -> None:
        """Sets the game directory path."""
        game_directory = Path(path).resolve()
        
        # Check for bd2 executable
        exe_path = game_directory / "BrownDust II.exe"
        
        if not exe_path.exists():
            logger.error("Game executable not found: %s", exe_path)
            raise GameNotFoundError(f"Game executable 'BrownDust II.exe' not found in directory: {game_directory}")
        
        self._game_directory = game_directory
        logger.info("Game directory successfully set to: %s", game_directory)

    def check_game_directory(self, path: str) -> bool:
        """Returns True if the path contains the game executable."""

        exe_path = Path(path) / "BrownDust II.exe"

        logger.debug("Checking for game executable at: %s", exe_path)

        if not exe_path.exists():
            logger.warning("Game executable not found at %s", exe_path)
            return False

        logger.debug("Game executable found at: %s", exe_path)

        return True

    def set_staging_mods_directory(self, path: Union[str, Path]) -> None:
        """Sets the staging mods directory path."""

        staging_path = Path(path)

        if not staging_path.exists():
            logger.debug("Staging mods directory does not exist. Creating: %s", staging_path)
            staging_path.mkdir(parents=True, exist_ok=True)

        self._staging_mods_directory = staging_path
        logger.debug("Staging mods directory set to %s", self._staging_mods_directory)

    def get_mods(self, recursive: bool = False) -> list[BD2ModEntry]:
        """Returns a list of all mods found in the staging mods directory."""
        logger.debug("Getting mods from staging directory: %s", self._staging_mods_directory)

        if recursive:
            modfiles = self._staging_mods_directory.rglob("*.modfile")
        else:
            modfiles = self._staging_mods_directory.glob("*/*.modfile")

        mods_folders = [modfile.parent for modfile in modfiles]

        logger.debug("Found %d mod folders.", len(mods_folders))

        mods = []
        for mod_folder in mods_folders:
            mod_metadata = self._mods_data.get(mod_folder.name, {})

            mod = BD2Mod.from_mod_path(mod_folder)

            mod_entry = BD2ModEntry(
                mod=mod,
                path=mod_folder.absolute().as_posix(),
                author=mod_metadata.get("author", None),
                enabled=mod_metadata.get("enabled", False)
            )

            if mod.type in (BD2ModType.CUTSCENE, BD2ModType.IDLE) and mod.character_id is not None:  # Set character
                char = self.game_data.get_character_by_id(mod.character_id)
                mod_entry.character = char
            elif mod.type == BD2ModType.DATING and mod.dating_id is not None:
                char = self.game_data.get_character_by_dating_id(mod.dating_id)
                mod_entry.character = char
            elif mod.type == BD2ModType.NPC and mod.npc_id is not None:
                npc = self.game_data.get_npc_by_id(mod.npc_id)
                mod_entry.npc = npc
            elif mod.type == BD2ModType.SCENE and mod.scene_id is not None:
                scene = self.game_data.get_scene_by_id(mod.scene_id)
                mod_entry.scene = scene

            mods.append(mod_entry)

        logger.debug("Total mods found: %d", len(mods))

        return mods

    def get_characters_mod_status(self, recursive: bool = False) -> dict:
        """Returns a dictionary with characters and their mod status."""

        logger.debug("Getting character mod status")

        mods = self.get_mods(recursive)
        mods_ids_cutscenes = set(mod_entry.character.id for mod_entry in mods if mod_entry.mod.type ==
                                 BD2ModType.CUTSCENE and mod_entry.enabled and mod_entry.character is not None)
        mods_ids_idles = set(mod_entry.character.id for mod_entry in mods if mod_entry.mod.type ==
                             BD2ModType.IDLE and mod_entry.enabled and mod_entry.character is not None)
        mods_ids_dating = set(mod_entry.character.id for mod_entry in mods if mod_entry.mod.type ==
                              BD2ModType.DATING and mod_entry.enabled and mod_entry.character is not None)

        dating_chars = self.game_data.get_dating_characters()

        mods_status = {}

        for character in sorted(self.game_data.get_characters(), key=lambda char: char.character):
            group = character.character
            mods_status.setdefault(group, []).append({
                "character": character,
                "cutscene": character.id in mods_ids_cutscenes,
                "idle": character.id in mods_ids_idles,
                "dating": character.id in mods_ids_dating if character in dating_chars else None
            })

        return mods_status

    def add_mod(
        self,
        *,
        path: Union[str, Path],
        name: Optional[str] = None,
        author: Optional[str] = None,
        enabled: bool = False,
    ) -> BD2ModEntry:
        """Adds a mod to the staging directory from a file or folder path."""
        mod_source = Path(path).resolve()
        
        if not mod_source.exists():
            logger.error("Source mod path does not exist: %s", mod_source)
            raise FileNotFoundError(f"Source mod path does not exist: {mod_source}")

        mod_name = name or mod_source.stem
        staging_mod = self._staging_mods_directory / mod_name
        
        logger.info("Adding mod '%s' from: %s", mod_name, mod_source)
        
        # Check if mod already exists
        if staging_mod.exists():
            logger.error("Mod already exists: %s", mod_name)
            raise ModAlreadyExistsError(mod_name)
        
        if is_compressed_file(mod_source):
            self._install_compressed_mod(mod_source, staging_mod, mod_name)
        else:
            self._install_folder_mod(mod_source, staging_mod, mod_name)

        mod = BD2Mod.from_mod_path(staging_mod)
        
        mod_entry = BD2ModEntry(
            mod=mod,
            path=staging_mod.as_posix(),
            author=author,
            enabled=enabled
        )

        if author:
            self._set_mod_data(mod.name, "author", author)
        
        if enabled:
            self._set_mod_data(mod.name, "enabled", enabled)
        
        logger.info("Successfully added mod '%s'", mod_name)
        
        return mod_entry

    def _install_compressed_mod(self, mod_source: Path, staging_mod: Path, mod_name: str) -> None:
        logger.debug("Extracting compressed mod: %s", mod_source)
        
        with tempfile.TemporaryDirectory() as temp_folder:
            temp_path = Path(temp_folder)
            
            try:
                extract_file(mod_source, temp_folder)
            except ReadError as e:
                raise UnsupportedArchiveFormatError(
                    f"Unsupported archive format for {mod_source.name}: {mod_source.suffix}"
                ) from e
            
            logger.debug("Mod extracted successfully to temporary folder")
            
            # Find and validate mod files
            mod_folder = self._find_valid_modfile(temp_path, mod_source)
            
            # Copy to staging directory
            logger.debug("Copying mod from %s to %s", mod_folder, staging_mod)
            copytree(mod_folder, staging_mod)
            logger.debug("Mod '%s' copied successfully", mod_name)

    def _install_folder_mod(self, mod_source: Path, staging_mod: Path, mod_name: str) -> None:
        if not mod_source.is_dir():
            raise ModInvalidError(f"Path is not a directory: {mod_source}")
        
        mod_folder = self._find_valid_modfile(mod_source, mod_source)

        logger.debug("Copying mod from %s to %s", mod_folder, staging_mod)
        copytree(mod_folder, staging_mod)
        logger.debug("Mod '%s' copied successfully", mod_name)

    def _find_valid_modfile(self, search_path: Path, source_path: Path) -> Path:
        modfiles = list(search_path.rglob("*.modfile"))
        
        if not modfiles:
            raise ModInvalidError(f"No .modfile found in: {source_path}")
        
 
        mod_folders = list(set(modfile.parent for modfile in modfiles))
        
        if len(mod_folders) > 1:
            raise ModInvalidError(
                f"Multiple mod folders found in {source_path}. Please install mods individually."
            )
        
        return mod_folders[0]

    def remove_mod(self, mod: BD2ModEntry) -> None:
        """Remove a mod from staging directory."""
        mod_path = Path(mod.path)
        mod_name = mod.mod.name

        if not mod_path.exists():
            logger.error("Mod folder not found: %s", mod_path)
            raise ModNotFoundError(
                f"Mod folder not found at {mod_path} for mod '{mod_name}'"
            )

        try:
            logger.debug("Removing mod directory: %s", mod_path)
            rmtree(mod_path)
            logger.debug("Mod directory removed successfully: %s", mod_name)
        except PermissionError as error:
            logger.error("Permission denied removing mod '%s': %s", mod_name, error)
            raise PermissionError(f"Permission denied removing mod '{mod_name}'. ") from error
        except FileNotFoundError:
            logger.warning("Mod directory already removed: %s", mod_path)

        logger.debug("Mod %s removed successfully.", mod_name)

        if self._mods_data.pop(mod_name, None):
            logger.debug("Removing mod data for %s", mod_name)
            self._save_mods_data()

    def enable_mod(self, mod: BD2ModEntry) -> None:
        logger.debug("Enabling mod: %s", mod.mod.name)
        self._set_mod_data(mod.mod.name, "enabled", True)

    def bulk_enable_mods(self, mods: list[BD2ModEntry]):
        logger.debug("Bulk enabling %d mods", len(mods))
        self._bulk_set_mod_data([mod_entry.mod.name for mod_entry in mods], "enabled", True)

    def disable_mod(self, mod: BD2ModEntry) -> None:
        logger.debug("Disabling mod: %s", mod.mod.name)
        self._set_mod_data(mod.mod.name, "enabled", False)
    
    def bulk_disable_mods(self, mods: list[BD2ModEntry]):
        logger.debug("Bulk disabling %d mods", len(mods))
        self._bulk_set_mod_data([mod_entry.mod.name for mod_entry in mods], "enabled", False)

    def set_mod_author(self, mod: BD2ModEntry, author: str) -> None:
        logger.debug("Setting author for mod %s to %s", mod.mod.name, author)
        self._set_mod_data(mod.mod.name, "author", author)

    def bulk_set_mod_author(self, mods: list[BD2ModEntry], author: str):
        logger.debug("Bulk setting author for %d mods to %s", len(mods), author)
        self._bulk_set_mod_data([mod_entry.mod.name for mod_entry in mods], "author", author)

    @required_game_path
    def sync_mods(self, symlink: bool = False, recursive: bool = False, progress_callback: Callable = None) -> None:
        if not self.check_game_directory(self._game_directory):
            raise GameDirectoryNotSetError(
                "Game path is not set. Please set the game path first.")

        if not self.is_browndustx_installed():
            raise BrownDustXNotInstalled("BrownDustX is not installed!")

        game_mods_directory = self._game_directory / \
            r"BepInEx\plugins\BrownDustX\mods" / "BD2MM"

        logger.debug("Game mods directory: %s", game_mods_directory)

        if not game_mods_directory.exists():
            logger.debug("Creating game mods directory: %s",
                         game_mods_directory)
            game_mods_directory.mkdir(exist_ok=True, parents=True)

        if symlink and not is_running_as_admin():
            logger.error(
                "Administrator privileges are required to use symlinks.")
            raise AdminRequiredError(
                "Administrator privileges are required to use symlinks.")

        if recursive:
            modfiles = self._staging_mods_directory.rglob("*.modfile")
        else:
            modfiles = self._staging_mods_directory.glob("*/*.modfile")

        mods_folder = [modfile.parent for modfile in modfiles]

        logger.debug("Found %d mod files to sync.", len(mods_folder))

        # Synced mods are installed directly, not inside nested folders.
        ingame_mods_folder = [
            mod_folder for mod_folder in game_mods_directory.iterdir()]

        mods_staging_names = {mod.name for mod in mods_folder}
        mods_ingame_names = {mod.name for mod in ingame_mods_folder}

        current_step = 0

        # if symlink then remove all mods from the bd2mods and create new
        if symlink:
            total_steps = len(mods_folder) + len(mods_ingame_names)
            for mod in mods_ingame_names:
                mod_game_path = game_mods_directory / mod
                if mod_game_path.exists() or mod_game_path.is_symlink():
                    logger.debug(
                        "Removing mod %s from game mods directory: %s", mod, mod_game_path)
                    if mod_game_path.is_symlink():
                        logger.debug(
                            "Removing symlink for mod %s at %s", mod, mod_game_path)
                        mod_game_path.rmdir()
                    else:
                        logger.debug("Removing mod folder %s at %s",
                                     mod, mod_game_path)
                        rmtree(mod_game_path)
                else:
                    logger.debug(
                        "Mod %s not found in game mods directory.", mod)

        # if is copy, then checks if it needs to be copied
        else:
            # Mods present in game but not in staging = should be removed
            mods_to_remove = mods_ingame_names - mods_staging_names
            total_steps = len(mods_to_remove) + \
                len(mods_folder) + len(mods_ingame_names)

            # remove all mods that is not in staging directory
            for mod in mods_to_remove:
                mod_game_path = game_mods_directory / mod
                if mod_game_path.exists() or mod_game_path.is_symlink():
                    logger.debug(
                        "Removing mod %s from game mods directory: %s", mod, mod_game_path)
                    if mod_game_path.is_symlink():
                        logger.debug(
                            "Removing symlink for mod %s at %s", mod, mod_game_path)
                        mod_game_path.rmdir()
                    else:
                        logger.debug("Removing mod folder %s at %s",
                                     mod, mod_game_path)
                        rmtree(mod_game_path)
                else:
                    logger.debug(
                        "Mod %s not found in game mods directory.", mod)

            # remove all symlinks from previous sync
            for mod in mods_ingame_names:
                mod_game_path = game_mods_directory / mod
                if mod_game_path.is_symlink():
                    logger.debug(
                        "Removing mod %s from game mods directory: %s", mod, mod_game_path)
                    if mod_game_path.is_symlink():
                        logger.debug(
                            "Removing symlink for mod %s at %s", mod, mod_game_path)
                        mod_game_path.rmdir()

                current_step += 1
                if progress_callback:
                    progress_callback(current_step, total_steps)

        for mod in mods_folder:
            mod_game_path = game_mods_directory / mod.name
            mod_enabled = self._mods_data.get(
                mod.name, {}).get("enabled", False)

            if mod_enabled:
                logger.debug("mod %s is enabled.", mod.name)

                if not mod_game_path.exists():
                    if symlink:
                        logger.debug(
                            "Creating symlink for mod %s at %s", mod.name, mod_game_path)
                        mod_game_path.symlink_to(
                            mod.resolve(), target_is_directory=True)
                    else:
                        logger.debug(
                            "Copying mod %s to game mods directory: %s", mod.name, mod_game_path
                        )
                        copytree(mod, mod_game_path)
                else:
                    logger.debug("Mod %s already exists at %s",
                                 mod.name, mod_game_path)

                    mod_removed = False
                    if symlink and not mod_game_path.is_symlink():
                        logger.info("Changed to symlink, removing folders...")
                        rmtree(mod_game_path)
                        mod_removed = True
                    elif not symlink and mod_game_path.is_symlink():
                        logger.info("Changed to copy, removing all symlinks")

                        mod_game_path.rmdir()
                        mod_removed = True

                    if mod_removed:
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
                    logger.debug("Removing mod %s at %s",
                                 mod.name, mod_game_path)
                    if mod_game_path.is_symlink():
                        logger.debug(
                            "Removing symlink for mod %s at %s", mod.name, mod_game_path)
                        mod_game_path.rmdir()
                    else:
                        logger.debug("Removing mod folder %s at %s",
                                     mod.name, mod_game_path)
                        rmtree(mod_game_path)
                        
            current_step += 1
            if progress_callback:
                progress_callback(current_step, total_steps)

        logger.debug("Syncing completed")

    @required_game_path
    def unsync_mods(self, progress_callback: Callable = None) -> None:
        game_mods_directory = self._game_directory / \
            r"BepInEx\plugins\BrownDustX\mods" / "BD2MM"

        if not game_mods_directory.exists():
            logger.debug("Game mods directory does not exist: %s",
                         game_mods_directory)
            game_mods_directory.mkdir(parents=True, exist_ok=True)

        logger.debug("Unsyncing mods from game mods directory: %s",
                     game_mods_directory)

        ingame_mods_folder = [
            mod_folder for mod_folder in game_mods_directory.iterdir()]
        mods_ingame_names = {mod.name for mod in ingame_mods_folder}

        current_step = 0
        total_steps = len(mods_ingame_names)
        for mod in mods_ingame_names:
            mod_game_path = game_mods_directory / mod
            if mod_game_path.exists() or mod_game_path.is_symlink():
                logger.debug("Removing mod %s at %s", mod, mod_game_path)
                if mod_game_path.is_symlink():
                    logger.debug(
                        "Removing symlink for mod %s at %s", mod, mod_game_path)
                    mod_game_path.rmdir()
                else:
                    logger.debug("Removing mod folder %s at %s",
                                 mod, mod_game_path)
                    rmtree(mod_game_path)
            else:
                logger.debug("Mod %s not found in game mods directory.", mod)

            if progress_callback:
                progress_callback(current_step, total_steps)
            current_step += 1

    def is_browndustx_installed(self) -> bool:
        if not self._game_directory:
            return False

        return Path(self._game_directory / r"BepInEx\plugins\BrownDustX\lynesth.bd2.browndustx.dll").exists()

    @required_game_path
    def get_browndustx_version(self) -> Optional[str]:
        if not self.is_browndustx_installed():
            raise BrownDustXNotInstalled("BrownDustX not installed.")

        dll_path = Path(self._game_directory /
                        r"BepInEx\plugins\BrownDustX\lynesth.bd2.browndustx.dll")

        pe = pefile.PE(dll_path)

        data = {}

        for entry in pe.FileInfo:
            if isinstance(entry, list):  # if is a list
                for subentry in entry:
                    if hasattr(subentry, 'StringTable'):
                        for st in subentry.StringTable:
                            for key, value in st.entries.items():
                                data[key.decode(
                                    'utf-8', errors='ignore')] = value.decode('utf-8', errors='ignore')
            elif hasattr(entry, 'StringTable'):
                for st in entry.StringTable:
                    for key, value in st.entries.items():
                        data[key.decode('utf-8', errors='ignore')
                             ] = value.decode('utf-8', errors='ignore')

        return data.get("FileVersion", None)

    def rename_mod(self, mod: BD2ModEntry, new_name: str) -> BD2ModEntry:
        """Renames a mod"""

        # check if it has slashes
        if not is_filename_valid(new_name):
            raise InvalidModNameError(
                f"Invalid mod name: {new_name!r}. Mod names must not contain slashes.")

        old_path = Path(mod.path)

        # If a mod is in a folder (recursive) it will stay in the same folder
        new_path = self._staging_mods_directory / \
            old_path.relative_to(
                self._staging_mods_directory).parent / new_name

        if not old_path.exists():
            logger.error("Mod not found: %s", mod.mod.name)
            raise ModNotFoundError(f"Mod not found: {mod.mod.name}")

        if new_path.exists():
            logger.error("A mod with the name already exists: %s", new_name)
            raise ModAlreadyExistsError(
                f"A mod with the name already exists: {new_name}")

        try:
            old_path.rename(new_path)
        except OSError:
            raise InvalidModNameError(f"Invalid mod name: {new_name!r}. Mod names must not contain illegal characters.")

        logger.debug("Mod renamed from %s to %s", mod.mod.name, new_name)

        if mod.mod.name in self._mods_data:
            self._mods_data[new_name] = self._mods_data.pop(mod.mod.name)
            self._save_mods_data()
        
        mod.mod.name = new_name
        
        return mod

    def auto_detect_authors(self, mods: list[BD2ModEntry]):
        authors = load_authors(AUTHORS_CSV)

        if not authors:
            return

        for mod in mods:
            author = get_author_by_folder(authors, mod.path)

            if author and not mod.author:
                if not mod.mod.name in self._mods_data:
                    self._mods_data[mod.mod.name] = {}

                self._mods_data[mod.mod.name]["author"] = author

        self._save_mods_data()

    def get_modfile_data(self, mod: BD2ModEntry) -> Optional[Dict[str, Any]]:
        """Load and parse JSON data from a mod's modfile."""
        
        modfile_path = list(Path(mod.path).rglob("*.modfile"))
                
        if len(modfile_path) == 0:
            return None
        
        modfile_path = modfile_path[0]
            
        try:
            with open(modfile_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Modfile not found: {modfile_path}")
        except PermissionError:
            logger.error(f"Permission denied reading modfile: {modfile_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in modfile {modfile_path}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error reading modfile {modfile_path}: {e}")
        
        return None

    def set_modfile_data(self, mod: BD2ModEntry, data: dict) -> bool:
        """Write JSON data to a mod's modfile."""
        modfile_path = list(Path(mod.path).rglob("*.modfile"))
        
        if len(modfile_path) == 0:
            return False
        
        modfile_path = modfile_path[0]
        
        try:
            with open(modfile_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                
            logger.info(f"Successfully wrote modfile: {modfile_path}")
            return True  
        except PermissionError:
            logger.error(f"Permission denied writing to modfile: {modfile_path}")
        except Exception as e:
            logger.error(f"Unexpected error writing modfile {modfile_path}: {e}")
            
        return False