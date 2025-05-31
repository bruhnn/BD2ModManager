from csv import DictReader
from pathlib import Path
from typing import Optional, Union

class BD2Characters:
    def __init__(self, characters_csv: Union[str, Path]):
        self.characters_csv = Path(characters_csv)
        self._characters = {}

        self._load_characters()

    @property
    def characters(self):
        return self._characters

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

    def get_characters(self) -> list:
        """
        Returns a list of all characters.
        """
        return list(self._characters.values())

    def get_character_by_id(self, char_id: str) -> Optional[dict]:
        """
        Returns character data by ID.
        """
        return self._characters.get(char_id, None)
