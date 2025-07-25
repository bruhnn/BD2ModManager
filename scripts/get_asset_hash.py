from argparse import ArgumentParser
from hashlib import sha256
from pathlib import Path

def get_file_hash(path: Path) -> str:
    hash = sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash.update(chunk)
    return hash.hexdigest()


parser = ArgumentParser()
parser.add_argument("character_id", type=str)

args = parser.parse_args()

ASSETS_FOLDER = Path(__file__).parent / "../src/resources/assets/characters"

CHAR_ASSET_PATH = ASSETS_FOLDER / f"{args.character_id}.png"

if(CHAR_ASSET_PATH.exists()):
    print(get_file_hash(CHAR_ASSET_PATH))
else:
    print("Character asset not found.")