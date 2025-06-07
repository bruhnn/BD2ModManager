from csv import DictReader
from pathlib import Path

from .files import get_folder_hash


def load_authors(path: Path):
    try:
        with path.open("r", encoding="UTF-8") as file:
            data = DictReader(file, ["author", "hash"])
            
            authors = {
                row["hash"]: row["author"] for row in data
            }
    except Exception:
        return 
    
    return authors

def get_author_by_folder(authors: dict, path: str):
    folder_hash = get_folder_hash(Path(path))
    return authors.get(folder_hash)