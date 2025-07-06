import time
import logging
from os import startfile
from pathlib import Path
from typing import List

from PySide6.QtCore import QObject, QThread, Signal

from src.models import ConfigModel, ModManagerModel
from src.services import SyncWorker, UnsyncWorker
from src.utils.errors import (ExtractionPasswordError, GameNotFoundError, InvalidModNameError, ModAlreadyExistsError, ModInstallError, ModInvalidError,
                            ModNotFoundError)
from src.views import ModsView

logger = logging.getLogger(__name__)


class ModManagerController(QObject):
    notificationRequested = Signal(str, str, str, int)
    modPreviewRequested = Signal(str)  # Mod name

    def __init__(
        self, model: ModManagerModel, view: ModsView, config_model: ConfigModel
    ) -> None:
        super().__init__()
        start_time = time.time()
        logger.info("Initializing ModManagerController...")

        self.model = model
        self.view = view
        self.config_model = config_model

        self.progress_modal = None
        self._active_thread = None
        self._active_worker = None

        self.model.set_recursive_mode(self.config_model.search_mods_recursively)

        self._setup_config_connections()
        self._setup_model_connections()
        self._setup_view_connections()
        
        self.set_browndustx_version()
        self.model.refresh_mods()

        end_time = time.time()
        logger.info(
            f"ModManagerController initialized in {end_time - start_time:.4f} seconds."
        )

    def _setup_config_connections(self) -> None:
        self.config_model.gameDirectoryChanged.connect(self.game_directory_changed)
        self.config_model.modsDirectoryChanged.connect(self.mods_directory_changed)
        self.config_model.searchModsRecursivelyChanged.connect(self.search_recursively_changed)

    def _setup_model_connections(self) -> None:
        self.model.currentProfileChanged.connect(self._on_profile_changed)
        self.model.modsRefreshed.connect(self._update_view_mods)
        self.model.modsMetadataChanged.connect(self._on_mods_changed)
        self.model.modsStateChanged.connect(self._on_mods_changed)
        self.model.modRenamed.connect(self._on_mod_renamed)
        self.model.modsRemoved.connect(self._on_mods_removed)
        self.model.modsAdded.connect(self._on_mods_added)
        self.model.modsAddFailed.connect(self._on_add_mods_failed)

    def _setup_view_connections(self) -> None:
        self.view.refreshRequested.connect(self._on_refresh_requested)
        self.view.addModsRequested.connect(self.add_mods)
        self.view.removeModRequested.connect(self.remove_mod)
        self.view.removeModsRequested.connect(self.remove_mods)
        self.view.renameModRequested.connect(self.rename_mod)
        self.view.syncRequested.connect(self.sync_mods)
        self.view.unsyncRequested.connect(self.unsync_mods)
        self.view.editModfileRequested.connect(self.edit_modfile)
        self.view.openModsFolderRequested.connect(self.open_mods_folder)
        self.view.openModFolderRequested.connect(self.open_mod_folder)
        self.view.modStateChanged.connect(self.mod_state_changed)
        self.view.modAuthorChanged.connect(self.mod_author_changed)
        self.view.modModfileChanged.connect(self.modfile_edited)
        self.view.modBulkStateChanged.connect(self.mod_bulk_state_changed)
        self.view.modBulkAuthorChanged.connect(self.mod_bulk_author_changed)
        self.view.modPreviewRequested.connect(self.modPreviewRequested.emit)

    # --- Public API (Slots for View Signals) ---

    def _on_refresh_requested(self) -> None:
        logger.info("Manual refresh requested by view.")
        self.model.refresh_mods()

    def add_mods(self, paths: list[str]) -> None:
        logger.info(f"Add mods requested for {len(paths)} path(s).")
        
        if len(paths) == 1:
            try:
                self.model.add_mod(path=paths[0])
            except ModAlreadyExistsError as error:
                logger.warning("Attempted to add a mod that already exists: %s", error)
                self.notificationRequested.emit(
                    "Mod Already Exists",
                    str(error),
                    "warning",
                    4000
                )

            except ModInvalidError as error:
                logger.error("Failed to add invalid mod: %s", error)
                self.notificationRequested.emit(
                    "Invalid Mod",
                    str(error),
                    "error",
                    5000
                )

            except FileNotFoundError as error:
                logger.error("File not found during add_mod: %s", error)
                self.notificationRequested.emit(
                    "File Not Found",
                    "The selected folder could not be found. It may have been moved or deleted.",
                    "error",
                    5000
                )
            
            except ModInstallError as error:
                logger.exception(f"Failed to install mod '{error.mod_name}'.")
                self.notificationRequested.emit(
                    f"Error Installing '{error.mod_name}'",
                    str(error), 
                    "error",
                    5000
                )
            
            except ExtractionPasswordError as error: # Password required if zip?
                logger.error("An error occured when adding mod: %s", error)
                self.notificationRequested.emit(
                    "Extraction Failed",
                    "The mod requires a password. Extract it manually before installing.",
                    "error",
                    5000
                )

            except Exception as error:
                logger.critical("An unexpected error occurred while adding a mod: %s", error, exc_info=True)
                self.notificationRequested.emit(
                    "Unexpected Error",
                    "An unknown error occurred. Please check the logs for details.",
                    "error",
                    5000
                )
        elif len(paths) > 1:
            self.model.add_multiple_mods(paths=paths)

    def remove_mod(self, mod_name: str) -> None:
        logger.info(f"Attempting to remove mod: {mod_name}")
        try:
            self.model.remove_mod(mod_name)
        except ModNotFoundError as error:
            logger.warning(f"Could not remove mod: {error}")
            self.notificationRequested.emit("Mod Not Found", str(error), "error", 5000)
        except Exception as error:
            logger.error(f"An unexpected error occurred while removing mod '{mod_name}': {error}", exc_info=True)
            self.notificationRequested.emit("Error", f"Could not remove mod: {error}", "error", 5000)
    
    def remove_mods(self, mod_names: list[str]):
        self.model.remove_multiple_mods(mod_names)
        

    def rename_mod(self, mod_name: str, new_name: str) -> None:
        logger.info(f"Attempting to rename mod '{mod_name}' to '{new_name}'.")
        
        if mod_name == new_name:
            return self.notificationRequested.emit("No Change Needed", f"The mod is already named '{new_name}'.", "info", 3000)
        
        try:
            if self.model.rename_mod(mod_name, new_name) is False:
                self.notificationRequested.emit("No Change Needed", f"The mod is already named '{new_name}'.", "info", 3000)
        except (ModAlreadyExistsError, InvalidModNameError, ModNotFoundError) as error:
            logger.warning(error)
            self.notificationRequested.emit("Rename Failed", str(error), "error", 5000)
        except Exception as error:
            logger.error(f"An unexpected error occurred while renaming mod '{mod_name}': {error}", exc_info=True)
            self.notificationRequested.emit("Error", f"Could not rename mod: {error}", "error", 5000)

    def mod_state_changed(self, mod_name: str, state: bool) -> None:
        logger.info(f"Changing state of '{mod_name}' to {'enabled' if state else 'disabled'}.")
        self.model.enable_mod(mod_name) if state else self.model.disable_mod(mod_name)

    def mod_bulk_state_changed(self, mod_names: list[str], state: bool) -> None:
        logger.info(f"Bulk changing state of {len(mod_names)} mods to {'enabled' if state else 'disabled'}.")
        self.model.enable_bulk_mods(mod_names) if state else self.model.disable_bulk_mods(mod_names)

    def mod_author_changed(self, mod_name: str, author: str) -> None:
        logger.info(f"Changing author of mod '{mod_name}' to '{author}'.")
        self.model.set_mod_author(mod_name, author)

    def mod_bulk_author_changed(self, mod_names: list[str], author: str) -> None:
        logger.info(f"Bulk changing author of {len(mod_names)} mods to '{author}'.")
        self.model.set_bulk_mod_author(mod_names, author)

    def edit_modfile(self, mod_name: str) -> None:
        logger.info(f"Editing modfile for mod: {mod_name}")
        modfile_data = self.model.get_modfile_data(mod_name) or {}
        self.view.show_modfile_dialog(mod_name, modfile_data)

    def modfile_edited(self, mod_name: str, modfile_data: dict):
        logger.info(f"Saving edited modfile for mod: {mod_name}")
        self.model.set_modfile_data(mod_name, modfile_data)

    def open_mods_folder(self) -> None:
        logger.info("Request to open mods folder.")
        if self.model.staging_mods_directory and self.model.staging_mods_directory.exists():
            startfile(self.model.staging_mods_directory)
        else:
            logger.warning("Mods directory is not set or does not exist.")
            self.notificationRequested.emit("Error", "Mods directory is not set.", "error", 3000)

    def open_mod_folder(self, path: str) -> None:
        mod_path = Path(path)
        logger.info(f"Request to open mod folder at: {mod_path}")
        if mod_path.exists():
            startfile(mod_path)
        else:
            logger.warning(f"Mod folder does not exist: {mod_path}")

    # --- Model Signal
    def _on_profile_changed(self) -> None:
        logger.info("Profile changed. Refreshing the view to display mods for the new profile.")
        self._update_view_mods()

    def _on_mods_added(self, mod_names: list[str]) -> None:
        mods = list(filter(lambda mod: mod is not None, [self.model.get_mod_by_name(mod_name) for mod_name in mod_names]))
                
        if mods:
            self.view.add_mods_to_view(mods, self.config_model.include_mod_relative_path)
            
            if len(mods) > 1:
                self.notificationRequested.emit("Mods Added", f"Added {len(mods)} mods.", "success", 3000)
            else:
                self.notificationRequested.emit("Mod added!", f"Mod \"{mods[0].display_name}\" was added.", "success", 3000)

    def _on_mods_removed(self, mod_names: list[str]) -> None:
        self.view.remove_mods_from_view(mod_names)
        if len(mod_names) > 1:
            self.notificationRequested.emit("Mods Removed", f"Removed {len(mod_names)} mods.", "success", 3000)
        elif mod_names:
            self.notificationRequested.emit("Mod Removed", f"Removed mod: {mod_names[0]}", "success", 3000)
    
    def _on_mod_renamed(self, old_name: str, mod_name: str) -> None:
        self.view.remove_mods_from_view([old_name])
        mod = self.model.get_mod_by_name(mod_name)
        if mod:
            self.view.add_mods_to_view([mod], self.config_model.include_mod_relative_path)

    def _on_mods_changed(self, mod_names: List[str]) -> None:
        mods_to_update = []
        for name in mod_names:
            mod = self.model.get_mod_by_name(name)
            if mod:
                mods_to_update.append(mod)

        if mods_to_update:
            self.view.update_mods(mods_to_update, self.config_model.include_mod_relative_path)

    def _on_add_mods_failed(self, failed_mods: list[str]):
        # self.notificationRequested.emit("Add Mod Error", message, "error", 5000)
        
        title = f"Failed to install {len(failed_mods)} mod(s)"
        
        details = []
        for path, error in failed_mods:
            details.append(f"- {Path(path).name}:\n {error}")
            
        detailed_message = "\n\n".join(details)
    
        self.view.show_error_dialog(title, detailed_message)

    # --- Configuration Handlers

    def game_directory_changed(self, path: str) -> None:
        logger.info(f"Game directory changed to: {path}")
        try:
            self.model.set_game_directory(path)
            self.set_browndustx_version()
        except GameNotFoundError:
            logger.error(f"Game not found at the specified directory: {path}")
            self.notificationRequested.emit("Invalid Game Directory", "The game was not found in the specified directory.", "error", 3000)
    
    def mods_directory_changed(self, path: str):
        logger.info(f"Mods directory changed to: {path}")
        self.model.set_staging_mods_directory(path)

    def search_recursively_changed(self, value: bool):
        logger.info(f"Search recursively setting changed to: {value}")
        self.model.set_recursive_mode(value)
        self.model.refresh_mods()

    # --- Worker/Thread Management

    def sync_mods(self) -> None:
        self._run_worker(
            worker_class=SyncWorker,
            button_to_disable=self.view.sync_button,
            confirmation_title="Sync Mods",
            confirmation_text="Are you sure you want to sync mods? This will replace existing mods in the game folder with the enabled ones."
        )

    def unsync_mods(self) -> None:
        self._run_worker(
            worker_class=UnsyncWorker,
            button_to_disable=self.view.unsync_button,
            confirmation_title="Unsync Mods",
            confirmation_text="Are you sure you want to unsync mods? This will remove all mods from the game folder."
        )

    def _run_worker(self, worker_class, button_to_disable, confirmation_title, confirmation_text):
        if not self.view.show_confirmation_dialog(self.tr(confirmation_title), self.tr(confirmation_text)):
            logger.info(f"{worker_class.__name__} cancelled by user.")
            return

        if self._active_thread is not None:
            logger.warning("A worker process is already running.")
            return

        self.progress_modal = self.view.create_progress_modal()
        
        button_to_disable.setDisabled(True)

        is_symlink = self.config_model.sync_method == "symlink"
        
        self._active_thread = QThread()
        self._active_worker = worker_class(self.model, symlink=is_symlink)
        self._active_worker.moveToThread(self._active_thread)

        self._active_thread.started.connect(self._active_worker.run)
        
        self._active_worker.started.connect(self.progress_modal.on_started)
        self._active_worker.progress.connect(self.progress_modal.update_progress)
        self._active_worker.finished.connect(self.progress_modal.on_finished)
        self._active_worker.error.connect(self.progress_modal.on_error)
        
        self._active_worker.finished.connect(self._active_thread.quit)
        self._active_worker.error.connect(self._active_thread.quit)
        
        self._active_worker.finished.connect(self._active_worker.deleteLater)
        self._active_worker.error.connect(self._active_worker.deleteLater)
        
        self._active_thread.finished.connect(self._active_thread.deleteLater)
        
        self._active_thread.finished.connect(lambda: self._on_worker_complete(button_to_disable))
        
        self._active_thread.start()
        
        self.progress_modal.open()
        
    def _on_worker_complete(self, button_to_enable) -> None:
        if button_to_enable:
            button_to_enable.setEnabled(True)
        
        self._active_thread = None
        self._active_worker = None
        
        logger.info("Worker process has finished and resources are cleaned up.")

    def set_browndustx_version(self) -> None:
        logger.info("Setting BrownDustX version info.")
        if self.model.is_browndustx_installed():
            bdx_version = self.model.get_browndustx_version()
            self.view.set_info_text(f"BrownDustX {bdx_version}")
        else:
            self.view.set_info_text(self.tr("BrownDustX not installed!"))

    def _update_view_mods(self) -> None:
        logger.info("Updating view with all mods from model.")
        mods = self.model.get_mods()
        self.view.set_mods(mods, self.config_model.include_mod_relative_path)