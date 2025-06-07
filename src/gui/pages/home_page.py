from os import startfile
from pathlib import Path

from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget, QHBoxLayout, QMessageBox, QLabel, QDialog, QPushButton, QProgressBar
from PySide6.QtCore import Qt, Signal, QObject, QThread
from PySide6.QtGui import QIcon

from src.BD2ModManager import BD2ModManager
from src.BD2ModManager.errors import GameNotFoundError, GameDirectoryNotSetError, AdminRequiredError, ModAlreadyExistsError
from src.BD2ModManager.models import BD2ModEntry

from src.gui.config import BD2MMConfigManager

from ..widgets import NavButton
from ..views import CharactersView, SettingsView, ModsView

class SyncWorker(QObject):
    finished = Signal()
    error = Signal(str)
    progress = Signal(int, int)
    
    def __init__(self, mod_manager: BD2ModManager, symlink: bool = False):
        super().__init__()
        self.mod_manager = mod_manager
        self.symlink = symlink

    def run(self):
        try:
            self.mod_manager.sync_mods(symlink=self.symlink, progress_callback=self.progress.emit)
        except GameDirectoryNotSetError:
            return self.error.emit("Game Directory Not Set")
        except AdminRequiredError:
            return self.error.emit("You need to run as administrator to use symlinks.")
        except Exception as error: # not frozen the app
            return self.error.emit(str(error)) 
        self.finished.emit()

class UnsyncWorker(QObject):
    finished = Signal()
    error = Signal(str)
    progress = Signal(int, int)

    def __init__(self, mod_manager: BD2ModManager):
        super().__init__()
        self.mod_manager = mod_manager

    def run(self):
        try:
            self.mod_manager.unsync_mods(progress_callback=self.progress.emit)
        except GameDirectoryNotSetError:
            return self.error.emit("Game Directory Not Set")
        except Exception as error: # not frozen the app
            return self.error.emit(str(error)) 
        self.finished.emit()


class Modal(QDialog):
    def __init__(self, parent, text: str):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setObjectName("progressModal")
        
        self.setMinimumWidth(250)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        label = QLabel(text, self)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        self.progress_bar = QProgressBar(self)
        # self.progress_bar.setRange(0, -1)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)
    
        self.button = QPushButton("Wait", self)
        self.button.clicked.connect(self.accept)
        self.button.setDisabled(True)
        self.button.setObjectName("progressModalButton")
        layout.addWidget(self.button)

    def on_finished(self):
        self.button.setDisabled(False)
        self.button.setText("Done!")
        self.progress_bar.setValue(self.progress_bar.maximum())
    
    def update_progress(self, value: int, max: int):
        self.progress_bar.setMaximum(max)
        self.progress_bar.setValue(value)


class HomePage(QWidget):
    def __init__(self, mod_manager: BD2ModManager, config_manager: BD2MMConfigManager):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.sync_thread = None
        self.sync_worker = None
        self.unsync_thread = None
        self.unsync_worker = None
        
        self.mod_manager = mod_manager
        self.config_manager = config_manager

        self.navigation_bar = QWidget()
        self.navigation_bar.setObjectName("navigationBar")
        self.navigation_bar_layout = QHBoxLayout(self.navigation_bar)
        self.navigation_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.navigation_bar_layout.setSpacing(0)

        self.nav_mods_button = NavButton(self.tr("Mods"))
        self.nav_mods_button.setProperty("active", True)
        self.nav_chars_button = NavButton(self.tr("Characters"))
        self.nav_settings_button = NavButton(self.tr("Settings"))
        self.nav_settings_button.setIcon(QIcon(":/material/settings.svg")) 

        self.navigation_bar_layout.addWidget(self.nav_mods_button, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.navigation_bar_layout.addWidget(self.nav_chars_button, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.navigation_bar_layout.addStretch()
        self.navigation_bar_layout.addWidget(self.nav_settings_button, 0, Qt.AlignmentFlag.AlignRight)

        self.navigation_view = QStackedWidget()

        self.mods_widget = ModsView()
        self.mods_widget.addModRequested.connect(self._add_mod)
        self.mods_widget.modStateChanged.connect(self._enable_or_disable_mod)
        self.mods_widget.modAuthorChanged.connect(self._change_mod_author)
        self.mods_widget.modsRefreshRequested.connect(self._refresh_mods)
        self.mods_widget.modsSyncRequested.connect(self._sync_mods)
        self.mods_widget.modsUnsyncRequested.connect(self._unsync_mods)
        self.mods_widget.openModsFolderRequested.connect(self._open_mods_folder)
        self.mods_widget.openModFolderRequested.connect(self._open_mod_folder)
        self.mods_widget.removeModRequested.connect(self._remove_mod)
        self.mods_widget.renameModRequested.connect(self._rename_mod)
        
        self.mods_widget.bulkModStateChanged.connect(self._bulk_enable_or_disable_mods)
        self.mods_widget.bulkModAuthorChanged.connect(self._bulk_change_author_name)

        self.characters_widget = CharactersView()
        self.characters_widget.refreshCharactersRequested.connect(self._refresh_characters)
        
        self._refresh_mods()
        
        self.settings_widget = SettingsView(config_manager)
        self.settings_widget.findAuthorsClicked.connect(self._find_authors)

        self.navigation_view.addWidget(self.mods_widget)
        self.navigation_view.addWidget(self.characters_widget)
        self.navigation_view.addWidget(self.settings_widget)

        self.nav_mods_button.clicked.connect(
            lambda: (self.navigation_view.setCurrentIndex(0), self._update_navigation_buttons())
        )
        self.nav_chars_button.clicked.connect(
            lambda: (self.navigation_view.setCurrentIndex(1), self._update_navigation_buttons())
        )
        self.nav_settings_button.clicked.connect(
            lambda: (self.navigation_view.setCurrentIndex(2), self._update_navigation_buttons())
        )
        
        layout.addWidget(self.navigation_bar)
        layout.addWidget(self.navigation_view)
    
    def show_error(self, message: str):
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle(self.tr("Error"))
        msg_box.setText(self.tr(message))
        msg_box.exec_()
    
    def retranslateUI(self):
        self.nav_mods_button.setText(self.tr("Mods"))
        self.nav_chars_button.setText(self.tr("Characters"))
        self.nav_settings_button.setText(self.tr("Settings"))
        self.mods_widget.retranslateUI()
        self.characters_widget.retranslateUI()
        self.settings_widget.retranslateUI()
    
    def _update_navigation_buttons(self):
        self.nav_mods_button.setProperty("active", self.navigation_view.currentIndex() == 0)
        self.nav_chars_button.setProperty("active", self.navigation_view.currentIndex() == 1)
        self.nav_settings_button.setProperty("active", self.navigation_view.currentIndex() == 2)

        self.nav_mods_button.style().unpolish(self.nav_mods_button)
        self.nav_mods_button.style().polish(self.nav_mods_button)
        
        self.nav_chars_button.style().unpolish(self.nav_chars_button)
        self.nav_chars_button.style().polish(self.nav_chars_button)

        self.nav_settings_button.style().unpolish(self.nav_settings_button)
        self.nav_settings_button.style().polish(self.nav_settings_button)
    
    def _open_mod_folder(self, path: str):
        # data = item.data(0, Qt.ItemDataRole.UserRole)
        startfile(path)
        
    def _open_mods_folder(self):
        startfile(self.mod_manager.staging_mods_directory)
    
    def _refresh_mods(self):
        if self.config_manager.get("search_mods_recursively", boolean=True, default=False):
            mods = self.mod_manager.get_mods(recursive=True)
            characters = self.mod_manager.get_characters_mod_status(recursive=True)
        else:
            mods = self.mod_manager.get_mods()
            characters = self.mod_manager.get_characters_mod_status()

        self.mods_widget.load_mods(mods)
        self.characters_widget.load_characters(characters)
    
    def _refresh_characters(self):
        if self.config_manager.get("search_mods_recursively", boolean=True, default=False):
            characters = self.mod_manager.get_characters_mod_status(recursive=True)
        else:
            characters = self.mod_manager.get_characters_mod_status()

        self.characters_widget.load_characters(characters)

    def _add_mod(self, filename: str):
        try:
            self.mod_manager.add_mod(path=filename)
        except ModAlreadyExistsError:
            self.show_error(f"Mod with \"{Path(filename).name}\" name already exists.")
    
    def _remove_mod(self, mod: BD2ModEntry):
        self.mod_manager.remove_mod(mod)

    def _enable_or_disable_mod(self, mod: BD2ModEntry, state: bool):
        # discover why it is being called on init
        print("Calling?")
        if state:
            self.mod_manager.enable_mod(mod)
        else:
            self.mod_manager.disable_mod(mod)
        
    def _bulk_enable_or_disable_mods(self, mods: list, state: bool):
        if state:
            self.mod_manager.bulk_enable_mods(mods)
        else:
            self.mod_manager.bulk_disable_mods(mods)
        
        self._refresh_characters()
    
    def _bulk_change_author_name(self, mods, author):
        self.mod_manager.bulk_set_mod_author(mods, author)

    def _sync_mods(self):
        confirmation = QMessageBox.question(
            self,
            self.tr("Sync Mods"),
            self.tr("Are you sure you want to sync mods? This will remove all existing mods from game folder and replace them with the enabled ones."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if confirmation == QMessageBox.StandardButton.Yes:
            modal = Modal(self, self.tr("Syncing Mods..."))
            self.mods_widget.sync_button.setEnabled(False)
            modal.show()
            
            symlink_mode = self.config_manager.sync_method == "symlink"

            # Thread and Worker setup
            self.sync_thread = QThread()
            self.sync_worker = SyncWorker(self.mod_manager, symlink=symlink_mode)
            self.sync_worker.moveToThread(self.sync_thread)

            self.sync_thread.started.connect(self.sync_worker.run)
            self.sync_worker.progress.connect(modal.update_progress)
            self.sync_worker.finished.connect(modal.on_finished)

            self.sync_worker.finished.connect(self.sync_thread.quit)

            # Enable UI elements when done
            self.sync_worker.finished.connect(lambda: self.mods_widget.sync_button.setEnabled(True))

            # Delete worker and thread safely after thread finishes
            self.sync_worker.finished.connect(self.sync_worker.deleteLater)
            self.sync_thread.finished.connect(self.sync_thread.deleteLater)

            # Handle errors
            self.sync_worker.error.connect(self.show_error)
            self.sync_worker.error.connect(modal.on_finished)
            self.sync_worker.error.connect(lambda: self.mods_widget.sync_button.setEnabled(True))
            self.sync_worker.error.connect(self.sync_thread.quit)

            self.sync_thread.start()

            
    def _unsync_mods(self):
        confirmation = QMessageBox.question(
            self,
            self.tr("Unsync Mods"),
            self.tr("Are you sure you want to unsync mods? This will remove all mods from the game folder."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if confirmation == QMessageBox.StandardButton.Yes:
            modal = Modal(self, self.tr("Unsyncing Mods..."))
            self.mods_widget.unsync_button.setEnabled(False)
            modal.show()

            self.unsync_thread = QThread()
            self.unsync_worker = UnsyncWorker(self.mod_manager)
            self.unsync_worker.moveToThread(self.unsync_thread)
            self.unsync_thread.started.connect(self.unsync_worker.run)
            self.unsync_worker.progress.connect(modal.update_progress)
            self.unsync_worker.finished.connect(modal.on_finished)
            self.unsync_worker.finished.connect(self.unsync_thread.quit)
            self.unsync_worker.finished.connect(lambda: self.mods_widget.unsync_button.setEnabled(True))
            self.unsync_worker.finished.connect(self.unsync_thread.deleteLater)
            self.unsync_worker.error.connect(self.show_error)
            self.unsync_worker.error.connect(modal.on_finished)
            self.unsync_worker.error.connect(lambda: self.mods_widget.unsync_button.setEnabled(True))
            self.unsync_worker.error.connect(self.unsync_thread.quit)
            self.unsync_thread.start()

    def _change_mod_author(self, name: str, author: str):
        self.mod_manager.set_mod_author(name, author)
        
    def _rename_mod(self, old_name: str, new_name: str):
        self.mod_manager.rename_mod(old_name, new_name)
        self._refresh_mods()
    
    def _find_authors(self):
        if self.config_manager.get("search_mods_recursively", boolean=True, default=False):
            mods = self.mod_manager.get_mods(recursive=True)
        else:
            mods = self.mod_manager.get_mods()
            
        self.mod_manager.auto_detect_authors(mods)
    
    def set_info_text(self, text: str):
        self.mods_widget.set_info_text(text)
        