import logging
import time
from typing import Optional
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow,
    QStackedWidget,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QComboBox,
    QFrame,
    QApplication,
)
from PySide6.QtCore import Qt, QSettings, QByteArray, Signal, QSize, QTranslator, Slot
from PySide6.QtGui import QCloseEvent

from src.version import __version__
from src.views.pages import SelectGameDirectory
from src.views.widgets import BaseButton, NavigationButton, PulsingLabel
from src.views.notification import NotificationsManager
from src.themes.theme_manager import ThemeManager
from src.models.profile_manager_model import Profile


logger = logging.getLogger(__name__)


class MainView(QMainWindow):
    appClosing = Signal(QCloseEvent)
    gameFolderSelected = Signal(str)

    launchGameRequested = Signal()

    profileChanged = Signal(Profile)
    newProfile = Signal(str)

    showProfilePageRequested = Signal()

    def __init__(self) -> None:
        super().__init__()
        start_time = time.perf_counter()  # Start timing
        logger.info("Initializing MainView")
        self.setWindowTitle(f"BD2 Mod Manager - v{__version__}")
        self.setObjectName("mainWindow")
        self.setGeometry(600, 250, 800, 600)

        self.settings = QSettings()

        self.main_stacked_widget = QStackedWidget()

        # Main Page - Full Page [Mods, Character --- Settings]
        self.main_page = QWidget()
        self.main_page_layout = QHBoxLayout(self.main_page)
        self.main_page_layout.setContentsMargins(*[0] * 4)
        self.main_page_layout.setSpacing(0)

        self.side_bar = QWidget()
        self.side_bar.setObjectName("sideBar")
        self.side_bar_layout = QVBoxLayout(self.side_bar)
        self.side_bar_layout.setContentsMargins(*[0] * 4)

        self.title_widget = QWidget()
        self.title_widget.setObjectName("titleWidget")
        self.title_widget_layout = QVBoxLayout(self.title_widget)
        self.title_widget_layout.setContentsMargins(32, 24, 32, 24)
        self.title_widget_layout.setSpacing(0)

        self.title_label = QLabel("BROWNDUST II")
        self.title_label.setObjectName("titleLabel")

        self.subtitle_label = QLabel(f"Mod Manager v{__version__}")
        self.subtitle_label.setObjectName("subtitleLabel")

        self.update_label = PulsingLabel(
            self.tr("New version v{version} available!").format(
                version="0.0.0")
        )
        self.update_label.setObjectName("updateLabel")
        self.update_label.setVisible(False)

        self.title_widget_layout.addWidget(
            self.title_label, 0, Qt.AlignmentFlag.AlignCenter
        )
        self.title_widget_layout.addWidget(
            self.subtitle_label, 1, Qt.AlignmentFlag.AlignCenter
        )
        self.title_widget_layout.addWidget(
            self.update_label, 1, Qt.AlignmentFlag.AlignCenter
        )

        self.navigation_bar_label = QLabel(self.tr("Navigation"))
        self.navigation_bar_label.setObjectName("navigationTitle")

        self.navigation_bar = QWidget()
        self.navigation_bar.setObjectName("navigationBar")
        self.navigation_bar_layout = QVBoxLayout(self.navigation_bar)
        self.navigation_bar_layout.setContentsMargins(8, 0, 8, 0)
        self.navigation_bar_layout.setSpacing(2)
        self.navigation_bar_layout.addWidget(self.navigation_bar_label)
        self.navigation_bar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.profile_widget = QWidget()
        self.profile_widget.setObjectName("profileWidget")
        self.profile_widget_layout = QVBoxLayout(self.profile_widget)
        self.profile_widget_layout.setContentsMargins(12, 12, 12, 12)

        self._previous_profile_index = 0

        self.profile_label = QLabel(self.tr("Profile"))
        self.profile_label.setObjectName("navigationTitle")

        self.profile_dropdown = QComboBox()
        self.profile_dropdown.currentIndexChanged.connect(
            self.on_profile_changed)
        # self.profile_dropdown.setItemIcon(self.profile_dropdown.count() - 1, QIcon(":/icons/material/build.svg"))
        self.profile_dropdown.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.profile_dropdown.setObjectName("profileDropdown")

        self.profile_widget_layout.addWidget(
            self.profile_label, 0, Qt.AlignmentFlag.AlignLeft
        )
        self.profile_widget_layout.addWidget(self.profile_dropdown, 0)

        self.start_game_widget = QWidget()
        self.start_game_layout = QVBoxLayout(self.start_game_widget)
        self.start_game_layout.setContentsMargins(32, 12, 32, 12)

        self.start_game_button = BaseButton(self.tr("Start BrownDust II"))
        self.start_game_button.setContentsMargins(0, 0, 0, 0)
        self.start_game_button.setObjectName("startGameButton")
        self.start_game_button.setToolTip(self.tr("Launch Brown Dust 2"))
        self.start_game_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_game_button.setIconSize(QSize(24, 24))
        self.start_game_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.start_game_button.setProperty("iconName", "play_arrow_fill")
        # self.start_game_button.setIcon(QIcon(f":/icons/material/dark/play_arrow_fill.svg"))
        self.start_game_button.setContentAlignmentCentered(True)
        self.start_game_button.setContentsMargins(16, 16, 16, 16)
        self.start_game_layout.addWidget(self.start_game_button)

        self.start_game_button.clicked.connect(self.launchGameRequested.emit)

        bline = QFrame()
        bline.setFrameShape(QFrame.Shape.HLine)
        bline.setFixedHeight(1)
        bline.setFrameShadow(QFrame.Shadow.Sunken)

        self.side_bar_layout.addWidget(
            self.title_widget,
            0,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
        )
        self.side_bar_layout.addWidget(self.navigation_bar, 1)
        self.side_bar_layout.addWidget(self.profile_widget)
        self.side_bar_layout.addWidget(bline)
        self.side_bar_layout.addWidget(self.start_game_widget)

        self.navigation_pages = {}

        self.navigation_view = QStackedWidget()
        self.navigation_view.setObjectName("navigationView")
        self.navigation_view.setContentsMargins(*[12] * 4)

        self.main_page_layout.addWidget(self.side_bar)
        self.main_page_layout.addWidget(self.navigation_view)

        self.main_stacked_widget.addWidget(self.main_page)

        # # Select Game Directory Page - Full Page []
        self.select_game_dir_page = SelectGameDirectory()
        self.select_game_dir_page.onGameFolderSelected.connect(
            self.gameFolderSelected.emit
        )

        self.main_stacked_widget.addWidget(self.select_game_dir_page)

        self.setCentralWidget(self.main_stacked_widget)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

        # needs to be after stylesheet is applied
        self.notifications = NotificationsManager(self)
        
        self._restore_geometry()

        load_time = (
            time.perf_counter() - start_time
        )

        logger.info(
            f"MainView initialized successfully in {load_time:.4f} seconds")

    # --- Events
    def closeEvent(self, event: QCloseEvent) -> None:
        logger.info("Close event triggered. Saving settings.")
        self.settings.setValue("mainWindow/geometry", self.saveGeometry())
        for view in self.navigation_view.findChildren(QWidget):
            if hasattr(view, "save_settings_state"):
                logger.debug(f"Saving settings for view: {view.objectName()}")
                view.save_settings_state()

        self.appClosing.emit(event)
        super().closeEvent(event)

    # --- Private Methods
    def _restore_geometry(self) -> None:
        logger.debug("Attempting to restore window geometry.")
        geometry = self.settings.value("mainWindow/geometry")
        if isinstance(geometry, QByteArray):
            self.restoreGeometry(geometry)
            logger.info("Window geometry restored.")
        else:
            logger.debug("No saved window geometry found.")

    def _update_navigation_buttons(self) -> None:
        for i in range(self.navigation_bar_layout.count()):
            widget = self.navigation_bar_layout.itemAt(i).widget()
            if isinstance(widget, NavigationButton):
                is_active = (
                    self.navigation_view.currentWidget()
                    == self.navigation_pages[widget.property("page")]
                )
                widget.set_active(is_active)
    # --- APP Methods

    def retranslateUI(self) -> None:
        self.setWindowTitle(
            self.tr("BD2 Mod Manager - v{version}").format(version=__version__)
        )

        self.update_label.setText(
            self.tr("New version v{version} available!").format(
                version=__version__)
        )
        self.navigation_bar_label.setText(self.tr("Navigation"))
        self.profile_label.setText(self.tr("Profile"))
        self.start_game_button.setText(self.tr("Start BrownDust II"))
        self.start_game_button.setToolTip(self.tr("Launch Brown Dust 2"))

        for button in self.navigation_bar.findChildren(NavigationButton):
            text = button.property("text")
            if text:
                button.setText(self.tr(text))

        for i in range(self.navigation_view.count()):
            widget = self.navigation_view.widget(i)
            if hasattr(widget, "retranslateUI"):
                widget.retranslateUI()

    def updateIcons(self) -> None:
        for btn in self.navigation_bar.findChildren(NavigationButton):
            btn.setIcon(ThemeManager.icon(btn.property("iconName")))

        self.start_game_button.setIcon(
            ThemeManager.icon(self.start_game_button.property("iconName"))
        )
        self.profile_dropdown.setItemIcon(
            self.profile_dropdown.count() - 1, ThemeManager.icon("build")
        )

        # update child icons
        for index in range(self.navigation_view.count()):
            view = self.navigation_view.widget(index)
            if hasattr(view, "updateIcons"):
                view.updateIcons()

    # --- Public Methods
    def add_page(self, name: str, view: QWidget) -> None:
        logger.info(f"Adding navigation page: {name}")
        self.navigation_pages[name] = view
        self.navigation_view.addWidget(view)

    def add_navigation_button(self, page: str, text: str, icon: str) -> None:
        logger.info(
            f"Adding navigation button for page: {page} with text: {text}")
        button = NavigationButton(text)
        button.setObjectName("navigationButton")
        button.setProperty("text", text)
        button.setProperty("index", self.navigation_view.count())
        button.setProperty("page", page)
        button.setProperty("iconName", icon)
        button.setIconSpacing(12)
        button.clicked.connect(lambda: self.change_navigation_page(page))
        self.navigation_bar_layout.addWidget(button)

        if self.navigation_view.count() == 1:
            button.set_active(True)
        else:
            self._update_navigation_buttons()

    def show_main_page(self) -> None:
        logger.info("Showing main page.")
        self.main_stacked_widget.setCurrentIndex(0)

    def show_game_directory_selection_page(self, game_path: str | None = None) -> None:
        logger.info("Showing game directory selection page.")
        if game_path is not None:
            self.select_game_dir_page.add_path(game_path)
        self.main_stacked_widget.setCurrentIndex(1)

    def change_navigation_page(self, page: str) -> None:
        if page not in self.navigation_pages:
            logger.error(f"Attempted to change to non-existent page: {page}")
            return

        if self.navigation_view.currentWidget() == self.navigation_pages[page]:
            return

        self.navigation_view.setCurrentWidget(self.navigation_pages[page])
        self._update_navigation_buttons()

    def set_update_available(self, version: str) -> None:
        self.update_label.setText(
            self.tr("New version v{version} available!".format(
                version=version))
        )
        self.update_label.setVisible(True)

    def update_profiles(self, profiles: list) -> None:
        logger.info(
            f"Updating profiles dropdown with {len(profiles)} profiles.")
        self._previous_profile_index = 0
        self.profile_dropdown.blockSignals(True)
        self.profile_dropdown.clear()

        for index, profile in enumerate(profiles):
            self.profile_dropdown.addItem(profile.name, profile)
            if profile.active:
                self.profile_dropdown.setCurrentIndex(index)
                logger.debug(
                    f"Set '{profile.name}' as active profile in dropdown.")

        self.profile_dropdown.addItem(
            ThemeManager.icon("build"), "Manage Profiles", "manage_profile"
        )
        self.profile_dropdown.blockSignals(False)
        logger.info("Profiles dropdown updated.")

    def set_game_directory_error(self, path: str, error_message: str) -> None:
        logger.warning(
            f"Setting game directory error for path '{path}': {error_message}")
        self.select_game_dir_page.set_folder_text(path)
        self.select_game_dir_page.set_info_text(error_message)

    def apply_stylesheet(self, theme: str, theme_path: str) -> None:
        path = Path(theme_path)
        
        # TODO: move this to controller
        
        logger.info(
            f"Applying stylesheet for theme '{theme}' from: {theme_path}")
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                stylesheet = f.read()
                self.setStyleSheet(stylesheet)
                ThemeManager.set_theme(theme)

            self.updateIcons()
            logger.info(f"Successfully applied stylesheet for theme: {theme}")
        except Exception as e:
            logger.error(
                f"Failed to apply stylesheet from {path}: {e}", exc_info=True)
            self.show_notification(
                title=self.tr("Theme Error"),
                text=self.tr(f"Failed to apply the '{theme}' theme. Please check the logs."),
                type="error",
                duration=5000  # 5 seconds
            )

    def apply_language(self, language: str, language_path: str) -> None:
        logger.info(f"Applying language '{language}' from: {language_path}")
        if language == "en-US":
            QApplication.instance().removeTranslator(QTranslator())
            self.retranslateUI()
            logger.info("Switched to default language (English).")
            return

        translator = QTranslator()
        if translator.load(language_path):
            QApplication.instance().installTranslator(translator)
            self.retranslateUI()
            logger.info(f"Successfully applied language: {language}")
        else:
            logger.warning(
                f"Failed to load translation for '{language}' from path: {language_path}"
            )

    def show_notification(
        self,
        title: Optional[str] = None,
        text: Optional[str] = None,
        type: str = "success",
        duration: int = 3000,
    ) -> None:
        logger.info(
            f"Showing '{type}' notification: Title='{title}', Text='{text}', Duration={duration}ms"
        )
        self.notifications.add_notification(
            title=title, description=text, notification_type=type, duration=duration
        )

    # --- Signals
    @Slot(int)
    def on_profile_changed(self, index: int) -> None:
        profile_data = self.profile_dropdown.itemData(index)

        if profile_data == "manage_profile":
            logger.info(
                "'Manage Profiles' selected. Emitting request to show profile page."
            )
            self.profile_dropdown.blockSignals(True)
            self.profile_dropdown.setCurrentIndex(self._previous_profile_index)
            self.profile_dropdown.blockSignals(False)
            self.showProfilePageRequested.emit()
            return

        self._previous_profile_index = index
        profile_id = profile_data.id if hasattr(
            profile_data, "id") else "Unknown"
        logger.info(
            f"Profile changed to: {self.profile_dropdown.itemText(index)} (ID: {profile_id})"
        )
        self.profileChanged.emit(profile_id)
