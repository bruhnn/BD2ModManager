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

        mods = mod_manager.get_mods()
        characters = mod_manager.get_characters_mod_status()

        self.mods_widget = ModsView()
        self.mods_widget.load_mods(mods)
        self.mods_widget.onAddMod.connect(self._add_mod)
        self.mods_widget.onRefreshMods.connect(self._refresh_mods)
        self.mods_widget.onModStateChanged.connect(self._enable_or_disable_mod)
        self.mods_widget.onSyncModsClicked.connect(self._sync_mods)
        self.mods_widget.onUnsyncModsClicked.connect(self._unsync_mods)

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

        layout.addWidget(self.navigation_bar)
        layout.addWidget(self.navigation_view)

    def _refresh_mods(self):
        mods = self.mod_manager.get_mods()
        self.mods_widget.load_mods(mods)

    def _add_mod(self, filename: str):
        self.mod_manager.add_mod(path=filename)

    def _enable_or_disable_mod(self, name: str, state: bool):
        if state:
            self.mod_manager.enable_mod(name)
        else:
            self.mod_manager.disable_mod(name)

    def _sync_mods(self):
        self.mod_manager.sync_mods()

    def _unsync_mods(self):
        self.mod_manager.unsync_mods()
