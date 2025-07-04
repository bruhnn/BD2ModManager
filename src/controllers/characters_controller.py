from PySide6.QtCore import QObject

from src.models import ModManagerModel
from src.views import CharactersView


class CharactersController(QObject):
    def __init__(
        self, mod_manager_model: ModManagerModel, characters_view: CharactersView
    ) -> None:
        super().__init__()

        self.mod_manager_model = mod_manager_model
        self.characters_view = characters_view
        self.characters_view.refreshCharactersRequested.connect(self.update_chars)

        # if mod enabled, disabled, etc.
        self.mod_manager_model.modsRefreshed.connect(self.update_chars)
        self.mod_manager_model.modsStateChanged.connect(self.update_chars)
        self.mod_manager_model.modsAdded.connect(self.update_chars)
        self.mod_manager_model.modsRemoved.connect(self.update_chars)

        self.update_chars()

    def update_chars(self) -> None:
        self.characters_view.load_characters(
            self.mod_manager_model.get_characters_mod_status()
        )
