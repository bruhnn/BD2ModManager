from typing import List
from PySide6.QtCore import QObject, Signal, QThread

from os import startfile
from pathlib import Path
import logging
import time

from src.views import ModsView
from src.models import ModManagerModel, ConfigModel
from src.utils.errors import (
    GameNotFoundError,
    ModAlreadyExistsError,
    InvalidModNameError,
    ModNotFoundError,
)
from src.workers import SyncWorker, UnsyncWorker

logger = logging.getLogger(__name__)


class ModManagerController(QObject):
    notificationRequested = Signal(str, str, str, int)
    modPreviewRequested = Signal(str)  # Mod path

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

        search_recursively = self.config_model.search_mods_recursively
        self.model.set_recursive_mode(search_recursively)

        self.sync_thread = None
        self.sync_worker = None
        self.unsync_thread = None
        self.unsync_worker = None

        self.set_browndustx_version()
        self._setup_config_connections()
        self._setup_model_connections()
        self._setup_view_connections()

        self.model.refresh_mods()
        self._update_view_mods()

        end_time = time.time()
        
        logger.info(
            f"ModManagerController initialized in {end_time - start_time:.4f} seconds."
        )
    
    def _setup_config_connections(self) -> None:
        """Config model connections"""
        self.config_model.gameDirectoryChanged.connect(self.game_directory_changed)
        self.config_model.modsDirectoryChanged.connect(self.mods_directory_changed)
        self.config_model.searchModsRecursivelyChanged.connect(
            self.search_recursively_changed
        )

    def _setup_model_connections(self) -> None:
        self.model.currentProfileChanged.connect(self._on_profile_changed)
        self.model.modMetadataChanged.connect(self._on_mod_updated)
        self.model.modsBulkMetadataChanged.connect(self._on_mods_bulk_updated)
        self.model.modsRefreshed.connect(self._update_view_mods)
        self.model.modRemoved.connect(self._on_mod_removed)
        self.model.modAdded.connect(self._on_mod_added)
        self.model.modRenamed.connect(self._on_mod_updated)

    def _setup_view_connections(self) -> None:
        self.view.refreshRequested.connect(self._on_refresh_requested)
        self.view.addModRequested.connect(self.add_mod)
        self.view.removeModRequested.connect(self.remove_mod)
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

    def _on_profile_changed(self) -> None:
        logger.info("Profile changed, syncing view with model")
        self._update_view_mods()

    def _on_mod_updated(self, mod_name: str) -> None:
        logger.info(f"Mod updated: {mod_name}")
        mod = self.model.get_mod_by_name(mod_name)
        if mod:
            show_full_path = self.config_model.include_mod_relative_path
            self.view.update_single_mod(mod, show_full_path)

    def _on_mods_bulk_updated(self, mod_names: List[str]) -> None:
        logger.info(f"Bulk mod update: {len(mod_names)} mods")
        mods = [self.model.get_mod_by_name(name) for name in mod_names]
        valid_mods = [mod for mod in mods if mod]
        if valid_mods:
            show_full_path = self.config_model.include_mod_relative_path
            self.view.update_bulk_mods(valid_mods, show_full_path)

    def _on_refresh_requested(self) -> None:
        logger.info("Manual refresh requested")
        self.model.refresh_mods()  # This will trigger model signals

    def _update_view_mods(self) -> None:
        logger.info("Updating view with new mods")
        mods = self.model.get_mods()
        show_full_path = self.config_model.include_mod_relative_path
        self.view.set_mods(mods, show_full_path)

    def mod_state_changed(self, mod_name: str, state: bool) -> None:
        logger.info(
            f"Changing state of mod '{mod_name}' to {'enabled' if state else 'disabled'}."
        )
        if state:
            self.model.enable_mod(mod_name)  # Model emits modMetadataChanged
        else:
            self.model.disable_mod(mod_name)  # Model emits modMetadataChanged

    def _on_mod_added(self, mod_name: str) -> None:
        mod = self.model.get_mod_by_name(mod_name)
        if mod:
            show_full_path = self.config_model.include_mod_relative_path
            self.view.add_mod_to_view(mod, show_full_path)

    def _on_mod_removed(self, mod_name: str) -> None:
        self.notificationRequested.emit(
            "Mod Removed", f"Removed mod: {mod_name}", "success", 3000
        )
        self.view.remove_mod_from_view(mod_name)

    def mod_bulk_state_changed(self, mod_names: list[str], state: bool) -> None:
        logger.info(
            f"Bulk changing state of {len(mod_names)} mods to {'enabled' if state else 'disabled'}."
        )
        if state:
            self.model.enable_bulk_mods(mod_names)
        else:
            self.model.disable_bulk_mods(mod_names)

    def mod_author_changed(self, mod_name: str, author: str) -> None:
        logger.info(f"Changing author of mod '{mod_name}' to '{author}'.")
        self.model.set_mod_author(mod_name, author)

    def mod_bulk_author_changed(self, mod_names: list[str], author: str) -> None:
        logger.info(f"Bulk changing author of {len(mod_names)} mods to '{author}'.")
        self.model.set_bulk_mod_author(mod_names, author)

    def add_mod(self) -> None:
        logger.info("Add mod requested.")
        self.notificationRequested.emit("Adding", "New mod!", "success", 3000)

    def remove_mod(self, mod_name: str) -> None:
        logger.info(f"Attempting to remove mod: {mod_name}")
        try:
            self.model.remove_mod(mod_name)
        except ModNotFoundError:
            logger.warning(f"Attempted to remove non-existent mod: {mod_name}")
            return self.notificationRequested.emit(
                "Mod Not Found",
                f"The mod '{mod_name}' could not be found.",
                "error",
                5000,
            )
        except Exception as error:
            logger.error(
                f"An unexpected error occurred while removing mod '{mod_name}': {error}",
                exc_info=True,
            )
            return self.notificationRequested.emit(
                "An unexpected error occurred.",
                f"{str(type(error).__name__)}: {str(error)}",
                "error",
                5000,
            )

    def rename_mod(self, mod_name: str, new_name: str) -> None:
        logger.info(f"Attempting to rename mod '{mod_name}' to '{new_name}'.")
        try:
            self.model.rename_mod(mod_name, new_name)
        except ModAlreadyExistsError:
            logger.warning(
                f"Failed to rename mod '{mod_name}' to '{new_name}' because a mod with the new name already exists."
            )
            return self.notificationRequested.emit(
                "Mod Already Exists",
                f"A mod named '{new_name}' already exists.",
                "error",
                5000,
            )
        except InvalidModNameError:
            logger.warning(
                f"Failed to rename mod '{mod_name}' due to invalid new name: '{new_name}'."
            )
            return self.notificationRequested.emit(
                "Invalid Mod Name",
                f"The mod name '{new_name}' is invalid. Please use only letters, numbers, and underscores.",
                "error",
                5000,
            )
        except ModNotFoundError:
            logger.warning(f"Attempted to rename a non-existent mod: {mod_name}")
            return self.notificationRequested.emit(
                "Mod Not Found",
                f"The mod '{mod_name}' could not be found.",
                "error",
                5000,
            )
        except Exception as error:
            logger.error(
                f"An unexpected error occurred while renaming mod '{mod_name}': {error}",
                exc_info=True,
            )
            return self.notificationRequested.emit(
                "An unexpected error occurred.",
                f"{str(type(error).__name__)}: {str(error)}",
                "error",
                5000,
            )

    def sync_mods(self) -> None:
        logger.info("Sync mods requested.")
        confirmation = self.view.show_confirmation_dialog(
            self.tr("Sync Mods"),
            self.tr(
                "Are you sure you want to sync mods? This will remove all existing mods from the game folder and replace them with the enabled ones."
            ),
        )
        if not confirmation:
            logger.info("Sync mods cancelled by user in confirmation dialog.")
            return

       
        self.progress_modal = self.view.create_progress_modal()

        self.view.sync_button.setDisabled(True)
        is_symlink = self.config_model.sync_method == "symlink"

        self.sync_thread = QThread()
        self.sync_worker = SyncWorker(self.model, symlink=is_symlink)
        self.sync_worker.moveToThread(self.sync_thread)

        self.sync_worker.started.connect(self.progress_modal.on_started)
        self.sync_worker.progress.connect(self.progress_modal.update_progress)
        self.sync_worker.finished.connect(self.progress_modal.on_finished)
        self.sync_worker.error.connect(self.progress_modal.on_error)

        # no cancel ):
        # self.progress_modal.cancelled.connect(self.sync_worker.stop)

        self.sync_worker.finished.connect(self._on_sync_complete)
        self.sync_worker.error.connect(self._on_sync_complete)


        self.sync_thread.started.connect(self.sync_worker.run)


        self.sync_thread.start()
        self.progress_modal.exec() 

    def _on_sync_complete(self):
        self.view.sync_button.setEnabled(True)

        if self.sync_worker:
            self.sync_worker.deleteLater()
        if self.sync_thread:
            self.sync_thread.quit()
            self.sync_thread.wait() 
            self.sync_thread.deleteLater()

        self.sync_thread = None
        self.sync_worker = None

    def unsync_mods(self) -> None:
        confirmation = self.view.show_confirmation_dialog(
            self.tr("Unsync Mods"),
            self.tr(
                "Are you sure you want to unsync mods? This will remove all mods from the game folder."
            ),
        )
        if not confirmation:
            logger.info("Unsync mods cancelled by user in confirmation dialog.")
            return

        self.progress_modal = self.view.create_progress_modal()

        self.view.unsync_button.setDisabled(True)
        is_symlink = self.config_model.sync_method == "symlink"

        self.unsync_thread = QThread()
        self.unsync_worker = UnsyncWorker(self.model, symlink=is_symlink)
        self.unsync_worker.moveToThread(self.unsync_thread)

        self.unsync_worker.started.connect(self.progress_modal.on_started)
        self.unsync_worker.progress.connect(self.progress_modal.update_progress)
        self.unsync_worker.finished.connect(self.progress_modal.on_finished)
        self.unsync_worker.error.connect(self.progress_modal.on_error)

        # self.progress_modal.cancelled.connect(self._cancel_unsync)

        self.unsync_worker.finished.connect(self._on_unsync_complete)
        self.unsync_worker.error.connect(self._on_unsync_complete)
        
        self.unsync_thread.started.connect(self.unsync_worker.run)

        self.unsync_thread.start()
        self.progress_modal.exec()

    def _on_unsync_complete(self):
        self.view.unsync_button.setEnabled(True)

        if self.unsync_worker:
            self.unsync_worker.deleteLater()
            
        if self.unsync_thread:
            self.unsync_thread.quit()
            self.unsync_thread.wait()
            self.unsync_thread.deleteLater()

        self.unsync_thread = None
        self.unsync_worker = None

    def edit_modfile(self, mod_name: str) -> None:
        logger.info(f"Editing modfile for mod: {mod_name}")
        modfile_data = self.model.get_modfile_data(mod_name) or {}
        self.view.show_modfile_dialog(mod_name, modfile_data)

    def modfile_edited(self, mod_name: str, modfile_data: dict):
        logger.info(f"Saving edited modfile for mod: {mod_name}")
        self.model.set_modfile_data(mod_name, modfile_data)

    def open_mods_folder(self) -> None:
        logger.info("Request to open mods folder.")
        if self.model.staging_mods_directory is None:
            logger.warning("Mods directory is not set.")
            return

        if Path(self.model.staging_mods_directory).exists():
            logger.info(f"Opening mods folder at: {self.model.staging_mods_directory}")
            startfile(self.model.staging_mods_directory)
        else:
            logger.warning(
                f"Mods directory does not exist: {self.model.staging_mods_directory}"
            )

    def open_mod_folder(self, path: str) -> None:
        logger.info(f"Request to open mod folder at: {path}")
        if Path(path).exists():
            startfile(path)
        else:
            logger.warning(f"Mod folder does not exist: {path}")

    def game_directory_changed(self, path: str) -> None:
        logger.info(f"Game directory changed to: {path}")
        try:
            self.model.set_game_directory(path)
        except GameNotFoundError:
            logger.error(f"Game not found at the specified directory: {path}")
            self.notificationRequested.emit(
                "Error", "Game not found in the specified directory.", "error", 3000
            )

    def mods_directory_changed(self, path: str):
        logger.info(f"Mods directory changed to: {path}")
        self.model.set_staging_mods_directory(path)
        self.model.refresh_mods()

    def search_recursively_changed(self, value: bool):
        logger.info(f"Search recursively setting changed to: {value}")
        self.model.set_recursive_mode(value)
        self.model.refresh_mods()

    def set_browndustx_version(self) -> None:
        logger.info("Setting BrownDustX version info.")
        if self.model.is_browndustx_installed():
            bdx_version = self.model.get_browndustx_version()
            logger.info(f"BrownDustX version found: {bdx_version}")
            self.view.set_info_text(f"BrownDustX {bdx_version}")
        else:
            logger.warning("BrownDustX not found.")
            self.view.set_info_text(self.tr("BrownDustX not installed!"))
