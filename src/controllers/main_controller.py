from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Slot, QTranslator
from PySide6.QtGui import QCloseEvent

import logging

from src.controllers.profile_manager_controller import ProfileManagerController
from src.models import ConfigModel, ModManagerModel

from src.models import ProfileManager
from src.services.mod_preview import BD2ModPreview
from src.views import MainView, ModsView, ConfigView, CharactersView, ManageProfilesView
from src.controllers import CharactersController, ConfigController, ModManagerController
from src.services import BD2GameData, UpdateManager
from src.themes import ThemeManager

from src.utils.files import open_file_or_directory
from src.utils.paths import app_paths


logger = logging.getLogger(__name__)


class MainController(QObject):
    def __init__(
        self,
        view: MainView,
    ) -> None:
        super().__init__()

        self.view = view
        
        self.mod_preview = BD2ModPreview()
        self.mod_preview.errorOccurred.connect(self._on_mod_preview_error)

        # to prevent update manager to trigger multiple notifications
        self._is_currently_updating = False

        self._setup_models()
        self._setup_views()
        self._setup_controllers()
        self._setup_signals()
        self._setup_navigation()
        self._setup_update_manager()

        # check if the game directory is stil valid, if not show the game selection page
        self._check_game_directory()
        self._refresh_profiles_dropdown()

        # Apply initial theme and language
        self._on_apply_stylesheet(self.config_model.theme)
        self._on_apply_language(self.config_model.language)

    # --- Setups
    def _setup_models(self) -> None:
        self.config_model = ConfigModel(
            path=app_paths.app_path / "BD2ModManager.ini")

        self.game_data_model = BD2GameData(
            characters_csv=app_paths.characters_csv,
            datings_csv=app_paths.datings_csv,
            npcs_csv=app_paths.npcs_csv
        )

        self.profile_manager_model = ProfileManager(
            profiles_directory=app_paths.profiles_path
        )

        staging_mods_dir = self.config_model.mods_directory

        if staging_mods_dir is None:
            staging_mods_dir = app_paths.app_path / "mods"

            self.config_model.set_mods_directory(str(staging_mods_dir.resolve()))

        self.mod_manager_model = ModManagerModel(
            game_data=self.game_data_model,
            profile_manager=self.profile_manager_model,
            staging_mods_directory=staging_mods_dir,
            mods_data_file=app_paths.user_data_path / "mods.json",
            game_directory=self.config_model.game_directory,
        )

    def _setup_views(self) -> None:
        self.mods_view = ModsView()
        self.characters_view = CharactersView()
        self.config_view = ConfigView()
        self.manage_profiles_view = ManageProfilesView()

    def _setup_controllers(self) -> None:
        self.mod_manager_controller = ModManagerController(
            self.mod_manager_model, self.mods_view, self.config_model
        )
        self.mod_manager_controller.notificationRequested.connect(
            self.view.show_notification
        )

        self.characters_controller = CharactersController(
            self.mod_manager_model, self.characters_view
        )

        self.config_controller = ConfigController(
            self.config_model, self.config_view
        )

        self.config_controller.validateGameDirectory.connect(
            self._validate_config_game_directory
        )

        self.profile_manager_controller = ProfileManagerController(
            self.profile_manager_model, self.manage_profiles_view
        )
        self.profile_manager_controller.notificationRequested.connect(
            self.view.show_notification
        )

    def _setup_signals(self) -> None:
        # Config Signals
        self.config_model.themeChanged.connect(self._on_apply_stylesheet)
        self.config_model.languageChanged.connect(self._on_apply_language)

        # Config Controller actions
        self.config_controller.findAuthorsClicked.connect(
            self._on_find_authors_clicked)
        self.config_controller.migrateToProfilesClicked.connect(
            self._on_migrate_to_profiles_clicked)

        # View Signals
        self.view.appClosing.connect(self._on_app_close)
        self.view.gameFolderSelected.connect(self._on_game_directory_selected)
        self.view.launchGameRequested.connect(self._on_launch_game_requested)
        self.view.profileChanged.connect(self._profile_changed)
        self.view.showProfilePageRequested.connect(
            self._on_show_profile_page_requested)

        # Profile Signals
        self.profile_manager_model.profilesChanged.connect(
            self._refresh_profiles_dropdown
        )
        
        
        # preview
        self.mod_manager_controller.modPreviewRequested.connect(
            self._on_mod_preview_requested
        )

    def _setup_navigation(self) -> None:
        # Navigation
        self.view.add_page("mods", self.mods_view)
        self.view.add_page("characters", self.characters_view)
        self.view.add_page("settings", self.config_view)
        self.view.add_page("profiles", self.manage_profiles_view)

        self.view.add_navigation_button("mods", self.tr("Mods"), "extension")
        self.view.add_navigation_button(
            "characters", self.tr("Characters"), "book4_fill")
        self.view.add_navigation_button(
            "settings", self.tr("Settings"), "settings")

    def _setup_update_manager(self) -> None:
        self.update_manager = UpdateManager(
            manifest_url=self.config_model.manifest_url,
            releases_url=self.config_model.releases_url,
            modpreview_releases_url="https://api.github.com/repos/bruhnn/BD2ModPreview/releases"
        )

        self.update_manager.appUpdateAvailable.connect(
            self._on_app_new_version_available
        )
            
        self.update_manager.dataUpdateAvailable.connect(
            self._on_update_started)
        self.update_manager.assetUpdateAvailable.connect(
            self._on_update_started
        )
        self.update_manager.allDownloadsFinished.connect(
            self._on_all_updates_finished)
        
        self.update_manager.errorOccurred.connect(self._on_update_error)
        
        self.update_manager.toolUpdateAvailable.connect(self._on_tool_update_available)
        self.update_manager.toolUpdated.connect(self._on_tool_updated)

        if self.config_model.auto_download_game_data:
            self.update_manager.start_update_process()
        
        if self.config_model.auto_update_mod_preview:
            self.update_manager.check_bd2modpreview_version()
        
        self.update_manager.check_app_version()
    
    @Slot(str)
    def _on_tool_update_available(self, tool_name: str):
        self.view.show_notification(
            title=self.tr("Tool Update Available"),
            text=self.tr(f"A new version of {tool_name} is available. Updating now..."),
            duration=3000,
        )

    @Slot(str)
    def _on_tool_updated(self, tool_name: str):
        if tool_name == "BD2ModPreview":
            self.mod_preview.refresh_path()
            
        self.view.show_notification(
            title=self.tr("Tool Updated"),
            text=self.tr(f"{tool_name} was successfully updated."),
            duration=3000,
        )

    # --- Slots
    @Slot(str)
    def _on_app_new_version_available(self, version: str) -> None:
        self.view.set_update_available(version)
        self.view.show_notification(
            title=self.tr(f"New version {version} available!"),
            text=self.tr("Visit the GitHub releases page to update."),
            duration=20000,
        )

    @Slot(str)
    def _on_update_started(self, key: str):
        if not self._is_currently_updating:
            self._is_currently_updating = True
            self.view.show_notification(
                title=self.tr("Downloading new game data..."),
                text=self.tr("The application will update in the background."),
            )

    @Slot()
    def _on_all_updates_finished(self):
        if self._is_currently_updating:
            self.view.show_notification(
                title=self.tr("Update Complete!"),
                text=self.tr("Game data has been successfully updated."),
                duration=2000,
            )
            self.mod_manager_model.refresh_game_data()
            
            # if new characters was added
            self.characters_controller.update_chars()

        self._is_currently_updating = False 

    @Slot(str)
    def _on_update_error(self, error_message: str):
        self._is_currently_updating = False

    @Slot()
    def _on_app_close(self, event: QCloseEvent) -> None:
        self.mods_view.save_settings_state()
        event.accept()

    @Slot(str)
    def _on_apply_stylesheet(self, theme: str) -> None:
        self.apply_stylesheet(theme)

    @Slot(str)
    def _on_apply_language(self, language: str) -> None:
        self.apply_language(language)

    @Slot()
    def _on_game_directory_selected(self, path: str) -> None:
        if not self.mod_manager_model.check_game_directory(path):
            self.view.set_game_directory_error(
                path, self.tr("BrownDust II.exe not found!")
            )
            return

        # Move to Home
        self.view.show_main_page()

        self.config_model.set_game_directory(path)

    @Slot()
    def _on_launch_game_requested(self) -> None:
        if not self.mod_manager_model.game_directory:
            return self.view.show_notification(
                self.tr("Game directory is not set."), None, "error", 3000
            )

        exe_path = self.mod_manager_model.game_exe_path

        if exe_path is None:
            return self.view.show_notification(
                self.tr(
                    "Game executable 'BrownDust II.exe' not found in game directory."
                ),
                None,
                "error",
                3000,
            )

        result, error_msg = open_file_or_directory(exe_path)

        if not result:
            self.view.show_notification(
                self.tr("Failed to launch game: {error}").format(
                    error=error_msg),
                None,
                "error",
                5000,
            )
            return

        self.view.show_notification(
            title=self.tr("Starting Brown Dust 2"), type="success"
        )

    @Slot(str)
    def _profile_changed(self, profile_id: str) -> None:
        self.profile_manager_model.switch_profile(profile_id)

    @Slot()
    def _on_show_profile_page_requested(self) -> None:
        self.view.change_navigation_page("profiles")

    @Slot()
    def _on_find_authors_clicked(self):
        self.mod_manager_model.set_experimental_mod_authors_csv(
            app_paths.authors_csv)
        self.mod_manager_model.experimental_find_mod_authors()

    @Slot()
    def _on_migrate_to_profiles_clicked(self):
        try:
            if self.mod_manager_model.experimental_migrate_to_profiles():
                self.view.show_notification(
                    "Success", 
                    "All mod states were successfully migrated to the Default profile."
                )
            else:
                self.view.show_notification(
                    "Migration Skipped",
                    "Migration was not needed or the data file was not found.",
                    "info"
                )
        except Exception as error:
            print(f"Migration Error: {error}") 
            self.view.show_notification(
                "Error", 
                "An unexpected error occurred during migration.", 
                "error"
            )

    @Slot(str)
    def _validate_config_game_directory(self, path: str) -> None:
        if not self.mod_manager_model.check_game_directory(path):
            self.view.show_notification(
                self.tr("Game Not Detected"),
                self.tr("'BrownDust II.exe' is missing from the selected folder. Make sure you've picked the correct installation path."),
                "error",
                5000,
            )
            return

        self.config_controller.set_game_directory(path)

    @Slot(str)
    def _on_mod_preview_requested(self, mod_name: str):

        mod = self.mod_manager_model.get_mod_by_name(mod_name)

        if not mod:
            return self.view.show_notification("Mod Not Found", f"Mod with the name '{mod_name}' was not found.", "error")
    
        self.mod_preview.launch_preview(mod.path)
    
    @Slot(str)
    def _on_mod_preview_error(self, message: str):
        self.view.show_notification("Mod Preview Error", message, "error")

        # if not hasattr(self, "spine_web"):
        #     return

        # mod = self.mod_manager_model.get_mod_by_name(mod_name)

        # if not mod:
        #     return self.view.show_notification("Mod Not Found", f"Mod with the name '{mod_name}' was not found.", "error")

        # self.spine_web.load_from_path(mod.path)
        # self.view.change_navigation_page("viewer")

    # --- Private Methods
    def _check_game_directory(self) -> None:
        game_dir = self.mod_manager_model.game_directory

        if self.config_model.get("bypass_path", value_type=bool):
            return

        if not game_dir or not self.mod_manager_model.check_game_directory(
            str(game_dir)
        ):
            game_path_located = self.mod_manager_model.locate_game()
            return self.view.show_game_directory_selection_page(game_path_located)

    def _refresh_profiles_dropdown(self) -> None:
        profiles = self.profile_manager_model.get_profiles()
        self.view.update_profiles(profiles)

    # --- Public Methods
    def show(self) -> None:
        self.view.show()

    def apply_stylesheet(self, theme: str) -> None:
        current_theme = ThemeManager.themes.get(theme)

        if not current_theme:
            logger.warning(f"Theme '{theme}' not found.")
            if ThemeManager.themes:
                try:
                    themes = ThemeManager.themes
                    theme = themes[list(themes.keys())[0]].get("name")
                    self.apply_stylesheet(theme)
                except IndexError:
                    pass
            return
        
        theme_path = current_theme.get("style_path")
        
        if not theme_path:
            return logger.error(f"Path of theme '{theme}' was not found.")
        
        
        logger.info(f"Applying stylesheet for theme '{theme}' from: {theme_path}")
        
        try:
            with open(theme_path, "r", encoding="utf-8") as f:
                stylesheet = f.read()
                self.view.setStyleSheet(stylesheet)
                ThemeManager.set_theme(theme)
            self.view.updateIcons()
            logger.info(f"Successfully applied stylesheet for theme: {theme}")
            
            # TODO: quick hack
            if self.config_model.theme != theme:
                self.config_model.set_theme(theme)
        except Exception as e:
            logger.error(
                f"Failed to apply stylesheet from {path}: {e}", exc_info=True)
            self.view.show_notification(
                title=self.tr("Theme Error"),
                text=self.tr(f"Failed to apply the '{theme}' theme. Please check the logs."),
                type="error",
                duration=5000  # 5 seconds
            )

    def apply_language(self, language: str) -> None:
        language_path = (
                app_paths.source_path
                / "translations"
                / (language + ".qm")
        )
        
        if language == "en-US":
            QApplication.instance().removeTranslator(QTranslator())
            self.view.retranslateUI()
            logger.info("Switched to default language (English).")
            return
        
        if not language_path.exists():
            return logger.error(f"Path of language '{language}' not found.")
        
        logger.info(f"Applying language '{language}' from: {language_path}")
        
        translator = QTranslator()
        if translator.load(language_path.as_posix()):
            QApplication.instance().installTranslator(translator)
            self.view.retranslateUI()
            logger.info(f"Successfully applied language: {language}")
        else:
            logger.warning(
                f"Failed to load translation for '{language}' from path: {language_path}"
            )