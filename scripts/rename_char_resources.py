from pathlib import Path
import shutil
from argparse import ArgumentParser
import re

parse = ArgumentParser()
parse.add_argument("source", type=Path, help="Assets folder")
parse.add_argument("output", type=Path)
parse.add_argument("--overwrite", action="store_true", default=False)

# TODO: download from github, create a temporary folder then copy

args = parse.parse_args()

if not args.source.exists() or not args.source.is_dir():
    print(f'Source folder "{args.source}" not found or it is not a directory.')
    exit(0)

if not args.output.exists() or not args.output.is_dir():
    print(f'output folder "{args.output}" not found or it is not a directory.')
    exit(0)

regex = re.compile(r"illust_inven_char(\d+)_\d+.png")

for char_img in args.source.iterdir():
    if char_id_match := (regex.match(char_img.name)):
        char_id = char_id_match.group(1)

        path = args.output / f"{char_id}.png"

        if path.exists() and not args.overwrite:
            continue
        
        try:
            shutil.copy(char_img, path)
        except Exception as error:
            print(f"An error occurred copying character asset '{char_img.name}' ({char_id}) to {path}: {error}")
        else:
            print(f"Added new character asset for character ID {char_id}: {path}")