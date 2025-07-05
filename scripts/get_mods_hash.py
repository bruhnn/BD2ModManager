from pathlib import Path
import csv
import argparse
from random import choices
from string import ascii_letters
from hashlib import sha256

def get_folder_hash(path: Path) -> str:
    hash = sha256()

    for file in sorted(path.rglob("*")):
        if file.is_file():
            with file.open("rb") as f:
                while chunk := f.read(8192):
                    hash.update(chunk)

    return hash.hexdigest()

parse = argparse.ArgumentParser()
parse.add_argument("path", type=Path)
parse.add_argument("-o", "--output", type=Path)
parse.add_argument("-a", "--author", type=str)

args = parse.parse_args()

directory: Path = args.path

if not directory.exists():
    raise FileNotFoundError(f"Directory not found: {directory}")

output_path: Path | None = args.output

if output_path is None:
    output_path = Path(__file__).parent / f'{"".join(choices(ascii_letters, k=8))}.csv'
    
author: str = args.author

if author is None:
    print("Author will be the name of the folder.")

data = []
for mod_folder in directory.iterdir():
    author = author or mod_folder.name

    folder_hash = get_folder_hash(mod_folder)
    
    data.append({
        "author": author,
        "hash": folder_hash
    })

if data:
    with output_path.open("w", encoding="UTF-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["author", "hash"])
        writer.writeheader()
        writer.writerows(data)

    print(f"Data saved to {output_path}")
else:
    print("Empty results. Not saved.")