import sys
from pathlib import Path
import requests
from packaging import version

from PySide6.QtWidgets import QMainWindow, QStackedWidget, QApplication
from PySide6.QtCore import QTranslator, Qt, QSettings, QByteArray

from src.BD2ModManager import BD2ModManager
from src.version import __version__
from .pages import HomePage, SelectFolderPage
from .config import BD2MMConfigManager


if getattr(sys, 'frozen', False):
    # If the application is frozen
    app_path = Path(sys._MEIPASS)
else:
    app_path = Path(__file__).parent.parent

STYLES_PATH = app_path / "gui" / "styles"
LANGUAGE_PATH = app_path / "gui" / "translations"



class MainWindow(QMainWindow):
    def __init__(self, mod_manager: BD2ModManager, config_manager: BD2MMConfigManager):
        super().__init__()
        self.setWindowTitle("BD2 Mod Manager - v{version}".format(version=__version__))
        self.setObjectName("mainWindow")
        self.setGeometry(600, 250, 800, 600)
        
        self.settings = QSettings("Bruhnn", "BD2ModManager")
        # self.settings.clear()
        # self.settings.beginGroup("MainWindow")

        self.mod_manager = mod_manager
        self.config_manager = config_manager
        self.config_manager.onLanguageChanged.connect(self._change_language)
        self.config_manager.onThemeChanged.connect(self._change_theme)
        self.config_manager.onConfigChanged.connect(self._config_changed)
        
        # This will update self.mod_manager
        self.config_manager.onGameDirectoryChanged.connect(self._game_directory_changed)
        self.config_manager.onModsDirectoryChanged.connect(self._mods_directory_changed)
        
        self.main_stacked_widget = QStackedWidget()
        self.home_page = HomePage(self.settings, mod_manager, config_manager)
        
        self.select_folder_page = SelectFolderPage(self.mod_manager.game_directory)
        self.select_folder_page.onGameFolderSelected.connect(self._change_game_directory)
        
        self.main_stacked_widget.addWidget(self.home_page)
        self.main_stacked_widget.addWidget(self.select_folder_page)
        
        self.setCentralWidget(self.main_stacked_widget)

        settings_game_directory = self.config_manager.get("game_path")
        if settings_game_directory is not None:
            if self.mod_manager.check_game_directory(settings_game_directory):
                self.mod_manager.set_game_directory(settings_game_directory)
            else:
                self.main_stacked_widget.setCurrentIndex(1)
                self.select_folder_page.set_folder_text(settings_game_directory)
                self.select_folder_page.set_info_text("BrownDust 2.exe was not found in the current game directory.")
        else:
            self.main_stacked_widget.setCurrentIndex(1)
            self.select_folder_page.set_info_text("Select the folder where \"BrownDust 2.exe\" is located." )
        
        if config_manager.get("debug", boolean=True, default=False) and self.main_stacked_widget.currentIndex() == 1:
            self.main_stacked_widget.setCurrentIndex(0)
        
        self._apply_stylesheet(self.config_manager.get("theme", default="dark"))
        self._apply_language(self.config_manager.get("language", default="english"))
        
        self.check_browndustx()

        # remove focus from qlineedit
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        
        self.restore_geometry()
        self.check_github_releases()

    def check_github_releases(self):
        url = "https://api.github.com/repos/bruhnn/BD2ModManager/releases"
        
        try:
            req = requests.get(url, timeout=5)
            req.raise_for_status()
            data = req.json()
            latest_version = data[0]["tag_name"][1:]
            
            if version.parse(__version__) < version.parse(latest_version):
                self.home_page.set_info_text(self.tr(f"🚀 New version {latest_version} available! Visit the GitHub releases page to update."))
            # else:
            #     self.home_page.set_info_text(self.tr(f"You are up to date!"))
        except requests.exceptions.RequestException:
            pass
        
    
    def restore_geometry(self):
        geometry = self.settings.value("mainWindow/geometry")
        if isinstance(geometry, QByteArray):
            self.restoreGeometry(geometry)
    
    def closeEvent(self, event):
        self.settings.setValue("mainWindow/geometry", self.saveGeometry())
        self.home_page.save_settings_state()
        return super().closeEvent(event)
    
    def _apply_stylesheet(self, theme: str):
        path = STYLES_PATH / f"{theme}.qss"

        if not path.exists():
            path = STYLES_PATH / "dark.qss"

        with path.open("r", encoding="utf-8") as f:
            stylesheet = f.read()
            self.setStyleSheet(stylesheet)

    def _apply_language(self, language: str):
        if language == "english":
            QApplication.instance().removeTranslator(QTranslator())
            self.retranslateUI()
            return
        
        translator = QTranslator()

        if translator.load((LANGUAGE_PATH / f"{language}.qm").as_posix()):
            QApplication.instance().installTranslator(translator)
            self.retranslateUI()
        else:
            print(f"Translation for {language} not found.")
    
    def _change_theme(self, theme: str):
        self._apply_stylesheet(theme)

    def _change_language(self, language: str):
        self._apply_language(language)
    
    def _change_game_directory(self, path: str):
        if self.mod_manager.check_game_directory(path):
            self.config_manager.game_directory = path
            self.mod_manager.set_game_directory(path)
            self.main_stacked_widget.setCurrentIndex(0) # Go To Home
            self.check_browndustx()
        else:
            self.select_folder_page.set_folder_text(path)
            self.select_folder_page.set_info_text("\"BrownDust 2.exe\" not found!")
        
    def _config_changed(self, config: str, value: str):
        if config == "language":
            self._change_theme(value)
        elif config == "theme":
            self._change_language(value)
    
    def _game_directory_changed(self, path: str):
        if self.mod_manager.check_game_directory(path):
            self.mod_manager.set_game_directory(path)
            self.check_browndustx()
        else:
            raise ValueError()
    
    def _mods_directory_changed(self, path: str):
        self.mod_manager.set_staging_mods_directory(path)
    
    def retranslateUI(self):
        self.home_page.retranslateUI()
    
    def check_browndustx(self):
        if self.mod_manager.is_browndustx_installed():
            self.home_page.set_info_text(f"BrownDustX {self.mod_manager.get_browndustx_version()}")
        else:
            self.home_page.set_info_text(self.tr("BrownDustX not installed!"))
            