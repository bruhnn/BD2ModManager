import sys
from pathlib import Path
from PySide6.QtCore import QCoreApplication, QStandardPaths


class ApplicationPaths:
    SRC_DIR_NAME = "src"
    DATA_SUBDIR_NAME = "data"
    RESOURCES_DIR_NAME = "resources"
    ASSETS_SUBDIR_NAME = "assets"
    CHAR_ASSETS_SUBDIR_NAME = "characters"
    USER_CHAR_ASSETS_DIR_NAME = "characters_assets"
    PROFILES_DIR_NAME = "profiles"
    CACHE_DIR_NAME = "cache"

    def __init__(self) -> None:
        self.is_running_as_exe = hasattr(sys, "_MEIPASS")

        if self.is_running_as_exe:
            self._app_path = Path(sys.executable).parent
            self._bundle_path = Path(getattr(sys, "_MEIPASS"))
        else:
            self._app_path = Path(__file__).resolve().parent.parent.parent
            self._bundle_path = self._app_path


        # User-specific, writable data path
        self._user_data_path = self._get_user_data_path()
        
        self._create_required_directories()

    def _get_user_data_path(self) -> Path:
        """Finds the appropriate writable location for user data."""
        path_str = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppLocalDataLocation
        )

        if not path_str:
            app_name = QCoreApplication.applicationName()
            if not app_name:
                app_name = "BD2ModManager" # Fallback app name
            path_str = str(Path.home() / f".{app_name}")
            
        return Path(path_str)

    def _create_required_directories(self):
        dirs_to_create = [
            self.user_data_path,
            self.user_data_subpath,
            self.user_characters_assets,
            self.profiles_path,
            self.user_cache_path,
            self.user_tools_path
        ]
        for path in dirs_to_create:
            path.mkdir(parents=True, exist_ok=True)

    # --- Base Path Properties ---
    @property
    def app_path(self) -> Path:
        """The root directory of the application source or install location."""
        return self._app_path

    @property
    def bundle_path(self) -> Path:
        return self._bundle_path

    @property
    def user_data_path(self) -> Path:
        """The root directory for user-specific, writable data."""
        return self._user_data_path
        
    @property
    def source_path(self) -> Path:
        """The path to the 'src' directory."""
        return self.app_path / self.SRC_DIR_NAME

    @property
    def resources_path(self) -> Path:
        """The path where bundled resources are located."""
        return self.bundle_path / self.SRC_DIR_NAME / self.RESOURCES_DIR_NAME

    @property
    def assets_path(self) -> Path:
        """The path to bundled assets."""
        return self.resources_path / self.ASSETS_SUBDIR_NAME

    @property
    def character_assets(self) -> Path:
        """The path to the default, bundled character assets."""
        return self.assets_path / self.CHAR_ASSETS_SUBDIR_NAME

    @property
    def user_characters_assets(self) -> Path:
        """Path where users can store their own character assets."""
        return self.user_data_path / self.USER_CHAR_ASSETS_DIR_NAME

    @property
    def profiles_path(self) -> Path:
        """Path to the directory containing user profiles."""
        return self.user_data_path / self.PROFILES_DIR_NAME
        
    @property
    def user_cache_path(self) -> Path:
        """Path to a directory for caching temporary data."""
        return self.user_data_path / self.CACHE_DIR_NAME

    @property
    def app_data_path(self) -> Path:
        """Path to the default/template data directory in the application bundle."""
        return self.source_path / self.DATA_SUBDIR_NAME
        
    @property
    def user_data_subpath(self) -> Path:
        """Path to the user's writable data sub-directory."""
        return self.user_data_path / self.DATA_SUBDIR_NAME

    @property
    def characters_csv(self) -> Path:
        """Path to the user's writable characters.csv."""
        return self.user_data_subpath / "characters.csv"

    @property
    def default_characters_csv(self) -> Path:
        """Path to the default characters.csv included with the app."""
        return self.app_data_path / "characters.csv"
        
    @property
    def datings_csv(self) -> Path:
        """Path to the user's writable datings.csv."""
        return self.user_data_subpath / "datings.csv"

    @property
    def default_datings_csv(self) -> Path:
        """Path to the default datings.csv included with the app."""
        return self.app_data_path / "datings.csv"

    @property
    def authors_csv(self) -> Path:
        """Path to the user's writable authors.csv."""
        return self.user_data_subpath / "authors.csv"

    @property
    def default_authors_csv(self) -> Path:
        """Path to the default authors.csv included with the app."""
        return self.app_data_path / "authors.csv"
        
    @property
    def manifest_json(self) -> Path:
        """Path to the user's manifest.json file."""
        return self.user_data_path / "manifest.json"

    @property
    def tools_path(self) -> Path:
        return self.bundle_path / "tools"
    
    @property
    def user_tools_path(self) -> Path:
        return self._user_data_path / "tools"
        


app_paths = ApplicationPaths()