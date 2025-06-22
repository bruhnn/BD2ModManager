from PySide6.QtCore import QObject, Signal

import logging
from pathlib import Path
from typing import Optional, Union, Any, Callable, Dict, List
import json
import pefile
import shutil
import os

from src.utils.paths import DATA_FOLDER, CURRENT_PATH, CHARACTERS_CSV, NPCS_CSV, SCENES_CSV, AUTHORS_CSV, DATINGS_CSV
from src.utils.models import BD2Mod, BD2ModEntry, BD2ModType
from src.utils.errors import GameDirectoryNotSetError, GameNotFoundError, ModNotFoundError, ModAlreadyExistsError, InvalidModNameError, BrownDustXNotInstalled, AdminRequiredError, ModInvalidError
from src.utils.BD2GameData import BD2GameData
from src.utils.files import is_filename_valid, get_folder_hash
from src.utils import is_running_as_admin
from src.services.profiles import ProfileManager, ModInfo

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

class ModsModel(QObject):
    modsChanged = Signal()
    modsStateChanged = Signal()
    
    modAdded = Signal() # mod
    modRemoved = Signal() # mod
    modRenamed = Signal()
    modAuthorChanged = Signal()
    modStateChanged = Signal()
    
    modBulkStateChanged = Signal()
    modBulkAuthorChanged = Signal()

    gameDirectoryChanged = Signal(str)
    stagingModsDirectoryChanged = Signal()

    onProfileChanged = Signal()

    def __init__(self, 
                 game_directory: Optional[Union[str, Path]] = None, 
                 staging_mods_directory: Optional[Union[str, Path]] = None, 
                 data_file: Optional[Union[str, Path]] = None):
        super().__init__()
        
        self.game_data = BD2GameData(CHARACTERS_CSV, DATINGS_CSV, SCENES_CSV, NPCS_CSV)

        self._game_directory = Path(game_directory) if game_directory else None
        self._staging_mods_directory = Path(staging_mods_directory) if staging_mods_directory else CURRENT_PATH / "mods"
        
        self._recursive_mode = False
        
        self.profile_manager = ProfileManager(DATA_FOLDER / "profiles")
        
        self._data_file = Path(data_file) if data_file else DATA_FOLDER / "mods.json"

        if not self._staging_mods_directory.exists():
            self._staging_mods_directory.mkdir()

        if not DATA_FOLDER.exists():
            DATA_FOLDER.mkdir(exist_ok=True)
        
        self._mods = []
        self._mods_data = self._load_mods_data()
    
    def set_recursive_mode(self, value: bool):
        self._recursive_mode = value
    
    def get_profiles(self):
        return self.profile_manager.get_all_profiles()
    
    def switch_profile(self, profile_id: str):
        result = self.profile_manager.switch_profile(profile_id)
        if result:
            self.onProfileChanged.emit()
        return result

    def create_profile(self, profile_name: str, profile_description: str):
        return self.profile_manager.create_profile(profile_name, profile_description)
    
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

    def _set_mod_data(self, mod_name: str, key: str, value: Any, save: bool = True) -> bool:
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

        if save:
            self._save_mods_data()
        
        return True

    def _bulk_set_mod_data(self, mod_names: list[str], key: str, value: Any):
        """Sets the mulitples mod data for a given list of mod names."""
        logger.debug("Starting bulk update: setting %s = %s for %d mods", key, value, len(mod_names))

        for mod_name in mod_names:
            self._set_mod_data(mod_name, key, value, save=False)

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
        
        self.gameDirectoryChanged.emit(self._game_directory.as_posix())

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
    
    def _load_mods(self) -> List[BD2Mod]:
        """Returns a list of all mods found in the staging mods directory."""
        logger.debug("Getting mods from staging directory: %s (recursive=%s)", self._staging_mods_directory, self._recursive_mode)

        if self._recursive_mode:
            modfiles = self._staging_mods_directory.rglob("*.modfile")
        else:
            modfiles = self._staging_mods_directory.glob("*/*.modfile")

        mods_folders = [modfile.parent for modfile in modfiles]

        logger.debug("Found %d mod folders.", len(mods_folders))

        mods = []
        for mod_folder in mods_folders:
            mod = BD2Mod.from_mod_path(mod_folder)
            
            relative_name = mod_folder.relative_to(self._staging_mods_directory).as_posix()

            if not relative_name == mod.name: # is recursive
                mod.relative_name = relative_name.replace("/", " / ")

            mods.append(mod)

        logger.debug("Total mods found: %d", len(mods))

        return mods
    
    def refresh_mods(self) -> None:
        self._mods = self._load_mods()

    def get_mods(self) -> list[BD2ModEntry]:
        profile = self.profile_manager.get_active_profile()

        mods = []
        for mod in self._mods:
            # mod metadata: author, etc.
            mod_metadata = self._mods_data.get(mod.name, {})
            
            # mod profile: enabled, etc.
            mod_info = profile.mods.get(mod.name, ModInfo())
            
            mod_entry = BD2ModEntry(
                mod=mod,
                author=mod_metadata.get("author", None),
                enabled=mod_info.enabled
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
        return mods

    def get_characters_mod_status(self) -> dict:
        """Returns a dictionary with characters and their mod status."""

        logger.debug("Getting character mod status")

        mods = self.get_mods()
        
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
            shutil.copytree(mod_folder, staging_mod)
            logger.debug("Mod '%s' copied successfully", mod_name)

    def _install_folder_mod(self, mod_source: Path, staging_mod: Path, mod_name: str) -> None:
        if not mod_source.is_dir():
            raise ModInvalidError(f"Path is not a directory: {mod_source}")
        
        mod_folder = self._find_valid_modfile(mod_source, mod_source)

        logger.debug("Copying mod from %s to %s", mod_folder, staging_mod)
        shutil.copytree(mod_folder, staging_mod)
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
            shutil.rmtree(mod_path)
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
    
    def set_mod_state(self, mod: BD2ModEntry, state: bool):
        logger.debug(f"Changing {mod.mod.name} from {mod.enabled} state to {state}")
        
        profile = self.profile_manager.get_active_profile()
        
        if mod.name not in profile.mods:
            profile.mods[mod.name] = ModInfo()
        
        profile.mods[mod.name].enabled = state
        
        self.profile_manager.save_profile(profile)
        
        self.modsStateChanged.emit()
    
    def set_bulk_mod_state(self, mods: list[BD2ModEntry], state: bool):
        logger.debug(f"Changing bulking mod state of {len(mods)} mods state to {state}.")
        self._bulk_set_mod_data([mod.mod.name for mod in mods], "enabled", state)
        self.modsStateChanged.emit()

    def enable_mod(self, mod: BD2ModEntry) -> None:
        logger.debug("Enabling mod: %s", mod.mod.name)
        self._profile.set_mod_info(mod.name, "enabled", True)
        # self._set_mod_data(mod.mod.name, "enabled", True)

    def bulk_enable_mods(self, mods: list[BD2ModEntry]):
        logger.debug("Bulk enabling %d mods", len(mods))
        self._bulk_set_mod_data([mod_entry.mod.name for mod_entry in mods], "enabled", True)

    def disable_mod(self, mod: BD2ModEntry) -> None:
        logger.debug("Disabling mod: %s", mod.mod.name)
        self._profile.set_mod_info(mod.name, "enabled", True)
        # self._set_mod_data(mod.mod.name, "enabled", False)
    
    def bulk_disable_mods(self, mods: list[BD2ModEntry]):
        logger.debug("Bulk disabling %d mods", len(mods))
        self._bulk_set_mod_data([mod_entry.mod.name for mod_entry in mods], "enabled", False)

    def set_mod_author(self, mod: BD2ModEntry, author: str) -> None:
        logger.debug("Setting author for mod %s to %s", mod.mod.name, author)
        self._set_mod_data(mod.mod.name, "author", author)

    def set_bulk_mod_author(self, mods: list[BD2ModEntry], author: str):
        logger.debug("Bulk setting author for %d mods to %s", len(mods), author)
        if not author.strip(): # is empty
            author = None
         
        self._bulk_set_mod_data([mod_entry.mod.name for mod_entry in mods], "author", author)
    
    @required_game_path
    def sync_mods(self, symlink=False, progress_callback=None):
        """Sync mods from staging directory to game directory."""
        if self._game_directory is None or not self.check_game_directory(self._game_directory):
            raise GameDirectoryNotSetError("Game path is not set. Please set the game path first.")

        if not self.is_browndustx_installed():
            raise BrownDustXNotInstalled("BrownDustX is not installed!")

        game_mods_directory = self._game_directory / r"BepInEx\plugins\BrownDustX\mods" / "BD2MM"
        logger.debug("Game mods directory: %s", game_mods_directory)

        if not game_mods_directory.exists():
            logger.debug("Creating game mods directory: %s", game_mods_directory)
            game_mods_directory.mkdir(exist_ok=True, parents=True)

        if symlink and not is_running_as_admin():
            logger.error("Administrator privileges are required to use symlinks.")
            raise AdminRequiredError("Administrator privileges are required to use symlinks.")

        # Get mod files and folders
        try:
            if self._recursive_mode:
                modfiles = list(self._staging_mods_directory.rglob("*.modfile"))
            else:
                modfiles = list(self._staging_mods_directory.glob("*/*.modfile"))
        except (OSError, PermissionError) as e:
            logger.error("Failed to access staging directory: %s", e)
            raise

        # Get existing mods in game directory
        mods_folder = [modfile.parent for modfile in modfiles]
        
        try:
            ingame_mods_folder = [mod_folder for mod_folder in game_mods_directory.iterdir() 
                                if mod_folder.is_dir() or mod_folder.is_symlink()]
        except (OSError, PermissionError) as e:
            logger.error("Failed to access game mods directory: %s", e)
            raise
        
        mods_staging_names = {mod.name for mod in mods_folder}
        mods_ingame_names = {mod.name for mod in ingame_mods_folder}
        
        logger.debug("Found %d mod folders to sync.", len(mods_folder))
        logger.debug("Found %d existing mods in game directory.", len(ingame_mods_folder))

        # Calculate total steps for progress tracking
        if symlink:
            total_steps = len(mods_ingame_names) + len(mods_folder)
        else:
            mods_to_remove = mods_ingame_names - mods_staging_names
            total_steps = len(mods_to_remove) + len(mods_ingame_names) + len(mods_folder)

        current_step = 0

        def update_progress(progress_text="Processing..."):
            nonlocal current_step
            current_step += 1
            if progress_callback:
                progress_callback(current_step, total_steps, progress_text)

        def remove_mod_path(mod_game_path, mod_name):
            try:
                if mod_game_path.is_symlink():
                    logger.debug("Removing symlink for mod %s at %s", mod_name, mod_game_path)
                    if os.name == 'nt': 
                        mod_game_path.rmdir()
                    else:
                        mod_game_path.unlink()
                elif mod_game_path.exists():
                    logger.debug("Removing mod folder %s at %s", mod_name, mod_game_path)
                    shutil.rmtree(mod_game_path)
                else:
                    logger.debug("Mod %s not found in game mods directory.", mod_name)
            except (OSError, PermissionError) as e:
                logger.error("Failed to remove mod %s: %s", mod_name, e)
                raise

        if symlink:
            for mod_name in mods_ingame_names:
                mod_game_path = game_mods_directory / mod_name
                logger.debug("Removing mod %s from game mods directory: %s", mod_name, mod_game_path)
                remove_mod_path(mod_game_path, mod_name)
                update_progress(f"Cleaning up existing mod: {mod_name}")
        else:
            mods_to_remove = mods_ingame_names - mods_staging_names
            
            for mod_name in mods_to_remove:
                mod_game_path = game_mods_directory / mod_name
                logger.debug("Removing mod %s from game mods directory: %s", mod_name, mod_game_path)
                remove_mod_path(mod_game_path, mod_name)
                update_progress(f"Removing unused mod: {mod_name}")

            for mod_name in mods_ingame_names:
                mod_game_path = game_mods_directory / mod_name
                if mod_game_path.is_symlink():
                    logger.debug("Removing symlink for mod %s at %s", mod_name, mod_game_path)
                    try:
                        if os.name == 'nt':  # Windows
                            mod_game_path.rmdir()
                        else: 
                            mod_game_path.unlink()
                    except (OSError, PermissionError) as e:
                        logger.error("Failed to remove symlink %s: %s", mod_name, e)
                        raise
                update_progress(f"Cleaning symlinks: {mod_name}")

        for mod in mods_folder:
            mod_game_path = game_mods_directory / mod.name
            mod_enabled = self._mods_data.get(mod.name, {}).get("enabled", False)

            try:
                if mod_enabled:
                    logger.debug("Mod %s is enabled.", mod.name)
                    
                    if not mod_game_path.exists():
                        if symlink:
                            logger.debug("Creating symlink for mod %s at %s", mod.name, mod_game_path)
                            mod_game_path.symlink_to(mod.resolve(), target_is_directory=True)
                        else:
                            logger.debug("Copying mod %s to game mods directory: %s", mod.name, mod_game_path)
                            shutil.copytree(mod, mod_game_path, dirs_exist_ok=True)
                    else:
                        logger.debug("Mod %s already exists at %s", mod.name, mod_game_path.as_posix())
                        
                        mode_changed = False
                        if symlink and not mod_game_path.is_symlink():
                            logger.info("Changed to symlink mode, removing folder for %s", mod.name)
                            shutil.rmtree(mod_game_path)
                            mode_changed = True
                        elif not symlink and mod_game_path.is_symlink():
                            logger.info("Changed to copy mode, removing symlink for %s", mod.name)
                            if os.name == 'nt':
                                mod_game_path.rmdir()
                            else:
                                mod_game_path.unlink()
                            mode_changed = True

                        # Reinstall if mode changed
                        if mode_changed:
                            if symlink:
                                logger.debug("Creating symlink for mod %s at %s", mod.name, mod_game_path)
                                mod_game_path.symlink_to(mod.resolve(), target_is_directory=True)
                            else:
                                logger.debug("Copying mod %s to game mods directory: %s", mod.name, mod_game_path)
                                shutil.copytree(mod, mod_game_path, dirs_exist_ok=True)
                        
                        # Check if mod content has changed (only for copy mode)
                        elif not symlink:
                            try:
                                if not get_folder_hash(mod) == get_folder_hash(mod_game_path):
                                    logger.debug("Mod %s has changed. Updating at %s", mod.name, mod_game_path)
                                    shutil.rmtree(mod_game_path)
                                    shutil.copytree(mod, mod_game_path, dirs_exist_ok=True)
                            except Exception as e:
                                logger.warning("Failed to compare mod hashes for %s: %s. Skipping update.", mod.name, e)

                else:
                    # Remove disabled mod
                    logger.debug("Mod %s is disabled.", mod.name)
                    if mod_game_path.exists() or mod_game_path.is_symlink():
                        logger.debug("Removing disabled mod %s at %s", mod.name, mod_game_path)
                        remove_mod_path(mod_game_path, mod.name)

            except Exception as e:
                logger.error("Failed to process mod %s: %s", mod.name, e)
                update_progress(f"Failed to process mod: {mod.name}")
                continue

            update_progress(f"Processing mod: {mod.name}")

        logger.debug("Syncing completed")

    @required_game_path
    def unsync_mods(self, progress_callback: Callable = None) -> None:
        """Remove all mods from game directory."""
        game_mods_directory = self._game_directory / r"BepInEx\plugins\BrownDustX\mods" / "BD2MM"

        if not game_mods_directory.exists():
            logger.debug("Game mods directory does not exist: %s", game_mods_directory)
            if progress_callback:
                progress_callback(1, 1, "No mods directory found - nothing to unsync")
            return

        logger.debug("Unsyncing mods from game mods directory: %s", game_mods_directory)

        try:
            ingame_mods_folder = [mod_folder for mod_folder in game_mods_directory.iterdir() 
                                if mod_folder.is_dir() or mod_folder.is_symlink()]
        except (OSError, PermissionError) as e:
            logger.error("Failed to access game mods directory: %s", e)
            if progress_callback:
                progress_callback(1, 1, f"Failed to access mods directory: {e}")
            raise

        if not ingame_mods_folder:
            logger.debug("No mods found in game mods directory")
            if progress_callback:
                progress_callback(1, 1, "No mods found.")
            return

        mods_ingame_names = {mod.name for mod in ingame_mods_folder}
        total_steps = len(mods_ingame_names)
        current_step = 0

        for mod_name in mods_ingame_names:
            mod_game_path = game_mods_directory / mod_name
            current_step += 1
            
            try:
                if mod_game_path.is_symlink():
                    logger.debug("Removing symlink for mod %s at %s", mod_name, mod_game_path)
                    if os.name == 'nt':  # Windows
                        mod_game_path.rmdir()
                    else:  # Unix-like systems
                        mod_game_path.unlink()
                    if progress_callback:
                        progress_callback(current_step, total_steps, f"Removed symlink: {mod_name}")
                elif mod_game_path.exists():
                    logger.debug("Removing mod folder %s at %s", mod_name, mod_game_path)
                    shutil.rmtree(mod_game_path)
                    if progress_callback:
                        progress_callback(current_step, total_steps, f"Removed mod folder: {mod_name}")
                else:
                    logger.debug("Mod %s not found in game mods directory.", mod_name)
                    if progress_callback:
                        progress_callback(current_step, total_steps, f"Mod not found: {mod_name}")
            
            except (OSError, PermissionError) as e:
                logger.error("Failed to remove mod %s: %s", mod_name, e)
                if progress_callback:
                    progress_callback(current_step, total_steps, f"Failed to remove: {mod_name}")
                # Continue with other mods instead of raising
                continue

        logger.debug("Unsyncing completed")

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
            raise InvalidModNameError(f"Invalid mod name: {new_name!r}. Mod names must not contain slashes.")

        old_path = Path(mod.path)

        # If a mod is in a folder (recursive) it will stay in the same folder
        new_path = self._staging_mods_directory / \
            old_path.relative_to(self._staging_mods_directory).parent / new_name

        if not old_path.exists():
            logger.error("Mod not found: %s", mod.mod.name)
            raise ModNotFoundError(f"Mod not found: {mod.mod.name}")

        if new_path.exists():
            logger.error("A mod with the name already exists: %s", new_name)
            raise ModAlreadyExistsError(f"A mod with the name already exists: {new_name}")

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
                if mod.mod.name not in self._mods_data:
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
