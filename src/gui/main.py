from PySide6.QtWidgets import QMainWindow, QStackedWidget

from src.BD2ModManager import BD2ModManager
from .pages import HomePage
from .config import BD2MMConfigManager

class MainWindow(QMainWindow):
    def __init__(self, mod_manager: BD2ModManager, config_manager: BD2MMConfigManager):
        super().__init__()
        self.setWindowTitle("BrownDust2 Mod Manager")

        self.setGeometry(600, 250, 800, 600)

        self.mod_manager = mod_manager
        self.config_manager = config_manager

        self.main_stacked_widget = QStackedWidget()
    
        self.home_page = HomePage(mod_manager, config_manager)

        self.main_stacked_widget.addWidget(self.home_page)
        
        self.setCentralWidget(self.main_stacked_widget)