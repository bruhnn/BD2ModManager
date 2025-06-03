import sys
import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTranslator

from src.BD2ModManager import BD2ModManager
from src.gui import MainWindow
from src.gui.config import BD2MMConfigManager

from src.gui.resources import icons_rc, characters_rc

if getattr(sys, 'frozen', False): # if is running on .exe
    CURRENT_PATH = Path(sys.executable).parent
    BUNDLE_PATH = Path(sys._MEIPASS)
else:
    CURRENT_PATH = Path(__file__).parent
    BUNDLE_PATH = CURRENT_PATH

def main():
    app = QApplication(sys.argv)

    BD2MMConfig = BD2MMConfigManager(CURRENT_PATH / "BD2ModManager.ini")
    
    staging_folder = BD2MMConfig.get("staging_mods_path")
    
    if not staging_folder:
        staging_folder = CURRENT_PATH / "mods"
        BD2MMConfig.set("staging_mods_path", str(staging_folder))

    BD2MM = BD2ModManager(staging_folder, CURRENT_PATH / "mods.json")

    window = MainWindow(BD2MM, BD2MMConfig)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    main()
