from PySide6.QtCore import QObject, Signal, QThread

from pathlib import Path
from os import startfile

from src.models import ModsModel, ConfigModel
from src.views.mods_view import ModsView
from src.utils.models import BD2ModEntry
from src.utils.errors import ModAlreadyExistsError, InvalidModNameError, ModNotFoundError, GameDirectoryNotSetError, AdminRequiredError



class SyncWorker(QObject):
    started = Signal()
    finished = Signal()
    error = Signal(str)
    progress = Signal(int, int, str)

    def __init__(self, mods_model: ModsModel, symlink: bool = False):
        super().__init__()
        self.mods_model = mods_model
        self.symlink = symlink

    def run(self):
        try:
            self.started.emit()
            self.mods_model.sync_mods(symlink=self.symlink, progress_callback=self.progress.emit)
        except GameDirectoryNotSetError:
            return self.error.emit("Game directory not set.")
        except AdminRequiredError:
            return self.error.emit("You need to run as administrator to use symlinks.")
        except Exception as error:  # to not frozen the app
            return self.error.emit(str(error))

        self.finished.emit()

class UnsyncWorker(QObject):
    started = Signal()
    finished = Signal()
    error = Signal(str)
    progress = Signal(int, int, str)

    def __init__(self, mods_model: ModsModel, symlink: bool = False):
        super().__init__()
        self.mods_model = mods_model
        self.symlink = symlink

    def run(self):
        try:
            self.started.emit()
            self.mods_model.unsync_mods(progress_callback=self.progress.emit)
        except GameDirectoryNotSetError:
            return self.error.emit("Game directory not set.")
        except AdminRequiredError:
            return self.error.emit("You need to run as administrator to use symlinks.")
        except Exception as error:  # to not frozen the app
            return self.error.emit(str(error))

        self.finished.emit()


class ModsController(QObject):
    showToastRequested = Signal(str, str, str, int)
    
    def __init__(self, model: ModsModel, view: ModsView, config_model: ConfigModel):
        super().__init__()
        self.model = model
        self.view = view

        self.config_model = config_model
        
        search_recursively = self.config_model.search_mods_recursively
        self.model.set_recursive_mode(search_recursively)

        # Model Signals
        self.model.modsChanged.connect(self.view.update_mods)  # update view
        
        self.model.onProfileChanged.connect(self.refresh_mods)

        # View Signals
        self.view.modsRefreshRequested.connect(self.refresh_mods)

        self.view.addModRequested.connect(self.add_mod)
        self.view.removeModRequested.connect(self.remove_mod)
        self.view.renameModRequested.connect(self.rename_mod)
        self.view.modsSyncRequested.connect(self.sync_mods)
        self.view.modsUnsyncRequested.connect(self.unsync_mods)
        self.view.editModfileRequested.connect(self.edit_modfile)

        self.view.openModsFolderRequested.connect(self.open_mods_folder)
        self.view.openModFolderRequested.connect(self.open_mod_folder)

        self.view.modStateChanged.connect(self.mod_state_changed)
        self.view.modAuthorChanged.connect(self.mod_author_changed)
        self.view.modModfileChanged.connect(self.mod_modfile_changed)

        self.view.bulkModStateChanged.connect(self.bulk_mod_state_changed)
        self.view.bulkModAuthorChanged.connect(self.bulk_mod_author_changed)

        self.view.launchGameRequested.connect(self.launch_game)

        self.config_model.onGameDirectoryChanged.connect(self.game_directory_changed)
        self.config_model.onModsDirectoryChanged.connect(self.mods_directory_changed)
        
        # when the search_mods_recursively change in .ini file
        self.config_model.onSearchModsRecursivelyChanged.connect(self.search_recursively_changed)

        self.sync_thread = None
        self.sync_worker = None
        self.unsync_thread = None
        self.unsync_worker = None

        self.view.onSwitchProfileRequested.connect(self.model.switch_profile)

        self.refresh_mods()
        
        # self.view.update_profile_combobox(self.model.get_profiles())

    def refresh_mods(self):
        self.model.refresh_mods()
        mods = self.model.get_mods()
        self.view.update_mods(mods)
        self.showToastRequested.emit(None, "Mods Updated!", None, None)

    def mod_state_changed(self, mod: BD2ModEntry, state: bool) -> None:
        return self.model.set_mod_state(mod, state)

    def bulk_mod_state_changed(self, mods: list[BD2ModEntry], state: bool) -> None:
        return self.model.set_bulk_mod_state(mods, state)

    def mod_author_changed(self, mod: BD2ModEntry, author: str) -> None:
        return self.model.set_mod_author(mod, author)

    def bulk_mod_author_changed(self, mods: list[BD2ModEntry], author: str) -> None:
        # there's no error i think
        return self.model.set_bulk_mod_author(mods, author)

    def add_mod(self):
        # make some validation, etc.
        pass

    def remove_mod(self, mod: BD2ModEntry):
        try:
            self.model.remove_mod(mod)
        except ModNotFoundError:
            return self.showToastRequested.emit("Mod Not Found", f"The mod '{mod.mod.name}' could not be found.", "error", 5000)
        except Exception as error:
            return self.showToastRequested.emit("An unexpected error occurred.", f"{str(type(error).__name__)}: {str(error)}", "error", 5000)

        self.showToastRequested.emit("Mod Removed", f"Removed mod: {mod.mod.name}")

        self.refresh_mods()

    def rename_mod(self, mod: BD2ModEntry, new_name: str):
        old_name = mod.mod.name

        try:
            self.model.rename_mod(mod, new_name)
        except ModAlreadyExistsError:
            return self.showToastRequested.emit("Mod Already Exists", f"A mod named '{new_name}' already exists.", "error", 5000)
        except InvalidModNameError:
            return self.showToastRequested.emit("Invalid Mod Name", f"The mod name '{new_name}' is invalid. Please use only letters, numbers, and underscores.", "error", 5000)
        except ModNotFoundError:
            return self.showToastRequested.emit("Mod Not Found", f"The mod '{mod.mod.name}' could not be found.", "error", 5000)
        except Exception as error:
            return self.showToastRequested.emit("An unexpected error occurred.", f"{str(type(error).__name__)}: {str(error)}", "error", 5000)

        self.showToastRequested.emit(
            "Mod Renamed", f"Renamed '{old_name}' to '{new_name}'")

        self.refresh_mods()

    def sync_mods(self):
        confirmation = self.view.show_confirmation_dialog(self.tr("Sync Mods"),
                                                          self.tr("Are you sure you want to sync mods? This will remove all existing mods from game folder and replace them with the enabled ones."))

        if not confirmation:
            return

        self.view.show_progress_modal("Syncing Mods...")

        is_symlink = self.config_model.sync_method == "symlink"
        recursive = self.config_model.search_mods_recursively

        self.view.sync_button.setDisabled(True)

        # Thread and Worker setup
        self.sync_thread = QThread()
        self.sync_worker = SyncWorker(self.model, symlink=is_symlink)
        self.sync_worker.moveToThread(self.sync_thread)

        self.sync_thread.started.connect(self.sync_worker.run)

        self.sync_worker.started.connect(self.view.progress_modal_started)

        self.sync_worker.progress.connect(self.view.update_progress_modal)

        self.sync_worker.finished.connect(self.view.progress_modal_finished)
        self.sync_worker.finished.connect(self.sync_thread.quit)
        self.sync_worker.finished.connect(lambda: self.view.sync_button.setEnabled(True))
        self.sync_worker.finished.connect(self.handle_sync_worker_finished)

        # Delete worker and thread safely after thread finishes
        self.sync_worker.finished.connect(self.sync_worker.deleteLater)
        self.sync_thread.finished.connect(self.sync_thread.deleteLater)

        # Handle errors
        self.sync_worker.error.connect(self.handle_sync_worker_error)
        self.sync_worker.error.connect(lambda: self.view.sync_button.setEnabled(True))
        self.sync_worker.error.connect(self.view.progress_modal_error)
        self.sync_worker.error.connect(self.sync_thread.quit)

        self.sync_thread.start()

    def handle_sync_worker_error(self, error_text: str):
        self.showToastRequested.emit("Error syncing mods.", error_text, "error", 10000)

    def handle_sync_worker_finished(self):
        self.showToastRequested.emit("Success!", text="All mods were successfully synced.", duration=5000)

    def unsync_mods(self):
        confirmation = self.view.show_confirmation_dialog(self.tr("Unsync Mods"),
                                                          self.tr("Are you sure you want to unsync mods? This will remove all mods from the game folder."))

        if not confirmation:
            return
    
        self.view.show_progress_modal("Unsync Mods...")

        is_symlink = self.config_model.sync_method == "symlink"
        recursive = self.config_model.search_mods_recursively

        self.view.unsync_button.setDisabled(True)

        # Thread and Worker setup
        self.unsync_thread = QThread()
        self.unsync_worker = UnsyncWorker(self.model, symlink=is_symlink)
        self.unsync_worker.moveToThread(self.unsync_thread)

        self.unsync_thread.started.connect(self.unsync_worker.run)

        self.unsync_worker.started.connect(self.view.progress_modal_started)

        self.unsync_worker.progress.connect(self.view.update_progress_modal)

        self.unsync_worker.finished.connect(self.view.progress_modal_finished)
        self.unsync_worker.finished.connect(self.unsync_thread.quit)
        self.unsync_worker.finished.connect(lambda: self.view.unsync_button.setEnabled(True))
        self.unsync_worker.finished.connect(self.handle_unsync_worker_finished)

        # Delete worker and thread safely after thread finishes
        self.unsync_worker.finished.connect(self.unsync_worker.deleteLater)
        self.unsync_thread.finished.connect(self.unsync_thread.deleteLater)

        # Handle errors
        self.unsync_worker.error.connect(self.handle_unsync_worker_error)
        self.unsync_worker.error.connect(lambda: self.view.unsync_button.setEnabled(True))
        self.unsync_worker.error.connect(self.view.progress_modal_error)
        self.unsync_worker.error.connect(self.unsync_thread.quit)

        self.unsync_thread.start()
    
    def handle_unsync_worker_error(self, error_text: str):
        self.showToastRequested.emit("Error unsyncing mods.", error_text, "error", 10000)

    def handle_unsync_worker_finished(self):
        self.showToastRequested.emit(
            "Success!", text="All mods were successfully removed.", duration=5000)

    def edit_modfile(self, mod: BD2ModEntry):
        modfile_data = self.model.get_modfile_data(mod) or {}
        self.view.show_modfile_dialog(mod, modfile_data)

    def mod_modfile_changed(self, mod: BD2ModEntry, modfile_data: dict):
        self.model.set_modfile_data(mod, modfile_data)

    def open_mods_folder(self):
        return
        if self.model.game_directory:
            startfile(self.model.staging_mods_directory)

    def open_mod_folder(self, path: str):
        startfile(path)

    def game_directory_changed(self, path: str):
        self.model.set_game_directory(path)

    def mods_directory_changed(self, path: str):
        self.model.set_staging_mods_directory(path)
    
    def search_recursively_changed(self, value: bool):
        print(">>", value)
        self.model.set_recursive_mode(value)
        self.refresh_mods()

    def launch_game(self):
        if not self.model.game_directory:
            return self.showToastRequested.emit(text="Game directory is not set.")

        game_exe = Path(self.model.game_directory) / "BrownDust II.exe"

        if not game_exe.exists():
            return self.showToastRequested.emit(text="Game executable 'BrownDust II.exe' not found in game directory.", type="error")

        startfile(game_exe)
