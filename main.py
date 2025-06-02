import sys
import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication

from src.BD2ModManager import BD2ModManager
from src.gui import MainWindow
from src.gui.config import BD2MMConfigManager

from src.gui.resources import icons_rc


def main():
    app = QApplication(sys.argv)
    
    CURRENT_PATH = Path(__file__).parent

    BD2MMConfig = BD2MMConfigManager(CURRENT_PATH / "BD2ModManager.ini")
        
    BD2MM = BD2ModManager(BD2MMConfig.get("staging_mods_path"))

    window = MainWindow(BD2MM, BD2MMConfig)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    main()
