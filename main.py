import sys
import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication

from src.BD2ModManager import BD2ModManager
from src.gui import MainWindow


def main():
    app = QApplication(sys.argv)

    BD2MM = BD2ModManager(Path(__file__).parent / "mods")

    window = MainWindow(BD2MM)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    main()
