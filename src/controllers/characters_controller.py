from PySide6.QtCore import QObject

from src.models import ModsModel
# from src.views import CharactersView

class CharactersController(QObject):
    def __init__(self, mods_model: ModsModel, characters_view):
        super().__init__()

        self.mods_model = mods_model
        self.characters_view = characters_view
        self.characters_view.refreshCharactersRequested.connect(self.update_chars)
        
        # if enabled, disable, etc.
        self.mods_model.modsStateChanged.connect(self.update_chars)

        self.update_chars()
        
    def update_chars(self):
        self.characters_view.load_characters(self.mods_model.get_characters_mod_status())