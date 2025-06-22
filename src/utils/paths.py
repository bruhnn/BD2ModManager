import sys
from pathlib import Path

IS_BUNDLED = hasattr(sys, "_MEIPASS")
CURRENT_PATH = Path(sys.executable).parent if IS_BUNDLED else Path(__file__).parent.parent
BUNDLE_PATH = Path(sys._MEIPASS) if IS_BUNDLED else CURRENT_PATH

DATA_FOLDER = BUNDLE_PATH / "data"

# CSV
CHARACTERS_CSV = DATA_FOLDER / "characters.csv"
DATINGS_CSV = DATA_FOLDER / "datings.csv"
SCENES_CSV = DATA_FOLDER / "scenes.csv"
NPCS_CSV = DATA_FOLDER / "npcs.csv"
AUTHORS_CSV = DATA_FOLDER / "authors.csv"

# Tools
SEVENZIP_BINARY_PATH = BUNDLE_PATH / "tools" / "7z" / "7za.exe"
