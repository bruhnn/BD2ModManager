from pathlib import Path
from pathlib import PurePath
from hashlib import sha256

def get_folder_hash(path: Path) -> str:
    """Compute sha256 hash of all files under a directory."""
    hash = sha256()
    for file in sorted(path.rglob("*")):
        if file.is_file():
            hash.update(file.read_bytes())
    return hash.hexdigest()

def is_filename_valid(filename: str):
    print(PurePath(filename).name)
    return PurePath(filename).name == filename