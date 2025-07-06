import os
import winreg
import logging
from pathlib import Path
from typing import Optional, Union, Any, Callable, Dict, List
import json
import pefile
import shutil
import tempfile
from csv import DictReader

from PySide6.QtCore import QObject, Signal

from src.utils.paths import app_paths
from src.utils import is_running_as_admin
from src.utils.models import BD2Mod, BD2ModEntry, BD2ModType
from src.models.profile_manager_model import ProfileManager
from src.utils.errors import (
    GameDirectoryNotSetError,
    GameNotFoundError,
    ModInstallError,
    ModNotFoundError,
    ModAlreadyExistsError,
    InvalidModNameError,
    BrownDustXNotInstalled,
    AdminRequiredError,
    ModInvalidError,
    UnsupportedArchiveFormatError,
)
from src.services.BD2_game_data import BD2GameData
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
    def wrapper(self, *args, **kwargs):# -> Any:
        if not self.is_browndustx_installed():
            raise BrownDustXNotInstalled("BrownDustX is not installed!")

        return function(self, *args, **kwargs)

    return wrapper


BD2MM_MODS_FOLDER = "BD2MM"


class ModManagerModel(QObject):
    modsRefreshed = Signal()

    profileListChanged = Signal()

    modsAddFailed = Signal(list)
    modsRemoveFailed = Signal(list)

    modsAdded = Signal(list)
    modsRemoved = Signal(list)
    modRenamed = Signal(str, str)  # old name, new name

    # A mod's metadata (name, author, version, etc.) was changed.
    modsMetadataChanged = Signal(list)

    modsStateChanged = Signal(list)  # list of mod names

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
        self._mod_entries: Dict[str, BD2ModEntry] = {}

        self._mods_data = self._load_mods_data()

        self._profile_manager.activeProfileChanged.connect(
            self._on_profile_switched)

    # --- Signals
    def _on_profile_switched(self) -> None:
        self._refresh_mods_state()
        self.currentProfileChanged.emit()

    def _refresh_mods_state(self) -> None:
        profile = self._profile_manager.get_current_profile()

        for mod_name, mod_entry in self._mod_entries.items():
            if profile:
                modinfo = profile.get_mod(mod_name)
                if modinfo:
                    mod_entry.enabled = modinfo.enabled
                else:
                    mod_entry.enabled = False

    # --- Public Methods
    def refresh_mods(self) -> None:
        logger.info("Refreshing mod cache from staging directory...")

        self._mod_entries = {}

        staging_mods = self._load_mods_from_staging()

        profile = self._profile_manager.get_current_profile()

        for mod in staging_mods:
            mod_metadata = self._mods_data.get(mod.name, {})
            mod_entry = BD2ModEntry.create_from_mod(
                mod=mod,
                game_data=self.game_data,
                author=mod_metadata.get("author"),
            )

            if profile:
                modinfo = profile.get_mod(mod.name)
                if modinfo:
                    mod_entry.enabled = modinfo.enabled

            self._mod_entries[mod_entry.name] = mod_entry

        self.modsRefreshed.emit()

    def get_mods(self) -> List[BD2ModEntry]:
        return list(self._mod_entries.values())

    def get_mod_by_name(self, mod_name: str, case_insensitive: bool = False) -> Optional[BD2ModEntry]:
        if not case_insensitive:
            return self._mod_entries.get(mod_name)

        for mname, mentry in self._mod_entries.items():
            if mname.lower() == mod_name.lower():
                return mentry

    def add_mod(self, *, path: Union[str, Path]) -> Optional[BD2ModEntry]:
        mod_entry = self._install_mod(path)
        logger.info("Successfully added mod '%s'", mod_entry.mod.name)
        self.modsAdded.emit([mod_entry.mod.name])
        return mod_entry

    def add_multiple_mods(self, paths: List[Union[str, Path]]) -> None:
        new_entries = []
        failed_mods = []

        logger.info("Starting batch install for %d items.", len(paths))
        for path in paths:
            try:
                entry = self._install_mod(path)
                new_entries.append(entry)
            except Exception as e:
                error_message = f"{e}"
                logger.error(
                    "Failed to process mod from path %s: %s", path, error_message)
                failed_mods.append((str(path), error_message))

        if new_entries:
            for entry in new_entries:
                self._mod_entries[entry.mod.name] = entry

            logger.info(
                "Successfully installed %d mods in a batch.", len(new_entries))
            self.modsAdded.emit([entry.mod.name for entry in new_entries])

        if failed_mods:
            logger.warning(
                "Failed to install %d mod(s) during batch operation.", len(
                    failed_mods)
            )
            self.modsAddFailed.emit(failed_mods)

        if not new_entries and not failed_mods:
            logger.info("No new mods were installed from the provided paths.")

    def remove_mod(self, mod_name: str) -> None:
        """Remove a mod from staging directory."""
        # TODO: remove parents if is empty.
        
        mod_entry = self.get_mod_by_name(mod_name)
        if not mod_entry:
            raise ModNotFoundError(
                f"Cannot remove mod '{mod_name}' because it was not found.")

        mod_path = Path(mod_entry.path)

        if mod_path.exists():
            try:
                logger.debug("Removing mod directory: %s", mod_path)
                shutil.rmtree(mod_path)
                logger.info(
                    "Successfully removed mod directory for '%s'.", mod_name)
            except (PermissionError, OSError) as e:
                logger.error(
                    "A file system error occurred while removing '%s': %s", mod_name, e)
                raise PermissionError(
                    f"Could not delete files for '{mod_name}'. Please check file permissions.") from e

        for profile in self._profile_manager.get_profiles():
            try:
                if profile.get_mod(mod_name):
                    profile.remove_mod(mod_name)
                    self._profile_manager.save_profile(profile)
            except Exception as e:
                logger.critical(
                    "CRITICAL: Mod '%s' was deleted from disk, but failed to update profile '%s'. Manual correction may be needed. Error: %s",
                    mod_name, profile.name, e
                )

        self._mod_entries.pop(mod_name, None)

        if self._mods_data.pop(mod_name, None):
            logger.debug("Removing metadata for '%s'", mod_name)
            self._save_mods_data()

        self.modsRemoved.emit([mod_name])

        logger.info("Successfully removed mod '%s'.", mod_name)

    def remove_multiple_mods(self, mod_names: list[str]) -> None:
        successfully_removed_mods = []
        failed_removals = {}

        for mod_name in mod_names:
            mod_entry = self.get_mod_by_name(mod_name)
            if not mod_entry:
                logger.warning("Cannot remove mod '%s' because it was not found.", mod_name)
                continue

            mod_path = Path(mod_entry.path)

            if mod_path.exists():
                try:
                    logger.debug("Removing mod directory: %s", mod_path)
                    shutil.rmtree(mod_path)
                    successfully_removed_mods.append(mod_name)
                except (PermissionError, OSError) as e:
                    error_msg = f"Could not delete files for '{mod_name}'. Please check file permissions."
                    logger.error("%s Error: %s", error_msg, e)
                    failed_removals[mod_name] = error_msg
            else:
                successfully_removed_mods.append(mod_name)

        if not successfully_removed_mods:
            logger.error("Could not remove any of the specified mods due to errors.")
            return

        for profile in self._profile_manager.get_profiles():
            mods_to_remove_from_profile = [
                mod for mod in successfully_removed_mods if profile.get_mod(mod)
            ]
            if mods_to_remove_from_profile:
                try:
                    for mod_name in mods_to_remove_from_profile:
                        profile.remove_mod(mod_name)
                    self._profile_manager.save_profile(profile)
                except Exception as e:
                    logger.critical(
                        "CRITICAL: Mods %s were deleted, but failed to update profile '%s'. Manual correction may be needed. Error: %s",
                        mods_to_remove_from_profile, profile.name, e
                    )

        metadata_was_changed = False
        for mod_name in successfully_removed_mods:
            self._mod_entries.pop(mod_name, None)
            if self._mods_data.pop(mod_name, None):
                metadata_was_changed = True

        if metadata_was_changed:
            logger.debug("Removing metadata for %d mods.", len(successfully_removed_mods))
            self._save_mods_data()

        self.modsRemoved.emit(successfully_removed_mods)

        logger.info("Completed removal process. Successfully removed %d mods.", len(successfully_removed_mods))
        if failed_removals:
            logger.warning("Failed to remove %d mods: %s", len(failed_removals), list(failed_removals.keys()))

    def rename_mod(self, mod_name: str, new_name: str) -> bool:
        """Renames a mod"""
        
        if not is_filename_valid(new_name):
            raise InvalidModNameError(new_name)

        if mod_name == new_name:
            if Path(mod_name).name == new_name:
                logger.info("New name is identical to the old name. Nothing to do.")
                return False

        mod_entry = self.get_mod_by_name(mod_name)
        if not mod_entry:
            raise ModNotFoundError(mod_name)
        
        old_path = Path(mod_entry.path)
        new_path = old_path.with_name(new_name)
        
        new_full_name = new_path.relative_to(self._staging_mods_directory).as_posix()

        existing_mod = self.get_mod_by_name(new_full_name, case_insensitive=True)

        if existing_mod and mod_entry is not existing_mod:
            raise ModAlreadyExistsError(new_name)

        old_path = Path(mod_entry.path)
        new_path = old_path.with_name(new_name)
        
        # if old_path.resolve().as_posix() == new_path.as_posix(): # a/b == a/B
        #     # check if the cases are different
        #     logger.info("New name is identical to the old name. Nothing to do.")
        #     return False
        
        if str(old_path.parent).lower() == str(new_path.parent).lower():
            if old_path.name == new_path.name:
                logger.info("New name is identical to the old name. Nothing to do.")
                return False        
        try:
            logger.debug("Renaming mod folder from '%s' to '%s'", old_path, new_path)
            old_path.rename(new_path)
        except FileExistsError as error:
            raise ModAlreadyExistsError(new_name) from error
        except OSError as e:
            logger.error("Failed to rename mod folder for '%s': %s", mod_name, e)
            raise IOError(f"Could not rename '{mod_name}' to '{new_name}'.") from e

        mod_entry.mod.path = str(new_path)
        mod_entry.mod.name = new_full_name
        mod_entry.mod.display_name = new_path.name

        self._mod_entries.pop(mod_name)
        self._mod_entries[new_full_name] = mod_entry

        if mod_name in self._mods_data:
            self._mods_data[new_full_name] = self._mods_data.pop(mod_name)
            self._save_mods_data()

        for profile in self._profile_manager.get_profiles():
            if profile.has_mod(mod_name):
                profile.rename_mod(mod_name, new_full_name)
                self._profile_manager.save_profile(profile)

        logger.info("Successfully renamed mod '%s' to '%s'.", mod_name, new_full_name)
        
        self.modRenamed.emit(mod_name, new_full_name)

        return True

    def get_characters_mod_status(self) -> dict:
        """Returns a dictionary with characters and their mod status."""
        logger.debug("Getting character mod status")

        mods_ids_cutscenes = set()
        mods_ids_idles = set()
        mods_ids_dating = set()

        for mod_name, mod_entry in self._mod_entries.items():
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
                    if character in dating_chars else None,
                }
            )

        return mods_status

    def enable_mod(self, mod_name: str) -> None:
        mod = self.get_mod_by_name(mod_name)

        if not mod:
            raise ModNotFoundError(mod_name)

        logger.debug(
            "Enabling mod '%s' (Current state: %s)",
            mod_name,
            mod.enabled,
        )

        self._set_mod_state(mod_name, True)

    def enable_bulk_mods(self, mod_names: list[str]) -> None:
        logger.debug(
            "Bulk enabling %d mods: [%s]", len(mod_names), ", ".join(mod_names)
        )
        self._set_bulk_mod_state(mod_names, True)

    def disable_mod(self, mod_name: str) -> None:
        mod = self.get_mod_by_name(mod_name)

        if not mod:
            raise ModNotFoundError(mod_name)

        logger.debug(
            "Disabling mod '%s' (Current state: %s)",
            mod_name,
            mod.enabled,
        )

        self._set_mod_state(mod_name, False)

    def disable_bulk_mods(self, mod_names: list[str]) -> None:
        logger.debug(
            "Bulk disabling %d mods: [%s]", len(
                mod_names), ", ".join(mod_names)
        )
        self._set_bulk_mod_state(mod_names, False)

    def set_mod_author(self, mod_name: str, author: str) -> None:
        logger.debug("Setting author for mod '%s' to '%s'", mod_name, author)
        self._set_mod_data(mod_name, "author", author)

    def set_bulk_mod_author(self, mod_names: list[str], author: str | None):
        logger.debug(
            "Bulk setting author to '%s' for %d mods: [%s]",
            author,
            len(mod_names),
            ", ".join(mod_names),
        )
        self._set_bulk_mod_data(mod_names, "author", author)

    def check_game_directory(self, path: Path | str) -> bool:
        """Returns True if the path contains the game executable."""

        exe_path = Path(path) / "BrownDust II.exe"

        if not exe_path.exists():
            return False

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

        logger.debug("Staging mods directory set to %s",
                     self._staging_mods_directory)

        self.refresh_mods()

    @require_bdx_installed
    @require_game_path
    def sync_mods(
        self, symlink: bool = False, progress_callback: Optional[Callable] = None, cancel_callback: Optional[Callable] = None
    ) -> None:
        """Sync mods from staging directory to game directory."""

        logger.info("Syncing mods to game mods folder: %s",
                    self._game_mods_directory)

        self._game_mods_directory.mkdir(exist_ok=True, parents=True)

        if symlink and not is_running_as_admin():
            logger.error(
                "Administrator privileges are required to use symlinks.")
            raise AdminRequiredError(
                "Administrator privileges are required to use symlinks."
            )

        # Get mod files and folders in staging mods folder
        try:
            if self._recursive_mode:
                modfiles = list(
                    self._staging_mods_directory.rglob("*.modfile"))
            else:
                modfiles = list(
                    self._staging_mods_directory.glob("*/*.modfile"))
        except (OSError, PermissionError) as e:
            logger.error("Failed to access staging directory: %s", e)
            raise

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

    @require_game_path
    def unsync_mods(self, progress_callback: Callable | None = None, cancel_callback: Callable | None = None) -> None:
        if not self._game_mods_directory.exists():
            logger.debug(
                "Game mods directory does not exist. Nothing to unsync.")
            if progress_callback:
                progress_callback(1, 1, "No mods directory to clear.")
            return

        logger.debug("Clearing all content from: %s",
                     self._game_mods_directory)

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
                progress_callback(
                    i, total_steps, f"Removing: {path_to_remove.name}")

            try:

                remove_folder(path_to_remove)
            except (OSError, PermissionError) as e:
                logger.error("Failed to remove '%s': %s",
                             path_to_remove.name, e)
                if progress_callback:
                    progress_callback(
                        i, total_steps, f"Failed to remove: {path_to_remove.name}")
                continue  # Continue

        logger.debug("Unsyncing completed successfully.")
        if progress_callback:
            progress_callback(total_steps, total_steps, "Unsync complete.")

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
                                    data[key.decode("utf-8")
                                         ] = value.decode("utf-8")
                                except UnicodeDecodeError:
                                    data[key.decode("latin-1", "ignore")] = (
                                        value.decode("latin-1", "ignore")
                                    )

        return data.get("FileVersion")

    def get_modfile_data(self, mod_name: str) -> Optional[Dict[str, Any]]:
        mod = self.get_mod_by_name(mod_name)

        if not mod:
            raise ModNotFoundError(mod_name)

        modfile_path = list(Path(mod.path).rglob("*.modfile"))

        if not modfile_path:
            return None

        modfile_path = modfile_path[0]

        data = None

        try:
            with open(modfile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            logger.error("Modfile not found: %s", modfile_path)
        except PermissionError:
            logger.error("Permission denied reading modfile: %s", modfile_path)
        except json.JSONDecodeError as error:
            logger.error("Invalid JSON in modfile %s: %s", modfile_path, error)
        except Exception as error:
            logger.error("Unexpected error reading modfile %s: %s",
                         modfile_path, error)

        return data

    def set_modfile_data(self, mod_name: str, data: dict) -> bool:
        """Write JSON data to a mod's modfile."""
        mod = self.get_mod_by_name(mod_name)
        if not mod:
            raise ModNotFoundError(mod_name)

        modfile_path = list(Path(mod.path).rglob("*.modfile"))

        if not modfile_path:
            return False

        modfile_path = modfile_path[0]

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="UTF-8", dir=mod.path, delete=False) as tempf:
                temp_path = Path(tempf.name)
                json.dump(data, tempf, indent=4, ensure_ascii=False)

            shutil.move(temp_path, modfile_path)

            logger.info("Successfully saved modfile: %s", modfile_path)

            return True
        except PermissionError:
            logger.error(
                "Permission denied writing to modfile: %s", modfile_path)
        except Exception as error:
            logger.error("Unexpected error writing modfile %s: %s",
                         modfile_path, error)
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink(missing_ok=True)

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

    def experimental_migrate_to_profiles(self) -> bool:
        old_mods_json = app_paths.app_path / "mods.json"

        if not old_mods_json.exists():
            return False

        with old_mods_json.open("r", encoding="UTF-8") as f:
            data = json.load(f)

        enabled_mods = [
            mod_name
            for mod_name, data in data.items()
            if data.get("enabled")
        ]

        self._set_bulk_mod_state(enabled_mods, True, False)

        authors = {}

        for mod_name, data in data.items():
            if not data.get("author"):
                continue

            authors.setdefault(data.get("author"), []).append(mod_name)

        for author, mods in authors.items():
            self._set_bulk_mod_data(mods, "author", author, False)

        # update cache
        self.refresh_mods()

        # make backup of the mods.json
        try:
            shutil.move(old_mods_json, app_paths.user_data_path / "old_mods_v2.json")
        except (OSError, PermissionError) as e:
            logger.warning("Could not back up old mods.json file: %s", e)

        return True

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

    def refresh_game_data(self) -> None:
        self.game_data.refresh()

    def set_recursive_mode(self, value: bool) -> None:
        self._recursive_mode = value

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
            mod = BD2Mod.from_mod_path(
                mod_folder, self._staging_mods_directory)
            mods.append(mod)

        logger.debug("Total mods found: %d", len(mods))

        return mods

    def _create_empty_mods_data(self) -> None:
        logger.info("Creating an empty data file.")

        self._data_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with self._data_file.open("w", encoding="UTF-8") as file:
                json.dump({}, file, indent=4)
        except (OSError, IOError) as e:
            logger.error("Failed to create data file %s: %s",
                         self._data_file, e)

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
    def _browndustx_dll_path(self) -> Optional[Path]:
        if not self._game_directory:
            return None
        return (
            self._game_directory
            / r"BepInEx\plugins\BrownDustX\lynesth.bd2.browndustx.dll"
        )

    @property
    def staging_mods_directory(self) -> Path:
        """Returns the path to the staging mods directory."""
        return self._staging_mods_directory

    def _find_valid_modfile(self, search_path: Path, source_path: Path) -> Path:
        modfiles = list(search_path.rglob("*.modfile"))

        if not modfiles:
            raise ModInvalidError(message=f"No .modfile found in: {source_path}")

        mod_folders = list(set(modfile.parent for modfile in modfiles))

        if len(mod_folders) > 1:
            raise ModInvalidError(
                message=f"Multiple mod folders found in {source_path}. Please install mods individually."
            )

        return mod_folders[0]

    def _get_mod_source_folder(self, mod_source: Path) -> Path:
        return self._find_valid_modfile(mod_source, mod_source)

    def _install_mod(self, path: Union[str, Path]) -> BD2ModEntry:
        mod_source = Path(path).resolve()
        if not mod_source.exists():
            raise FileNotFoundError(
                f"Source mod path does not exist: {mod_source}")

        mod_name = mod_source.stem
        staging_mod_path = self._staging_mods_directory / mod_name
        
        # BUG: if there's a folder named without a .modfile, it will not install the mod
        if staging_mod_path.exists():
            if staging_mod_path.is_dir():
                if os.listdir(staging_mod_path):
                    if next(staging_mod_path.rglob("*.modfile"), None):
                        raise ModAlreadyExistsError(mod_name)
                    
                    raise ModInstallError(
                        mod_name=mod_name,
                        message=f"Mod '{mod_name}' cannot be installed because a non-empty directory "
                        f"already exists. Please remove it first."
                    )
                # directory is empty
                else:
                    logger.info(f"Removing existing empty directory at {staging_mod_path}")
                    os.rmdir(staging_mod_path)
            else:
                raise ModInstallError(
                    mod_name=mod_name,
                    message=f"A file exists at mods folder, which prevents the mod "
                    f"'{mod_name}' from being installed. Please remove or rename this file."
                )

        source_to_copy_from = None
        temp_dir = None

        try:
            if is_compressed_file(mod_source):
                temp_dir = tempfile.TemporaryDirectory()
                temp_path = Path(temp_dir.name)

                extract_file(mod_source, temp_path)

                source_to_copy_from = self._get_mod_source_folder(temp_path)

            elif mod_source.is_dir():
                source_to_copy_from = self._get_mod_source_folder(mod_source)
            else:
                raise ModInvalidError(message=f"Source path is not a valid directory or supported archive: {mod_source}")

            shutil.copytree(source_to_copy_from, staging_mod_path)
        finally:
            if temp_dir:
                temp_dir.cleanup()

        mod = BD2Mod.from_mod_path(staging_mod_path, self._staging_mods_directory)
        mod_entry = BD2ModEntry.create_from_mod(mod, self.game_data)
        self._mod_entries[mod_entry.name] = mod_entry

        return mod_entry

    def _set_mod_state(self, mod_name: str, state: bool, trigger_event: bool = True) -> None:
        logger.debug(
            "Changing mod state '%s' from %s to %s",
            mod_name,
            self.get_mod_by_name(mod_name).enabled,
            state,
        )
        self._set_bulk_mod_state([mod_name], state, trigger_event)

    def _set_bulk_mod_state(self, mod_names: list[str], state: bool, trigger_event: bool = True) -> None:
        if not mod_names:
            return  # Do nothing if the list is empty

        logger.debug("Changing bulk mod state of %d mods to %s.",
                     len(mod_names), state)

        profile = self._profile_manager.get_current_profile()

        for mod_name in mod_names:
            mod = self.get_mod_by_name(mod_name)

            if not mod:
                logger.warning(
                    "Mod '%s' not found while setting bulk state.", mod_name)
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

        if trigger_event:
            self.modsStateChanged.emit(mod_names)

    def _set_mod_data(self, mod_name: str, key: str, value: Any, trigger_event: bool = True) -> bool:
        logger.debug("Setting mod data: %s = %s for mod '%s'",
                     key, value, mod_name)
        self._set_bulk_mod_data([mod_name], key, value, trigger_event)
        return True

    def _set_bulk_mod_data(self, mod_names: list[str], key: str, value: Any, trigger_event: bool = True) -> bool:
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

            # update cache
            cached_mod_entry = self._mod_entries.get(mod_name)
            if cached_mod_entry:
                self._mod_entries[mod_name].author = self._mods_data[mod_name].get("author")

        if not changed_mods:
            logger.debug(
                "Bulk update complete. No actual changes were needed.")
            return False

        logger.debug("Saving profile after changing %d mods.", len(changed_mods))

        self._save_mods_data()

        if trigger_event:
            self.modsMetadataChanged.emit(changed_mods)

        return True

    def _sync_mods_symlink(
        self, staging_mods_folders: List[Path], update_progress: Callable
    ) -> None:
        profile = self._profile_manager.get_current_profile()
        if not profile:
            logger.error("Could not get current profile. Aborting sync.")
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
            # if path.is_symlink()
        }

        installed_relpaths = set(installed_mods.keys())

        mods_to_link = enabled_relpaths - installed_relpaths
        mods_to_unlink = installed_relpaths - enabled_relpaths

        for mod_relpath in installed_relpaths & enabled_relpaths:
            installed_path = installed_mods[mod_relpath]
            staging_path = staging_mods_by_relpath[mod_relpath]

            try:
                is_correct_link = installed_path.resolve() == staging_path.resolve()
            except (OSError, FileNotFoundError):  # Catches broken links
                is_correct_link = False

            if not is_correct_link:
                logger.warning(
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
            update_progress(
                f"Removing '{mod_relpath}'", current_step, total_steps)
            try:
                mod_game_path = installed_mods[mod_relpath]

                # remove_folder correctly handles symlinksw
                remove_folder(mod_game_path)
                logger.debug("Removed mod link '%s'.", mod_relpath)

                cleanup_empty_parent_dirs(mod_game_path, self._game_mods_directory)
            except Exception as e:
                logger.error("Failed to remove '%s': %s", mod_relpath, e)

        for mod_relpath in mods_to_link:
            current_step += 1
            update_progress(f"Linking '{mod_relpath}'",
                            current_step, total_steps)
            try:
                mod_staging_path = staging_mods_by_relpath[mod_relpath]
                mod_game_path = self._game_mods_directory / mod_relpath

                mod_game_path.parent.mkdir(parents=True, exist_ok=True)

                mod_game_path.symlink_to(
                    mod_staging_path, target_is_directory=True)
                logger.debug("Linked mod '%s' to '%s'.",
                              mod_game_path, mod_staging_path)
            except Exception as e:
                logger.error("Failed to link '%s': %s", mod_relpath, e)

        update_progress("Synchronization complete!", total_steps, total_steps)

    def _sync_copy_mode(
        self, staging_mods_folders: list[Path], update_progress: Callable
    ) -> None:
        profile = self._profile_manager.get_current_profile()
        if not profile:
            logger.error("Could not get current profile. Aborting sync.")
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
            logger.warning(
                "Duplicate mod folder names found in staging. Sync may be unpredictable.")

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
                logger.warning(
                    "Mod '%s' is a symlink; will be replaced with a copy.", mod_relpath)
                mods_to_remove.add(mod_relpath)
                mods_to_add.add(mod_relpath)
                continue  # Skip to next mod

            if not are_folders_identical(installed_path, staging_path):
                logger.info(
                    "Mod '%s' has updates. Staged version is newer.", mod_relpath)
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
            update_progress(
                f"Removing '{mod_relpath}'", current_step, total_steps)
            try:

                mod_game_path = installed_mods[mod_relpath]
                remove_folder(mod_game_path)
                logger.debug(
                    "Removed mod '%s' from game folder.", mod_relpath)
                cleanup_empty_parent_dirs(
                    mod_game_path, self._game_mods_directory)
            except Exception as e:
                logger.error("Failed to remove '%s': %s", mod_relpath, e)

        for mod_relpath in mods_to_add:
            current_step += 1
            update_progress(
                f"Installing '{mod_relpath}'", current_step, total_steps)
            try:
                mod_staging_path = enabled_mods_by_relpath[mod_relpath]

                mod_game_path = self._game_mods_directory / mod_relpath

                if mod_game_path.exists():
                    # probably failed previously
                    logger.warning(
                        "Mod '%s' already exists in game directory. It will be replaced.",
                        mod_relpath,
                    )
                    remove_folder(mod_game_path)

                mod_game_path.parent.mkdir(parents=True, exist_ok=True)

                shutil.copytree(mod_staging_path, mod_game_path)
                logger.debug("Copied folder for '%s' to %s",
                              mod_relpath, mod_game_path)

            except Exception as e:
                logger.error(
                    "Failed to copy folder for '%s': %s", mod_relpath, e)

        update_progress("Synchronization complete!", total_steps, total_steps)