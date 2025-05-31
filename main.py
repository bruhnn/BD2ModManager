import sys
from PySide6.QtWidgets import QApplication

from src.BD2ModManager import BD2ModManager
from src.gui import MainWindow


def main():
    app = QApplication(sys.argv)

    BD2MM = BD2ModManager()

    window = MainWindow(BD2MM)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
