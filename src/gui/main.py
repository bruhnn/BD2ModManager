from PySide6.QtWidgets import QMainWindow, QStackedWidget, QVBoxLayout, QApplication
from PySide6.QtCore import QTranslator, Qt

from src.BD2ModManager import BD2ModManager
from .pages import HomePage
from .config import BD2MMConfigManager
from pathlib import Path

import sys

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
        self.setWindowTitle("BrownDust2 Mod Manager")
        self.setGeometry(600, 250, 800, 600)
        self.setObjectName("mainWindow")

        self.mod_manager = mod_manager
        self.config_manager = config_manager

        self.main_stacked_widget = QStackedWidget()
        self.home_page = HomePage(mod_manager, config_manager)
        self.home_page.onThemeChanged.connect(self._change_theme)
        self.home_page.onLanguageChanged.connect(self._change_language)

        self.main_stacked_widget.addWidget(self.home_page)
        
        self.setCentralWidget(self.main_stacked_widget)

        self._apply_stylesheet(self.config_manager.get("theme", default="dark"))
        self._apply_language(self.config_manager.get("language", default="english"))

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
    
    def retranslateUI(self):
        self.home_page.retranslateUI()