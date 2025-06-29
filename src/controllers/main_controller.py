from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QCloseEvent

from src.controllers.profile_manager_controller import ProfileManagerController
from src.models import ConfigModel, ModManagerModel

from src.models import ProfileManager
from src.views import MainView, ModsView, ConfigView, CharactersView, ManageProfilesView
from src.controllers import CharactersController, ConfigController, ModManagerController
from src.services import BD2GameData, UpdateManager
from src.themes import ThemeManager
from src.spine_viewer import SpineViewerWidget

from src.utils.paths import app_paths
from src.utils.files import open_file_or_directory


class MainController(QObject):
    def __init__(
        self,
        view: MainView,
    ) -> None:
        super().__init__()

        self.view = view

        # to prevent update manager to trigger multiple notifications
        self._is_currently_updating = False

        self._setup_models()
        self._setup_views()
        self._setup_controllers()
        self._setup_signals()
        self._setup_navigation()
        self._setup_update_manager()
        self._setup_spine_viewer()

        # check if the game directory is stil valid, if not show the game selection page
        self._check_game_directory()
        self._refresh_profiles_dropdown()

        # Apply initial theme and language
        self._on_apply_stylesheet(self.config_model.theme)
        current_language = self.config_model.language
        self._on_apply_language(current_language)

    # --- Setups
    def _setup_models(self) -> None:
        self.config_model = ConfigModel(
            path=app_paths.app_path / "BD2ModManager.ini")

        self.game_data_model = BD2GameData(
            characters_csv=app_paths.characters_csv,
            datings_csv=app_paths.datings_csv
        )

        self.profile_manager_model = ProfileManager(
            profiles_directory=app_paths.profiles_path
        )

        staging_mods_dir = self.config_model.mods_directory

        if staging_mods_dir is None:
            staging_mods_dir = app_paths.app_path / "mods"

            self.config_model.set_mods_directory(
                str(staging_mods_dir.resolve()))

        self.mod_manager_model = ModManagerModel(
            game_data=self.game_data_model,
            profile_manager=self.profile_manager_model,
            staging_mods_directory=staging_mods_dir,
            mods_data_file=app_paths.user_data_path / "mods.json",
            game_directory=self.config_model.game_directory,
        )

        self.mod_manager_model.set_experimental_mod_authors_csv(
            app_paths.authors_csv)

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

        # View Signals
        self.view.appClosing.connect(self._on_app_close)
        self.view.gameFolderSelected.connect(self._on_game_directory_selected)
        self.view.launchGameRequested.connect(self._on_launch_game_requested)
        self.view.profileChanged.connect(self._profile_changed)
        self.view.showProfilePageRequested.connect(
            self._show_profile_page_requested)

        # Profile Signals
        self.profile_manager_model.profilesChanged.connect(
            self._refresh_profiles_dropdown
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
        self.view.add_navigation_stretch(1)
        self.view.add_navigation_button(
            "settings", self.tr("Settings"), "settings")

    def _setup_update_manager(self) -> None:
        self.update_manager = UpdateManager(
            manifest_url=self.config_model.manifest_url,
            releases_url=self.config_model.releases_url,
        )

        self.update_manager.appVersionAvailable.connect(
            self._on_app_new_version_available
        )
        self.update_manager.dataUpdateAvailable.connect(
            self._on_update_started)
        self.update_manager.assetUpdateAvailable.connect(
            self._on_update_started
        )  # Also trigger for assets
        self.update_manager.allDownloadsFinished.connect(
            self._on_all_updates_finished)
        self.update_manager.dataUpdated.connect(self._on_data_updated)
        self.update_manager.error.connect(self._on_update_error)
        self.update_manager.check_for_updates()

    def _setup_spine_viewer(self) -> None:
        if not self.config_model.spine_viewer_enabled:
            return

        self.spine_web = SpineViewerWidget(
            self.mod_manager_model.staging_mods_directory,
            self.view
        )

        self.view.add_page("viewer", self.spine_web)
        self.view.add_navigation_button(
            "viewer", self.tr("Viewer"), "view_list", 3)

        self.mod_manager_controller.modPreviewRequested.connect(
            self._on_mod_preview_requested
        )

    # --- Slots
    @Slot(str)
    def _on_app_new_version_available(self, version: str) -> None:
        self.view.set_update_available(version)
        self.view.show_notification(
            title=f"New version {version} available!",
            text="Visit the GitHub releases page to update.",
            duration=20000,
        )

    @Slot(str)
    def _on_update_started(self, key: str):
        if not self._is_currently_updating:
            self._is_currently_updating = True
            self.view.show_notification(
                title="Downloading new game data...",
                text="The application will update in the background.",
            )

    @Slot()
    def _on_all_updates_finished(self):
        if self._is_currently_updating:
            self.view.show_notification(
                title="Update Complete!",
                text="Game data has been successfully updated.",
                duration=4000,  # Shorter duration for success messages
            )
            self.mod_manager_model.refresh_game_data()

        self._is_currently_updating = False  # Reset the flag for the next check

    @Slot(str)
    def _on_update_error(self, error_message: str):
        self.view.show_notification(
            title="Update Failed",
            text="Could not download necessary data.",
            duration=10000,
        )
        print(f"UpdateManager Error: {error_message}")
        self._is_currently_updating = False

    @Slot(str)
    def _on_data_updated(self, key: str):
        print(f"Data for '{key}' updated, refreshing game data...")
        self.mod_manager_model.refresh_game_data()

    @Slot()
    def _on_app_close(self, event: QCloseEvent) -> None:
        self.mods_view.save_settings_state()
        event.accept()

    @Slot(str)
    def _on_apply_stylesheet(self, theme: str) -> None:
        current_theme = ThemeManager.themes.get(theme)

        if current_theme:
            self.view.apply_stylesheet(
                current_theme["name"], current_theme["style_path"])

    @Slot(str)
    def _on_apply_language(self, language: str) -> None:
        self.view.apply_language(
            language,
            str(
                app_paths.source_path
                / "resources"
                / "translations"
                / (language + ".qm")
            ),
        )

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
    def _show_profile_page_requested(self) -> None:
        print("ABCV")
        self.view.change_navigation_page("profiles")

    @Slot(str)
    def _validate_config_game_directory(self, path: str) -> None:
        if not self.mod_manager_model.check_game_directory(path):
            self.view.show_notification(
                self.tr("BrownDust II.exe not found in the selected directory."),
                None,
                "error",
                5000,
            )
            return

        self.config_controller.set_game_directory(path)

    @Slot(str)
    def _on_mod_preview_requested(self, mod_name: str):
        if not hasattr(self, "spine_web"):
            return

        mod = self.mod_manager_model.get_mod_by_name(mod_name)

        if not mod:
            return self.view.show_notification("Mod Not Found", f"Mod with the name '{mod_name}' was not found.", "error")

        self.spine_web.load_from_path(mod.path)
        self.view.change_navigation_page("viewer")

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
