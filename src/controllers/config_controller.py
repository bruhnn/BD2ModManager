from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMessageBox

# from src.models import ConfigModel
# from src.views import ConfigView

class ConfigController(QObject):
    def __init__(self, model, view, mods_model):
        super().__init__()

        self.model = model
        self.view = view
        self.mods_model = mods_model
        
        self.view.onSearchModsRecursivelyChanged.connect(lambda value: self.model.set("search_mods_recursively", value))
        self.view.onGameDirectoryChanged.connect(self.on_game_directory_changed)
        self.view.onModsDirectoryChanged.connect(lambda value: self.model.set("staging_mods_path", value))
        self.view.onLanguageChanged.connect(lambda value: self.model.set("language", value))
        self.view.onThemeChanged.connect(lambda value: self.model.set("theme", value))
        self.view.onSyncMethodChanged.connect(lambda value: self.model.set("sync_method", value))
        
        self.update_config()
    
    def on_game_directory_changed(self, path: str):
        if self.mods_model.check_game_directory(path):
            self.model.game_directory = path
            return
        
        # show error
        QMessageBox.critical(None, "Game Not Found", f"Game executable 'BrownDust II.exe' not found in directory:\n{path}")
    
    def update_config(self):
        self.view.update_config(self.model.as_dict())