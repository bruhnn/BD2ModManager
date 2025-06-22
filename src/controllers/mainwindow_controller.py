import re
import requests
from packaging import version
from typing import Optional

from PySide6.QtCore import QObject

from src.version import __version__
from src.views import MainWindowView

from src.utils.theme_manager import ThemeManager

class MainWindowController(QObject):
    def __init__(self, view: MainWindowView, mods_controller, characters_controller, config_controller, profiles_controller = None):
        super().__init__()
        
        self.view = view
        
        self.mods_controller = mods_controller
        self.characters_controller = characters_controller
        self.profiles_controller = profiles_controller
        self.config_controller = config_controller
        
        mods_controller.showToastRequested.connect(self.view.show_toast)
        
        # game folder selection page
        self.view.onGameFolderSelected.connect(self.on_game_directory_selected)
        self.view.onAppClose.connect(self.on_app_close)
        
        self.view.add_navigation(self.tr("Mods"), self.mods_controller.view, "extension")
        self.view.add_navigation(self.tr("Characters"), self.characters_controller.characters_view, "book4_fill")
        self.view.set_settings_view(config_controller.view)

        current_theme = self.config_controller.model.theme
        
        self.view.apply_stylesheet(current_theme)
        # current_language = self.config_controller.model.language
        # self.view.apply_language(current_language)
        
        self.check_game_directory()
        self.get_browndustx_version()
        # self.mods_controller.view.loaded.connect(self.check_github_releases)

        self.config_controller.view.onThemeChanged.connect(self.view.apply_stylesheet)
    
    def on_app_close(self):
        self.mods_controller.view.save_settings_state()
    
    def show(self):
        self.view.show()
        
    def check_game_csv(self):
        """Check if characters.csv, authors.csv, etc. needs to be updated without installing another app version."""
        # it will make a requests to characters.csv from github and save it
        pass
    
    def check_game_directory(self):
        game_dir = self.mods_controller.model.game_directory
        
        if self.config_controller.model.get("bypass_path", boolean=True):
            return
        
        if not game_dir or not self.mods_controller.model.check_game_directory(game_dir.as_posix()):
            self.view.show_game_directory_selection_page()
    
    def check_github_releases(self):
        url = "https://api.github.com/repos/bruhnn/BD2ModManager/releases"
                
        try:
            req = requests.get(url, timeout=5)
            req.raise_for_status()
            data = req.json()
            latest_version = data[0]["tag_name"][1:]
            
            if version.parse(__version__) < version.parse(latest_version):
                self.view.show_toast(text=self.tr(f"🚀 New version {latest_version} available! Visit the GitHub releases page to update."), duration=20000)
        except requests.exceptions.RequestException:
            pass
    
    def _check_browndustx_version(self) -> Optional[version.Version]:
        url = "https://raw.githubusercontent.com/bruhnn/BD2ModManager/refs/heads/main/src/version.py"
        
        try:
            req = requests.get(url, timeout=5)
            req.raise_for_status()
            
            content = req.text
            
            if (match := re.search(r"BDX_VERSION\s?=\s?\"([0-9\.]+)\"", content, re.I)):
                if match.groups():
                    return version.parse(match.group(1))
        except Exception:
            return

    def get_browndustx_version(self):
        if self.mods_controller.model.is_browndustx_installed():
            bdx_version = self.mods_controller.model.get_browndustx_version()
            
            new_bdx_version = version.parse("0.0.0") # self._check_browndustx_version()
            if new_bdx_version and version.parse(bdx_version) < new_bdx_version:
                self.mods_controller.view.set_info_text(f"BrownDustX {new_bdx_version} is now available.")
            else:
                self.mods_controller.view.set_info_text(f"BrownDustX {bdx_version}")
        else:
            self.mods_controller.view.set_info_text(self.tr("BrownDustX not installed!"))
        
    def on_game_directory_selected(self, path: str):
        if not self.mods_controller.model.check_game_directory(path):
            self.view.select_game_dir_page.set_folder_text(path)
            self.view.select_game_dir_page.set_info_text("BrownDust II.exe not found!")
            return
        
        # Move to Home
        self.view.show_home_page()
        
        # it'll automatically update mod model
        self.config_controller.model.game_directory = path

        # update settings page
        # self.config_controller.update_config()

