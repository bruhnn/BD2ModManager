from src.version import __version__
from src.views import MainView
from src.controllers import MainController
from src.utils.logger import setup_logging
from src.utils.paths import app_paths
from argparse import ArgumentParser
import logging
import time
import sys
import shutil

from PySide6.QtWidgets import QApplication, QMessageBox, QSplashScreen
from PySide6.QtGui import QIcon, QFontDatabase, QPixmap
from PySide6.QtCore import Qt

# Needs to add the correct organization name and application before initializing app_paths
QApplication.setOrganizationName("Bruhnn")
QApplication.setApplicationName("BD2ModManager")


logger = logging.getLogger(__name__)


class Application:
    def __init__(self, start_time: float) -> None:
        logger.info("Initializing Application...")
        self._start_time = start_time

        self.app = QApplication(sys.argv)
        self.app.setOrganizationName("Bruhnn")
        self.app.setApplicationName("BD2ModManager")

        # self._show_splash_screen()

        self._init_appdata()
        self._add_resources()
        self._create_ui()
        logger.info("Application initialization complete.")

    def _show_splash_screen(self) -> None:
        logger.info("Showing splash screen...")
        splash_img = QPixmap(app_paths.source_path /
                             "resources" / "splash.png")
        splash_img = splash_img.scaled(
            200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.splash = QSplashScreen(
            splash_img, Qt.WindowType.WindowStaysOnTopHint)
        self.splash.show()
        self.app.processEvents()

    def _add_resources(self) -> None:
        logger.info("Adding application resources...")
        # load resources from QRC file: DON'T RUN RUFF --fix
        from src.resources import icons_rc, characters_rc

        icon_path = app_paths.source_path / "resources" / "icon.ico"

        if icon_path.exists():
            self.app.setWindowIcon(QIcon(str(icon_path)))
            logger.debug(f"Application icon set from {icon_path}")
        else:
            logger.warning(f"Application icon not found at {icon_path}")

        font_path = (
            app_paths.source_path
            / "resources"
            / "fonts"
            / "Cinzel"
            / "Cinzel-VariableFont_wght.ttf"
        )

        if font_path.exists():
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            if font_id != -1:
                font_families = QFontDatabase.applicationFontFamilies(font_id)
                logger.debug(
                    f"Font '{font_families[0]}' loaded from {font_path}")
            else:
                logger.error("Failed to load font from %s", font_path)
        else:
            logger.warning("Font not found at %s", font_path)

    def _init_appdata(self) -> None:
        logger.info("Initializing application data...")

        # Copy manifest.json
        default_manifest = app_paths.default_manifest_json
        user_manifest = app_paths.manifest_json

        if not user_manifest.exists():
            logger.info(
                f"User manifest not found, copying default to {user_manifest}")
            try:
                user_manifest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(default_manifest, user_manifest)
            except (IOError, OSError) as e:
                logger.critical(
                    f"Failed to copy default manifest: {e}", exc_info=True)
                QMessageBox.critical(
                    None,
                    "Fatal Initialization Error",
                    f"The application failed to create a critical configuration file.\n\n"
                    f"Error details: {e}\n\n"
                    "Please check folder permissions or try running as administrator. The application will now exit."
                )
                sys.exit(1)
        
        data_files = (
            (app_paths.default_characters_csv, app_paths.characters_csv),
            (app_paths.default_authors_csv, app_paths.authors_csv),
            (app_paths.default_datings_csv, app_paths.datings_csv),
            (app_paths.default_npcs_csv, app_paths.npcs_csv)
        )
        
        for default_file, user_file in data_files:
            if not user_file.exists():
                try:
                    logger.info(f"User data '{default_file.name}' not found. Copying default.")

                    shutil.copy2(default_file, user_file)
                except (IOError, OSError) as error:
                    logger.critical(f"Could not initialize {default_file.name}. Error: {error}", exc_info=True)
                    QMessageBox.critical(
                        None,
                        "Fatal Error",
                        f"A critical error occurred while initializing application data.\n\n"
                        f"File: {default_file.name}\n"
                        f"Error: {error}\n\n"
                        "The application will now exit."
                    )
                    sys.exit(1)


        tools = (
            (app_paths.tools_path / "BD2ModPreview.exe", app_paths.user_tools_path / "BD2ModPreview.exe"),
        )

        for tool_src, user_tool_dst in tools:
            logger.debug(f"Checking for tool: {user_tool_dst}")

            try:
                if not user_tool_dst.exists():
                    if tool_src.exists():
                        logger.info(
                            "User tool not found. Copying from '%s' to '%s'",
                            tool_src, user_tool_dst
                        )
                        shutil.copy2(tool_src, user_tool_dst)
                    else:
                        raise FileNotFoundError(
                            f"Default tool not found at {tool_src}")
            except (IOError, OSError, FileNotFoundError) as e:
                logger.critical(
                    "Could not initialize tool: %s. Error: %s",
                    user_tool_dst, e,
                    exc_info=True,
                )

    def _create_ui(self) -> None:
        logger.info("Creating user interface...")
        self.main_view = MainView()
        logger.debug("MainView instantiated.")
        self.main_controller = MainController(view=self.main_view)
        logger.debug("MainController instantiated and linked with MainView.")
        logger.info("UI creation complete.")

    def run(self) -> int:
        end_time = time.perf_counter()
        load_time = end_time - self._start_time
        logger.info("Application loaded in %.3f seconds.", load_time)

        logger.info("Showing main window and starting application event loop.")
        self.main_controller.show()

        if hasattr(self, "splash"):
            self.splash.finish(self.main_view)
            self.splash.deleteLater()

        return self.app.exec()


def main() -> None:
    parser = ArgumentParser(
        description=f"BD2ModManager v{__version__}",
        epilog="Example: python main.py --log-level debug"
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}"
    )

    logging_group = parser.add_argument_group("Logging")

    logging_group.add_argument(
        "-l", "--log-level",
        type=str,
        default="debug",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Set the logging verbosity level (default: %(default)s)."
    )
    logging_group.add_argument(
        "-f",
        "--log-filter",
        type=str,
        metavar="NAME",
        help="Filter logs by a specific module or function name."
    )
    logging_group.add_argument(
        "-n",
        "--no-logs",
        action="store_true",
        default=False
    )

    args = parser.parse_args()

    if not args.no_logs:
        setup_logging(app_paths.app_path / "BD2ModManager-logs.log",
                      args.log_level, args.log_filter)

    logger.info("=" * 50)
    logger.info("Starting BD2ModManager v%s", __version__)
    logger.info("=" * 50)

    start_time = time.perf_counter()

    from src.themes import ThemeManager

    ThemeManager.load_themes()

    app = Application(start_time=start_time)
    sys.exit(app.run())


if __name__ == "__main__":
    main()
