from csv import DictReader
from pathlib import Path
from typing import Optional, Union

from .models import Character, Scene, NPC


class BD2Data:
    def __init__(self, characters_csv: Union[str, Path], datings_csv: Union[str, Path], scenes_csv: Union[str, Path], npcs_csv: Optional[Union[str, Path]]):
        self.characters_csv = Path(characters_csv)
        self.datings_csv = Path(datings_csv)
        self.scenes_csv = Path(scenes_csv)
        self.npcs_csv = Path(npcs_csv)
        
        self._characters = {}
        self._datings = {}
        self._scenes = {}
        self._npcs = {}

        self._load_characters()
        self._load_datings()
        self._load_scenes()
        self._load_npcs()


    def _load_characters(self) -> None:
        """Load characters from the CSV file."""
        if not self.characters_csv.exists():
            raise FileNotFoundError(
                f"Characters data file not found at {self.characters_csv}."
            )

        with self.characters_csv.open("r", encoding="utf-8") as file:
            reader = DictReader(file)
            self._characters = {
                str(row["id"]): {
                    "id": row["id"],
                    "character": row["character"],
                    "costume": row["costume"],
                }
                for row in reader
            }
        
    def _load_datings(self):
        """Load characters from the CSV file."""
        if not self.datings_csv.exists():
            raise FileNotFoundError(
                f"Dating data file not found at {self.datings_csv}."
            )

        with self.datings_csv.open("r", encoding="utf-8") as file:
            reader = DictReader(file)
            self._datings = {
                str(row["id"]): {
                    "id": row["id"],
                    "character_id": row["character_id"],
                }
                for row in reader
            }
    
    def _load_scenes(self):
        """Load scenes from the CSV file."""
        if not self.scenes_csv.exists():
            raise FileNotFoundError(
                f"Scenes data file not found at {self.scenes_csv}."
            )

        with self.scenes_csv.open("r", encoding="utf-8") as file:
            reader = DictReader(file)
            self._scenes = {
                str(row["id"]): {
                    "id": row["id"]
                }
                for row in reader
            }
    
    def _load_npcs(self):
        """Load npcs from the CSV file."""
        if not self.npcs_csv.exists():
            raise FileNotFoundError(
                f"Scenes data file not found at {self.npcs_csv}."
            )

        with self.npcs_csv.open("r", encoding="utf-8") as file:
            reader = DictReader(file)
            self._npcs = {
                str(row["id"]): {
                    "id": row["id"]
                }
                for row in reader
            }

    def get_characters(self) -> list[Character]:
        """
        Returns a list of all characters.
        """
        return [Character(id=char["id"], character=char["character"], costume=char["costume"]) for char in self._characters.values()]

    def get_dating_characters(self) -> list[Character]:
        return [Character.from_dict(self._characters.get(dating["character_id"])) for dating in self._datings.values() if self._characters.get(dating["character_id"])]
            
    
    def get_character_by_id(self, char_id: str) -> Optional[Character]:
        """
        Returns character data by ID.
        """
        char = self._characters.get(char_id, None)

        if not char:
            return

        return Character(
            id=char["id"],
            character=char["character"],
            costume=char["costume"]
        )

    def get_character_by_dating_id(self, dating_id: str) -> Optional[Character]:
        """
        Returns character from a dating ID
        """

        dating = self._datings.get(dating_id, None)

        if dating is None:
            return
        
        char = self._characters.get(dating["character_id"])
        
        if not char:
            return

        return Character(
            id=char["id"],
            character=char["character"],
            costume=char["costume"]
        )

    def get_scene_by_id(self, scene_id: str) -> Scene:
        return Scene("", "")
    
    def get_npc_by_id(self, npc_id: str) -> NPC:
        return NPC("", "")