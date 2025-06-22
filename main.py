import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon, QFont, QFontDatabase
from PySide6.QtCore import QSettings, Qt

from src.models import ModsModel, ConfigModel
from src.views import MainWindowView, ModsView, CharactersView, ConfigView, ProfilesView
from src.controllers import MainWindowController, ModsController, CharactersController, ConfigController, ProfilesController
from src.utils.logger import setup_logging

from src.resources import characters_rc, icons_rc

if getattr(sys, 'frozen', False):  # if is running on .exe
    CURRENT_PATH = Path(sys.executable).parent
    BUNDLE_PATH = Path(getattr(sys, "_MEIPASS", CURRENT_PATH))
else:
    CURRENT_PATH = Path(__file__).parent
    BUNDLE_PATH = CURRENT_PATH

def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon((BUNDLE_PATH / r"icon.ico").as_posix()))
    
    QFontDatabase.addApplicationFont(r"C:\Users\dogui\Documents\GitHub\BD2ModManager\src\resources\fonts\Cinzel\Cinzel-VariableFont_wght.ttf")

    settings = QSettings("Bruhnn", "BD2ModManager")

    config_model = ConfigModel(path=CURRENT_PATH / "BD2ModManager.ini")
    
    staging_mods_dir = config_model.mods_directory
    
    if not staging_mods_dir:
        staging_mods_dir = CURRENT_PATH / "mods"
        config_model.mods_directory = staging_mods_dir.as_posix()
    
    if not Path(staging_mods_dir).exists():
        Path(staging_mods_dir).mkdir(exist_ok=True, parents=True)
    
    mods_model = ModsModel(
        game_directory=config_model.game_directory,
        staging_mods_directory=staging_mods_dir,
        data_file=CURRENT_PATH / "mods.json"
    )
    
    mainwindow_view = MainWindowView(settings)
    mods_view = ModsView(settings)
    characters_view = CharactersView()    
    config_view = ConfigView()
    
    mods_controller = ModsController(mods_model, mods_view, config_model)
    characters_controller = CharactersController(mods_model, characters_view)
    config_controller = ConfigController(config_model, config_view, mods_model)
    
    # profiles_view = ProfilesView()
    # profiles_controller = ProfilesController(mods_model, profiles_view)
    
    # Create main window controller instead of direct window
    main_window_controller = MainWindowController(
        mainwindow_view,
        mods_controller, 
        characters_controller,
        # profiles_controller,
        config_controller
    )
    main_window_controller.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        command = sys.argv[1]
    except IndexError:
        command = None
    
    if command != "no_logs":
        setup_logging(CURRENT_PATH / "BD2ModManager.log")
        
    main()