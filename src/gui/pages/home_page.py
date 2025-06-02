from os import startfile

from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget, QHBoxLayout
from PySide6.QtCore import Qt, Signal

from ..widgets import NavButton
from ..views import CharactersView, SettingsView, ModsView
from ..views import SettingsView, ModsView

from src.BD2ModManager import BD2ModManager
from src.BD2ModManager.errors import GameNotFoundError
from src.gui.config import BD2MMConfigManager


class HomePage(QWidget):
    def __init__(self, mod_manager: BD2ModManager, config_manager: BD2MMConfigManager):
        super().__init__()
        layout = QVBoxLayout(self)
        
        self.mod_manager = mod_manager
        self.config_manager = config_manager

        self.navigation_bar = QWidget()
        self.navigation_bar_layout = QHBoxLayout(self.navigation_bar)
        self.navigation_bar_layout.setContentsMargins(0, 0, 0, 0)

        self.nav_mods_button = NavButton("Mods")
        self.nav_chars_button = NavButton("Characters")
        self.nav_settings_button = NavButton("Settings")

        self.navigation_bar_layout.addWidget(
            self.nav_mods_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.navigation_bar_layout.addWidget(
            self.nav_chars_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.navigation_bar_layout.addStretch()
        self.navigation_bar_layout.addWidget(
        self.nav_settings_button, 0, Qt.AlignmentFlag.AlignRight)

        self.navigation_view = QStackedWidget()

        characters = mod_manager.get_characters_mod_status()

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
        
        self._refresh_mods()

        self.characters_widget = CharactersView(characters)
        
        self.settings_widget = SettingsView(config_manager, mod_manager)

        self.navigation_view.addWidget(self.mods_widget)
        self.navigation_view.addWidget(self.characters_widget)
        self.navigation_view.addWidget(self.settings_widget)

        self.nav_mods_button.clicked.connect(
            lambda: self.navigation_view.setCurrentIndex(0)
        )
        self.nav_chars_button.clicked.connect(
            lambda: self.navigation_view.setCurrentIndex(1)
        )
        self.nav_settings_button.clicked.connect(
            lambda: self.navigation_view.setCurrentIndex(2)
        )
        
        if self.config_manager.get("game_path"):
            try:
                self.mod_manager.set_game_directory(
                    self.config_manager.get("game_path")
                )
            except GameNotFoundError:
                self.mods_widget.set_info_text("Game not found, please set the game path in settings.")

        layout.addWidget(self.navigation_bar)
        layout.addWidget(self.navigation_view)
    
    def _open_mods_folder(self):
        startfile(self.mod_manager.staging_mods_directory)
    
    def _open_mod_folder(self, mod_path: str):
        startfile(mod_path)

    def _refresh_mods(self):
        if self.config_manager.get("search_mods_recursively", boolean=True, default=False):
            mods = self.mod_manager.get_mods(recursive=True)
        else:
            mods = self.mod_manager.get_mods()
        self.mods_widget.load_mods(mods)

    def _add_mod(self, filename: str):
        self.mod_manager.add_mod(path=filename)
    
    def _remove_mod(self, name: str):
        try:
            self.mod_manager.remove_mod(name)
        except GameNotFoundError as e:
            print("a")
            self.mods_widget.set_info_text("Game not found, cannot remove mod.")
            # self.mods_widget.show_error(str(e))

    def _enable_or_disable_mod(self, name: str, state: bool):
        if state:
            self.mod_manager.enable_mod(name)
        else:
            self.mod_manager.disable_mod(name)

    def _sync_mods(self):
        self.mod_manager.sync_mods()

    def _unsync_mods(self):
        self.mod_manager.unsync_mods()

    def _change_mod_author(self, name: str, author: str):
        self.mod_manager.set_mod_author(name, author)