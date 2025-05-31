from PySide6.QtWidgets import QMainWindow, QStackedWidget

from src.BD2ModManager import BD2ModManager
from src.BD2ModManager.errors import GameNotFoundError

from .pages import HomePage, SelectFolderPage


class MainWindow(QMainWindow):
    def __init__(self, mod_manager: BD2ModManager):
        super().__init__()
        self.setWindowTitle("BrownDust2 Mod Manager")

        self.setGeometry(600, 250, 800, 600)

        self.mod_manager = mod_manager
        game_directory = self.mod_manager.game_directory

        self.main_stacked_widget = QStackedWidget()

        self.select_folder_page = SelectFolderPage(game_directory)
        self.select_folder_page.onGameFolderSelected.connect(self._change_game_folder)

        self.home_page = HomePage(self.mod_manager.get_mods())
        self.home_page.onRefreshMods.connect(self._refresh_mods)
        self.home_page.onAddMod.connect(self._add_mod)
        self.home_page.onModStateChanged.connect(self._enable_or_disable_mod)
        self.home_page.onSyncModsClicked.connect(self._sync_mods)
        self.home_page.onUnsyncModsClicked.connect(self._unsync_mods)

        self.main_stacked_widget.addWidget(self.home_page)
        self.main_stacked_widget.addWidget(self.select_folder_page)

        if game_directory and not self.mod_manager.get_game_directory():
            self.select_folder_page.set_error_text("BrownDust II.exe not found")
            self.main_stacked_widget.setCurrentIndex(1)  # Change to selectFolderPage
        elif not self.mod_manager.game_directory:
            self.main_stacked_widget.setCurrentIndex(1)  # Change to selectFolderPage

        self.setCentralWidget(self.main_stacked_widget)

    def _change_game_folder(self, folder: str):
        try:
            self.mod_manager.set_game_directory(folder)
        except GameNotFoundError:
            self.select_folder_page.set_error_text("BrownDust II.exe not found")
            return

        self.main_stacked_widget.setCurrentIndex(1)

    def _refresh_mods(self):
        mods = self.mod_manager.get_mods()
        self.home_page.mods_widget.load_mods(mods)

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