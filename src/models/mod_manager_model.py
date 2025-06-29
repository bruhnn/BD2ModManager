from time import sleep
from turtle import update
import winreg
from PySide6.QtCore import QObject, Signal

import logging
from pathlib import Path
from typing import Optional, Set, Union, Any, Callable, Dict, List
import json
import pefile
import shutil
import tempfile
from csv import DictReader

from src.utils import is_running_as_admin
from src.utils.models import BD2Mod, BD2ModEntry, BD2ModType
from src.models.profile_manager_model import ProfileManager
from src.utils.errors import (
    GameDirectoryNotSetError,
    GameNotFoundError,
    ModNotFoundError,
    ModAlreadyExistsError,
    InvalidModNameError,
    BrownDustXNotInstalled,
    AdminRequiredError,
    ModInvalidError,
    UnsupportedArchiveFormatError,
)
from src.services.BD2GameData import BD2GameData
from src.utils.files import (
    are_folders_identical,
    cleanup_empty_parent_dirs,
    is_filename_valid,
    get_folder_hash,
    is_compressed_file,
    extract_file,
    remove_folder,
)

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def require_game_path(function: Callable) -> Callable:
    def wrapper(self, *args, **kwargs) -> Any:
        if self.game_directory is None:
            raise GameDirectoryNotSetError(
                "Game path is not set. Please set the game path first."
            )

        if not self.check_game_directory(self.game_directory):
            raise GameNotFoundError(
                f"Game executable 'BrownDust II.exe' not found in directory: {self.game_directory}"
            )

        return function(self, *args, **kwargs)

    return wrapper


def require_bdx_installed(function: Callable):  # -> Callable[..., Any]:
    def wrapper(self, *args, **kwargs):  # -> Any:
        if not self.is_browndustx_installed():
            raise BrownDustXNotInstalled("BrownDustX is not installed!")

        return function(self, *args, **kwargs)

    return wrapper


BD2MM_MODS_FOLDER = "BD2ModManager"


class ModManagerModel(QObject):
    modsRefreshed = Signal()

    profileListChanged = Signal()

    modAdded = Signal(str)  # mod name
    modRemoved = Signal(str)  # mod name
    modRenamed = Signal(str)  # old name, new name
    modStateChanged = Signal(str, bool)  # mod name, new state

    # A mod's metadata (name, author, version, etc.) was changed.
    modMetadataChanged = Signal(str)  # mod name
    modsBulkMetadataChanged = Signal(list, str)  # [mod name] key
    modsBulkStateChanged = Signal(list)  # list of mod names

    currentProfileChanged = Signal()
    gameDirectoryChanged = Signal(str)
    stagingDirectoryChanged = Signal(str)

    def __init__(
        self,
        game_data: BD2GameData,
        profile_manager: ProfileManager,
        staging_mods_directory: Union[str, Path],
        mods_data_file: Union[str, Path],
        game_directory: Union[str, Path, None] = None,
    ) -> None:
        super().__init__()

        self.game_data = game_data
        self._profile_manager = profile_manager

        self._game_directory = Path(game_directory) if game_directory else None
        self._game_mods_directory = (
            self._game_directory
            / "BepInEx"
            / "plugins"
            / "BrownDustX"
            / "mods"
            / BD2MM_MODS_FOLDER
            if self._game_directory
            else None
        )
        self._staging_mods_directory = Path(staging_mods_directory)
        self._data_file = Path(mods_data_file)

        self._staging_mods_directory.mkdir(parents=True, exist_ok=True)

        self._recursive_mode = False
        self._mods = []

        self._mods_data = self._load_mods_data()

        self._profile_manager.activeProfileChanged.connect(self._on_profile_switched)

    def _on_profile_switched(self) -> None:
        self.currentProfileChanged.emit()

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
                logger.warning(
                    "Data file contains non-dict data (type: %s). Using empty data.",
                    type(data).__name__,
                )
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
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="UTF-8",
                delete=False,
                dir=self._data_file.parent,
                suffix=".tmp",
            ) as tempf:
                json.dump(self._mods_data, tempf, indent=4)
                temp_path = tempf.name

            shutil.move(temp_path, self._data_file)
        except (OSError, IOError) as error:
            return logger.error(
                "Failed to save mods data to %s: %s", self._data_file, error
            )

        logger.debug("Mods data saved successfully to %s", self._data_file)

    def refresh_game_data(self) -> None:
        self.game_data.refresh()

    def set_recursive_mode(self, value: bool) -> None:
        self._recursive_mode = value

    @property
    def game_directory(self) -> Optional[Path]:
        """Returns the game directory if set, otherwise None."""
        return self._game_directory

    @property
    def game_exe_path(self) -> Optional[Path]:
        if self._game_directory is None or not self.check_game_directory(
            self._game_directory
        ):
            return None

        return Path(self._game_directory) / "BrownDust II.exe"

    @property
    def staging_mods_directory(self) -> Path:
        """Returns the path to the staging mods directory."""
        return self._staging_mods_directory

    def check_game_directory(self, path: Path | str) -> bool:
        """Returns True if the path contains the game executable."""

        exe_path = Path(path) / "BrownDust II.exe"

        # logger.debug("Checking for game executable at: %s", exe_path)

        if not exe_path.exists():
            # logger.warning("Game executable not found at %s", exe_path)
            return False

        # logger.debug("Game executable found at: %s", exe_path)

        return True

    def set_game_directory(self, path: Union[str, Path]) -> None:
        """Sets the game directory path."""

        game_directory = Path(path).resolve()

        # Check for BD2 executable
        if not self.check_game_directory(game_directory):
            raise GameNotFoundError(
                f"Game executable 'BrownDust II.exe' not found in directory: {game_directory}"
            )

        self._game_directory = game_directory
        self._game_mods_directory = (
            self._game_directory
            / "BepInEx"
            / "plugins"
            / "BrownDustX"
            / "mods"
            / BD2MM_MODS_FOLDER
        )

        logger.info("Game directory successfully set to: %s", game_directory)

        self.gameDirectoryChanged.emit(str(self._game_directory))

    def set_staging_mods_directory(self, path: Union[str, Path]) -> None:
        """Sets the staging mods directory path."""
        staging_path = Path(path)

        if not staging_path.exists():
            logger.debug(
                "Staging mods directory does not exist. Creating: %s", staging_path
            )
            staging_path.mkdir(parents=True, exist_ok=True)

        self._staging_mods_directory = staging_path

        logger.debug("Staging mods directory set to %s", self._staging_mods_directory)

        self.refresh_mods()

    def _load_mods_from_staging(self) -> List[BD2Mod]:
        """Returns a list of all mods found in the staging mods directory."""
        logger.debug(
            "Getting mods from staging directory: %s (recursive=%s)",
            self._staging_mods_directory,
            self._recursive_mode,
        )

        if self._recursive_mode:
            modfiles = self._staging_mods_directory.rglob("*.modfile")
        else:
            modfiles = self._staging_mods_directory.glob("*/*.modfile")

        mods_folders = [modfile.parent for modfile in modfiles]

        logger.debug("Found %d mod folders.", len(mods_folders))

        mods = []
        for mod_folder in mods_folders:
            mod = BD2Mod.from_mod_path(mod_folder, self._staging_mods_directory)

            # relative_name = str(mod_folder.relative_to(
            #     self._staging_mods_directory))

            # if not relative_name == mod.name:  # is recursive
            #     mod.relative_name = relative_name.replace("/", " / ")

            mods.append(mod)

        logger.debug("Total mods found: %d", len(mods))

        return mods

    def get_mods(self) -> list[BD2ModEntry]:
        profile = self._profile_manager.get_current_profile()

        mods_map = {}

        mods = []
        for mod in self._mods:
            # Author, etc.
            mod_metadata = self._mods_data.get(mod.name, {})
            mod_info = profile.get_mod(mod.name)

            is_enabled = mod_info.enabled if mod_info else False
            # Per-profile data: enabled, etc.

            mod_entry = BD2ModEntry(
                mod=mod, author=mod_metadata.get("author"), enabled=is_enabled
            )

            if (
                mod.type in (BD2ModType.CUTSCENE, BD2ModType.IDLE)
                and mod.character_id is not None
            ):
                mod_entry.character = self.game_data.get_character_by_id(
                    mod.character_id
                )
            elif mod.type == BD2ModType.DATING and mod.dating_id is not None:
                mod_entry.character = self.game_data.get_character_by_dating_id(
                    mod.dating_id
                )
            elif mod.type == BD2ModType.NPC and mod.npc_id is not None:
                mod_entry.npc = self.game_data.get_npc_by_id(mod.npc_id)
            elif mod.type == BD2ModType.SCENE and mod.scene_id is not None:
                mod_entry.scene = self.game_data.get_scene_by_id(mod.scene_id)

            mods.append(mod_entry)

            if mod_entry.character is not None and mod_entry.enabled:
                mods_map.setdefault((mod.type, mod_entry.character.id), []).append(
                    mod_entry
                )

        for items in mods_map.values():
            if len(items) > 1:
                for item in items:
                    item.has_conflict = True

        return mods

    def get_characters_mod_status(self) -> dict:
        """Returns a dictionary with characters and their mod status."""

        logger.debug("Getting character mod status")

        mods_ids_cutscenes = set()
        mods_ids_idles = set()
        mods_ids_dating = set()

        for mod_entry in self.get_mods():
            if not mod_entry.enabled or mod_entry.character is None:
                continue

            if mod_entry.mod.type == BD2ModType.CUTSCENE:
                mods_ids_cutscenes.add(mod_entry.character.id)
            elif mod_entry.mod.type == BD2ModType.IDLE:
                mods_ids_idles.add(mod_entry.character.id)
            elif mod_entry.mod.type == BD2ModType.DATING:
                mods_ids_dating.add(mod_entry.character.id)

        dating_chars = self.game_data.get_dating_characters()
        mods_status = {}

        for character in sorted(
            self.game_data.get_characters(), key=lambda char: char.character
        ):
            group = character.character
            mods_status.setdefault(group, []).append(
                {
                    "character": character,
                    "cutscene": character.id in mods_ids_cutscenes,
                    "idle": character.id in mods_ids_idles,
                    "dating": character.id in mods_ids_dating
                    if character in dating_chars
                    else None,
                }
            )

        return mods_status

    def get_mod_by_name(self, mod_name: str) -> Optional[BD2ModEntry]:
        """Returns a mod entry by its name."""
        for mod in self.get_mods():
            if mod.name == mod_name:
                return mod
        return None

    def refresh_mods(self) -> None:
        self._mods = self._load_mods_from_staging()
        self.modsRefreshed.emit()

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

        mod_entry = BD2ModEntry(mod=mod, author=author, enabled=enabled)

        if author:
            self._set_mod_data(mod.name, "author", author)

        if enabled:
            self._set_mod_data(mod.name, "enabled", enabled)

        logger.info("Successfully added mod '%s'", mod_name)

        self.modsChanged.emit()

        return mod_entry

    def _install_compressed_mod(
        self, mod_source: Path, staging_mod: Path, mod_name: str
    ) -> None:
        logger.debug("Extracting compressed mod: %s", mod_source)

        with tempfile.TemporaryDirectory() as temp_folder:
            temp_path = Path(temp_folder)

            try:
                extract_file(mod_source, temp_folder)
            except shutil.ReadError as e:
                raise UnsupportedArchiveFormatError(
                    f"Unsupported archive format for {mod_source.name}: {mod_source.suffix}"
                ) from e

            logger.debug("Mod extracted successfully to temporary folder.")

            # Find and validate mod files
            mod_folder = self._find_valid_modfile(temp_path, mod_source)

            # Copy to staging directory
            logger.debug("Copying mod from %s to %s", mod_folder, staging_mod)
            shutil.copytree(mod_folder, staging_mod)
            logger.debug("Mod '%s' copied successfully", mod_name)

    def _install_folder_mod(
        self, mod_source: Path, staging_mod: Path, mod_name: str
    ) -> None:
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

    def remove_mod(self, mod_name: str) -> None:
        """Remove a mod from staging directory."""
        mod = self._get_mod_by_name(mod_name)
        mod_path = Path(mod.path)

        if not mod_path.exists():
            logger.error("Mod folder not found: %s", mod_path)
            raise ModNotFoundError(
                f"Mod folder not found at {mod_path} for mod '{mod_name}'"
            )

        try:
            logger.debug("Removing mod directory: %s", mod_path)
            # shutil.rmtree(mod_path)
            logger.debug("Mod directory removed successfully: %s", mod_name)
        except PermissionError as error:
            logger.error("Permission denied removing mod '%s': %s", mod_name, error)
            raise PermissionError(
                f"Permission denied removing mod '{mod_name}'. "
            ) from error
        except FileNotFoundError:
            logger.warning("Mod directory already removed: %s", mod_path)

        logger.debug("Mod %s removed successfully.", mod_name)

        for profile in self._profile_manager.get_profiles():
            if profile.get_mod(mod_name):
                profile.remove_mod(mod_name)
                self._profile_manager.save_profile(profile)

        if self._mods_data.pop(mod_name, None):
            logger.debug("Removing mod data for %s", mod_name)
            self._save_mods_data()

        self.modRemoved.emit(mod_name)

    def _get_mod_by_name(self, mod_name: str) -> BD2ModEntry:
        """Returns a mod entry by its name."""
        mod = next((m for m in self.get_mods() if m.name == mod_name), None)

        if not mod:
            logger.error("Mod not found: %s", mod_name)
            raise ModNotFoundError(f"Mod not found: {mod_name}")

        return mod

    def rename_mod(self, mod_name: str, new_name: str) -> BD2ModEntry:
        """Renames a mod"""

        # check if it has slashes
        if not is_filename_valid(new_name):
            raise InvalidModNameError(
                f"Invalid mod name: {new_name!r}. Mod names must not contain slashes."
            )

        mod = self._get_mod_by_name(mod_name)

        old_name = mod_name
        old_path = Path(mod.path)

        # If a mod is in a folder (recursive) it will stay in the same folder
        new_path = (
            self._staging_mods_directory
            / old_path.relative_to(self._staging_mods_directory).parent
            / new_name
        )

        if not old_path.exists():
            logger.error("Mod not found: %s", mod.name)
            raise ModNotFoundError(f"Mod not found: {mod.name}")

        if new_path.exists():
            logger.error("A mod with the name already exists: %s", new_name)
            raise ModAlreadyExistsError(
                f"A mod with the name already exists: {new_name}"
            )

        try:
            old_path.rename(new_path)
        except OSError as error:
            raise InvalidModNameError(
                f"Invalid mod name: {new_name!r}. Mod names must not contain illegal characters."
            ) from error

        logger.debug("Mod renamed from %s to %s", mod.name, new_name)

        if mod.name in self._mods_data:
            self._mods_data[new_name] = self._mods_data.pop(mod.name)
            self._save_mods_data()

        profile = self._profile_manager.get_current_profile()

        if profile:
            profile.rename_mod(mod.name, new_name)
            self._profile_manager.save_profile(profile)

        mod.mod.name = new_name
        mod.mod.path = str(new_path)

        self.modRenamed.emit(new_name)

        return mod

    def _set_mod_state(self, mod_name: str, state: bool) -> None:
        logger.debug(
            "Changing mod state '%s' from %s to %s",
            mod_name,
            self._get_mod_by_name(mod_name).enabled,
            state,
        )
        self._set_bulk_mod_state([mod_name], state)

    def _set_bulk_mod_state(self, mod_names: list[str], state: bool) -> None:
        """
        Sets the enabled state for a list of mods and persists the change if a profile is active.
        """
        if not mod_names:
            return  # Do nothing if the list is empty

        logger.debug("Changing bulk mod state of %d mods to %s.", len(mod_names), state)

        profile = self._profile_manager.get_current_profile()

        # Process each mod name from the list
        for mod_name in mod_names:
            mod = self._get_mod_by_name(mod_name)

            # If a mod with that name doesn't exist, log it and skip.
            if not mod:
                logger.warning("Mod '%s' not found while setting bulk state.", mod_name)
                continue

            mod.enabled = state

            if profile:
                mod_info = profile.get_mod(mod_name)
                if mod_info is None:
                    # If the mod is not yet tracked in the profile, add it.
                    mod_info = profile.add_mod(mod_name)
                mod_info.enabled = state

        if profile:
            self._profile_manager.save_profile(profile)

        self.modsBulkStateChanged.emit(mod_names)

    def enable_mod(self, mod_name: str) -> None:
        logger.debug(
            "Enabling mod '%s' (Current state: %s)",
            mod_name,
            self._get_mod_by_name(mod_name).enabled,
        )
        self._set_mod_state(mod_name, True)

    def enable_bulk_mods(self, mod_names: list[str]) -> None:
        logger.debug(
            "Bulk enabling %d mods: [%s]", len(mod_names), ", ".join(mod_names)
        )
        self._set_bulk_mod_state(mod_names, True)

    def disable_mod(self, mod_name: str) -> None:
        logger.debug(
            "Disabling mod '%s' (Current state: %s)",
            mod_name,
            self._get_mod_by_name(mod_name).enabled,
        )
        self._set_mod_state(mod_name, False)

    def disable_bulk_mods(self, mod_names: list[str]) -> None:
        logger.debug(
            "Bulk disabling %d mods: [%s]", len(mod_names), ", ".join(mod_names)
        )
        self._set_bulk_mod_state(mod_names, False)

    def _set_bulk_mod_data(self, mod_names: list[str], key: str, value: Any) -> bool:
        logger.debug(
            "Starting bulk update: setting %s = %s for %d mods",
            key,
            value,
            len(mod_names),
        )

        changed_mods = []
        for mod_name in mod_names:
            if mod_name not in self._mods_data:
                self._mods_data[mod_name] = {}

            if self._mods_data[mod_name].get(key) != value:
                self._mods_data[mod_name][key] = value
                changed_mods.append(mod_name)
                logger.debug(
                    "Mod '%s' marked for update: %s = %s", mod_name, key, value
                )

        if not changed_mods:
            logger.debug("Bulk update complete. No actual changes were needed.")
            return False

        logger.debug("Saving profile after changing %d mods.", len(changed_mods))
        self._save_mods_data()

        logger.debug("Emitting modsBulkMetadataChanged signal for key '%s'", key)

        self.modsBulkMetadataChanged.emit(changed_mods, key)

        return True

    def _set_mod_data(self, mod_name: str, key: str, value: Any) -> bool:
        logger.debug("Setting mod data: %s = %s for mod '%s'", key, value, mod_name)
        if mod_name not in self._mods_data:
            self._mods_data[mod_name] = {}
        if self._mods_data[mod_name].get(key) == value:
            logger.debug("No change needed for mod '%s': %s = %s", mod_name, key, value)
            return False
        self._mods_data[mod_name][key] = value
        logger.debug("Mod '%s' updated: %s = %s", mod_name, key, value)
        self._save_mods_data()
        logger.debug("Emitting modMetadataChanged signal for mod '%s'", mod_name)
        self.modMetadataChanged.emit(mod_name)
        return True
        # return self._set_bulk_mod_data([mod_name], key, value)

    def set_mod_author(self, mod_name: str, author: str) -> None:
        logger.debug("Setting author for mod '%s' to '%s'", mod_name, author)
        self._set_mod_data(mod_name, "author", author)
        # self.modMetadataChanged.emit(mod_name)

    def set_bulk_mod_author(self, mod_names: list[str], author: str | None):
        logger.debug(
            "Bulk setting author to '%s' for %d mods: [%s]",
            author,
            len(mod_names),
            ", ".join(mod_names),
        )
        self._set_bulk_mod_data(mod_names, "author", author)

    @require_game_path
    @require_bdx_installed
    def sync_mods(
        self, symlink: bool = False, progress_callback: Optional[Callable] = None, cancel_callback: Optional[Callable] = None
    ) -> None:
        """Sync mods from staging directory to game directory."""

        logger.info("Syncing mods to game mods folder: %s", self._game_mods_directory)

        self._game_mods_directory.mkdir(exist_ok=True, parents=True)

        if symlink and not is_running_as_admin():
            logger.error("Administrator privileges are required to use symlinks.")
            raise AdminRequiredError(
                "Administrator privileges are required to use symlinks."
            )

        # Get mod files and folders in staging mods folder
        try:
            if self._recursive_mode:
                modfiles = list(self._staging_mods_directory.rglob("*.modfile"))
            else:
                modfiles = list(self._staging_mods_directory.glob("*/*.modfile"))
        except (OSError, PermissionError) as e:
            logger.error("Failed to access staging directory: %s", e)
            raise

        # Get existing mods in game directory
        staging_mods = [modfile.parent for modfile in modfiles]

        logger.debug("Found %d mod folders to sync.", len(staging_mods))

        def update_progress(
            text: str, current_step: int = 0, total_steps: int = 0
        ) -> None:
            if progress_callback:
                progress_callback(current_step, total_steps, text)

        if symlink:
            self._sync_mods_symlink(staging_mods, update_progress)
        else:
            self._sync_copy_mode(staging_mods, update_progress)

        logger.debug("Syncing completed.")

    def _sync_mods_symlink(
        self, staging_mods_folders: List[Path], update_progress: Callable
    ) -> None:
        profile = self._profile_manager.get_current_profile()
        if not profile:
            logging.error("Could not get current profile. Aborting sync.")
            return

        staging_mods_by_relpath = {
            mod_path.relative_to(self._staging_mods_directory).as_posix(): mod_path
            for mod_path in staging_mods_folders
        }

        enabled_relpaths = {
            relpath for relpath, mod_path in staging_mods_by_relpath.items()
            if (mod_info := profile.get_mod(relpath)) and mod_info.enabled
        }

        installed_mods = {
            path.relative_to(self._game_mods_directory).as_posix(): path
            for path in self._game_mods_directory.rglob("*")
            if path.is_symlink()
        }
        installed_relpaths = set(installed_mods.keys())

        mods_to_link = enabled_relpaths - installed_relpaths
        mods_to_unlink = installed_relpaths - enabled_relpaths


        for mod_relpath in installed_relpaths & enabled_relpaths:
            installed_path = installed_mods[mod_relpath]
            staging_path = staging_mods_by_relpath[mod_relpath]

            try:
                is_correct_link = installed_path.resolve() == staging_path.resolve()
            except (OSError, FileNotFoundError): # Catches broken links
                is_correct_link = False

            if not is_correct_link:
                logging.warning(
                    "Mod '%s' is an incorrect link or a folder. It will be replaced.", mod_relpath
                )
                mods_to_unlink.add(mod_relpath)
                mods_to_link.add(mod_relpath)

        total_steps = len(mods_to_unlink) + len(mods_to_link)
        current_step = 0
        if total_steps == 0:
            update_progress("Mods are already up to date.", 1, 1)
            return

        for mod_relpath in mods_to_unlink:
            current_step += 1
            update_progress(f"Removing '{mod_relpath}'", current_step, total_steps)
            try:
                mod_game_path = installed_mods[mod_relpath]
                remove_folder(mod_game_path) # remove_folder correctly handles symlinksw
                logging.debug("Removed mod link '%s'.", mod_relpath)
                
                cleanup_empty_parent_dirs(mod_game_path, self._game_mods_directory)
            except Exception as e:
                logging.error("Failed to remove '%s': %s", mod_relpath, e)


        for mod_relpath in mods_to_link:
            current_step += 1
            update_progress(f"Linking '{mod_relpath}'", current_step, total_steps)
            try:
                mod_staging_path = staging_mods_by_relpath[mod_relpath]
                mod_game_path = self._game_mods_directory / mod_relpath

                mod_game_path.parent.mkdir(parents=True, exist_ok=True)
                
                mod_game_path.symlink_to(mod_staging_path, target_is_directory=True)
                logging.debug("Linked mod '%s' to '%s'.", mod_game_path, mod_staging_path)
            except Exception as e:
                logging.error("Failed to link '%s': %s", mod_relpath, e)

        update_progress("Synchronization complete!", total_steps, total_steps)

    def _sync_copy_mode(
        self, staging_mods_folders: list[Path], update_progress: Callable
    ) -> None:
        profile = self._profile_manager.get_current_profile()
        if not profile:
            logging.error("Could not get current profile. Aborting sync.")
            return

        staging_mods_by_id = {
            mod_path.relative_to(self._staging_mods_directory).as_posix(): mod_path
            for mod_path in staging_mods_folders
        }

        enabled_mod_ids = {
            mod_id for mod_id, mod_path in staging_mods_by_id.items()
            if (mod_info := profile.get_mod(mod_id)) and mod_info.enabled
        }

        enabled_mods_by_relpath = {
            mod_id: staging_mods_by_id[mod_id]
            for mod_id in enabled_mod_ids
        }
        
        if len(enabled_mods_by_relpath) != len(enabled_mod_ids):
            logging.warning("Duplicate mod folder names found in staging. Sync may be unpredictable.")

        installed_mods = {
            path.parent.relative_to(self._game_mods_directory).as_posix(): path.parent
            for path in self._game_mods_directory.rglob("*.modfile")
        }

        installed_relpaths = set(installed_mods.keys())
        enabled_relpaths = set(enabled_mods_by_relpath.keys())

        mods_to_remove = installed_relpaths - enabled_relpaths
        mods_to_add = enabled_relpaths - installed_relpaths
        
        mods_to_check = installed_relpaths & enabled_relpaths
        for mod_relpath in mods_to_check:
            update_progress(f"Checking '{mod_relpath}'", 0, 0)
            
            installed_path = installed_mods[mod_relpath]
            staging_path = enabled_mods_by_relpath[mod_relpath]

            if installed_path.is_symlink():
                logger.warning("Mod '%s' is a symlink; will be replaced with a copy.", mod_relpath)
                mods_to_remove.add(mod_relpath)
                mods_to_add.add(mod_relpath)
                continue # Skip to next mod

            if not are_folders_identical(installed_path, staging_path):
                logger.info("Mod '%s' has updates. Staged version is newer.", mod_relpath)
                mods_to_remove.add(mod_relpath)
                mods_to_add.add(mod_relpath) 

        total_steps = len(mods_to_remove) + len(mods_to_add)
        current_step = 0
        if total_steps == 0:
            update_progress("Mods are already up to date.", 1, 1)
            return

        # remove mods that are no longer enabled or need updates.
        for mod_relpath in mods_to_remove:
            current_step += 1
            update_progress(f"Removing '{mod_relpath}'", current_step, total_steps)
            try:

                mod_game_path = installed_mods[mod_relpath]
                remove_folder(mod_game_path)
                logging.debug("Removed mod '%s' from game folder.", mod_relpath)
                cleanup_empty_parent_dirs(mod_game_path, self._game_mods_directory)
            except Exception as e:
                logging.error("Failed to remove '%s': %s", mod_relpath, e)    

        for mod_relpath in mods_to_add:
            current_step += 1
            update_progress(f"Installing '{mod_relpath}'", current_step, total_steps)
            try:
                mod_staging_path = enabled_mods_by_relpath[mod_relpath]
                
                mod_game_path = self._game_mods_directory / mod_relpath
                
                if mod_game_path.exists():
                    # probably failed previously
                    logging.warning(
                        "Mod '%s' already exists in game directory. It will be replaced.",
                        mod_relpath,
                    )
                    remove_folder(mod_game_path)

                mod_game_path.parent.mkdir(parents=True, exist_ok=True)
                
                shutil.copytree(mod_staging_path, mod_game_path)
                logging.debug("Copied folder for '%s' to %s", mod_relpath, mod_game_path)

            except Exception as e:
                logging.error("Failed to copy folder for '%s': %s", mod_relpath, e)

        update_progress("Synchronization complete!", total_steps, total_steps)

    @require_game_path
    def unsync_mods(self, progress_callback: Callable | None = None, cancel_callback: Callable | None = None) -> None:
        if not self._game_mods_directory.exists():
            logging.debug("Game mods directory does not exist. Nothing to unsync.")
            if progress_callback:
                progress_callback(1, 1, "No mods directory to clear.")
            return

        logger.debug("Clearing all content from: %s", self._game_mods_directory)

        try:
            items_to_remove = list(self._game_mods_directory.iterdir())
        except (OSError, PermissionError) as e:
            logger.error("Failed to access game mods directory: %s", e)
            if progress_callback:
                progress_callback(1, 1, f"Error accessing mods directory: {e}")
            raise

        if not items_to_remove:
            logger.debug("Game mods directory is already empty.")
            if progress_callback:
                progress_callback(1, 1, "Mods folder is already empty.")
            return

        total_steps = len(items_to_remove)
        for i, path_to_remove in enumerate(items_to_remove, 1):
            if progress_callback:
                progress_callback(i, total_steps, f"Removing: {path_to_remove.name}")

            try:
                
                remove_folder(path_to_remove)
            except (OSError, PermissionError) as e:
                logger.error("Failed to remove '%s': %s", path_to_remove.name, e)
                if progress_callback:
                    progress_callback(i, total_steps, f"Failed to remove: {path_to_remove.name}")
                continue # Continue

        logger.debug("Unsyncing completed successfully.")
        if progress_callback:
            progress_callback(total_steps, total_steps, "Unsync complete.")

    @property
    def _browndustx_dll_path(self) -> Optional[Path]:
        if not self._game_directory:
            return None
        return (
            self._game_directory
            / r"BepInEx\plugins\BrownDustX\lynesth.bd2.browndustx.dll"
        )

    def is_browndustx_installed(self) -> bool:
        dll_path = self._browndustx_dll_path
        return dll_path.exists() if dll_path else False

    @require_game_path
    def get_browndustx_version(self) -> Optional[str]:
        dll_path = self._browndustx_dll_path

        if not dll_path or not dll_path.exists():
            raise BrownDustXNotInstalled("BrownDustX not installed.")

        pe = pefile.PE(dll_path)
        data = {}

        if hasattr(pe, "FileInfo"):
            for file_info_entry in pe.FileInfo:
                entries_to_process = (
                    file_info_entry
                    if isinstance(file_info_entry, list)
                    else [file_info_entry]
                )
                for entry in entries_to_process:
                    if hasattr(entry, "StringTable"):
                        for st in entry.StringTable:
                            for key, value in st.entries.items():
                                try:
                                    data[key.decode("utf-8")] = value.decode("utf-8")
                                except UnicodeDecodeError:
                                    data[key.decode("latin-1", "ignore")] = (
                                        value.decode("latin-1", "ignore")
                                    )

        return data.get("FileVersion")

    def get_modfile_data(self, mod: BD2ModEntry) -> Optional[Dict[str, Any]]:
        modfile_path = list(Path(mod.path).rglob("*.modfile"))

        if len(modfile_path) == 0:
            return None

        modfile_path = modfile_path[0]

        try:
            with open(modfile_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error("Modfile not found: %s", modfile_path)
        except PermissionError:
            logger.error("Permission denied reading modfile: %s", modfile_path)
        except json.JSONDecodeError as error:
            logger.error("Invalid JSON in modfile %s: %s", modfile_path, error)
        except Exception as error:
            logger.error("Unexpected error reading modfile %s: %s", modfile_path, error)

        return None

    def set_modfile_data(self, mod_name: str, data: dict) -> bool:
        """Write JSON data to a mod's modfile."""
        modfile_path = list(Path(mod_name).rglob("*.modfile"))

        if len(modfile_path) == 0:
            return False

        modfile_path = modfile_path[0]

        try:
            with open(modfile_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            logger.info("Successfully wrote modfile: %s", modfile_path)
            return True
        except PermissionError:
            logger.error("Permission denied writing to modfile: %s", modfile_path)
        except Exception as error:
            logger.error("Unexpected error writing modfile %s: %s", modfile_path, error)

        return False

    def experimental_find_mod_authors(self) -> None | List[BD2ModEntry]:
        if not hasattr(self, "_experimental_authors") or not self._experimental_authors:
            return

        mods = self.get_mods()
          
        _ma = {}
        for mod in mods:
            folder_hash = get_folder_hash(Path(mod.path), False)
            author = self._experimental_authors.get(folder_hash)
        

            mod_author = (
                mod.author.strip() if isinstance(mod.author, str) else mod.author
            )
            
            if author is not None and not mod_author:
                _ma.setdefault(author, []).append(mod.name)
        
        for author, mods in _ma.items():
            self._set_bulk_mod_data(mods, "author", author)

        return mods

    def set_experimental_mod_authors_csv(self, path: str | Path) -> None:
        path = Path(path)

        try:
            with path.open("r", encoding="UTF-8") as file:
                data = DictReader(file, ["author", "hash"])

                authors = {row["hash"]: row["author"] for row in data}
        except Exception:
            return

        self._experimental_authors = authors

    def locate_game(self) -> str | None:
        path = None
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"Software\Neowiz\Browndust2Starter\10000001"
            )
            path, _ = winreg.QueryValueEx(key, "path")
            winreg.CloseKey(key)
        except Exception:
            pass

        return path
