from PySide6.QtWidgets import QMainWindow, QStackedWidget, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QComboBox, QFrame
from PySide6.QtCore import Qt, QSettings, QByteArray, Signal, QTimer, QSize, QObject, QEvent
from PySide6.QtGui import QIcon, QColor, QPixmap, QFont, QFontDatabase
from typing import Optional



from pyqttoast import Toast, ToastPreset, ToastPosition


from src.version import __version__
from src.pages.select_game_directory import SelectGameDirectory
from src.widgets.widgets import CPushButton
from src.utils.paths import BUNDLE_PATH, CURRENT_PATH
from src.utils.theme_manager import ThemeManager


class MainWindowView(QMainWindow):
    onAppClose = Signal()
    onGameFolderSelected = Signal(str)
    
    launchGameRequested = Signal()

    def __init__(self, settings: QSettings):
        super().__init__()
        self.setWindowTitle("BD2 Mod Manager - v{version}".format(version=__version__))
        self.setObjectName("mainWindow")
        self.setGeometry(600, 250, 800, 600)

        self.settings = settings
        
        self.main_stacked_widget = QStackedWidget()

        # Home Page - Full Page [Mods, Character --- Settings]
        self.main_page = QWidget()
        self.main_page_layout = QHBoxLayout(self.main_page)
        self.main_page_layout.setContentsMargins(*[0]*4)
        self.main_page_layout.setSpacing(0)
        
        self.side_bar = QWidget()
        self.side_bar.setObjectName("sideBar")
        self.side_bar_layout = QVBoxLayout(self.side_bar)
        self.side_bar_layout.setContentsMargins(*[0]*4)

        self.title_widget = QWidget()
        self.title_widget.setObjectName("titleWidget")
        self.title_widget_layout = QVBoxLayout(self.title_widget)
        self.title_widget_layout.setContentsMargins(32, 24, 32, 24)
        self.title_widget_layout.setSpacing(0)
        
        # BD2Logo = QPixmap(r"C:\Users\dogui\Documents\CursorGithub\BD2ModManager\src\resources\assets\bd2logo_white_fantasy.png")
        # scaled_pixmap = BD2Logo.scaledToHeight(48, mode=Qt.TransformationMode.SmoothTransformation)
        self.title_img = QLabel("BROWNDUST II")
        self.title_img.setObjectName("titleImg")
        # self.title_img.setPixmap(scaled_pixmap)
        
        self.title_label = QLabel(f"Mod Manager v{__version__}")
        self.title_label.setObjectName("titleLabel")
        
        self.update_label = QLabel("New version v3.0.0 available!")
        self.update_label.setObjectName("updateLabel")
        # self.update_label.hide()
        
        self._create_pulsing_color()
        
        self.title_widget_layout.addWidget(self.title_img, 0, Qt.AlignmentFlag.AlignCenter)
        self.title_widget_layout.addWidget(self.title_label, 1, Qt.AlignmentFlag.AlignCenter)
        self.title_widget_layout.addWidget(self.update_label, 1, Qt.AlignmentFlag.AlignCenter)
        
        self.navigation_bar_label = QLabel("Navigation")
        self.navigation_bar_label.setObjectName("navigationTitle")
        self.navigation_bar = QWidget()
        self.navigation_bar.setObjectName("navigationBar")
        self.navigation_bar_layout = QVBoxLayout(self.navigation_bar)
        self.navigation_bar_layout.setContentsMargins(8, 0, 8, 0)
        self.navigation_bar_layout.setSpacing(2)
        self.navigation_bar_layout.addWidget(self.navigation_bar_label)
        self.navigation_bar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.settings_button = CPushButton("Settings")
        self.settings_button.setObjectName("navigationButton")
        # self.settings_button.setIcon(QIcon(f":/material/{ThemeManager.current_theme}/settings_fill.svg"))
        self.settings_button.setIconSpacing(12)
        self.settings_button.setToolTip("Settings")
                
        self.profile_widget = QWidget()
        self.profile_widget.setObjectName("profileWidget")
        self.profile_widget_layout = QVBoxLayout(self.profile_widget)
        self.profile_widget_layout.setContentsMargins(12, 12, 12, 12)
        
        self.profile_label = QLabel("Profile")
        self.profile_label.setObjectName("navigationTitle")
        
        self.profile_dropdown = QComboBox()
        self.profile_dropdown.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.profile_dropdown.setObjectName("profileDropdown")
        self.profile_dropdown.addItems([
            "Default",
            "Profile One",
            "Profile Two"
        ])
        # self.profile_dropdown.setEditable(True)
        # self.profile_dropdown.lineEdit().setReadOnly(True)
        # self.profile_dropdown.lineEdit().addAction(QIcon(":/material/star_fill.svg"), QLineEdit.ActionPosition.LeadingPosition)
        # self.profile_dropdown.lineEdit().installEventFilter(self)
        self.profile_dropdown.addItem("Manage Profiles")
        self.profile_dropdown.setItemIcon(self.profile_dropdown.count() - 1, QIcon(":/material/build.svg"))
        
        self.profile_widget_layout.addWidget(self.profile_label, 0, Qt.AlignmentFlag.AlignLeft)
        self.profile_widget_layout.addWidget(self.profile_dropdown, 0)
        
        self.start_game_widget = QWidget()
        self.start_game_layout = QVBoxLayout(self.start_game_widget)
        self.start_game_layout.setContentsMargins(32, 12, 32, 12)
        
        self.start_game_button = CPushButton(self.tr("Start BrownDust II"))
        self.start_game_button.setContentsMargins(0, 0, 0, 0)
        self.start_game_button.setObjectName("startGameButton")
        self.start_game_button.setToolTip(self.tr("Launch Brown Dust 2"))
        self.start_game_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_game_button.setIconSize(QSize(24, 24))
        self.start_game_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.start_game_button.setProperty("iconName", "play_arrow_fill")
        # self.start_game_button.setIcon(QIcon(f":/material/dark/play_arrow_fill.svg"))
        self.start_game_button.setContentAlignmentCentered(True)
        self.start_game_button.setContentsMargins(16, 16, 16, 16)
        self.start_game_layout.addWidget(self.start_game_button)
        
        self.start_game_button.clicked.connect(self.launchGameRequested.emit)
        
        bline = QFrame()
        bline.setFrameShape(QFrame.Shape.HLine)
        bline.setFixedHeight(1)
        bline.setFrameShadow(QFrame.Shadow.Sunken)

        self.side_bar_layout.addWidget(self.title_widget, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.side_bar_layout.addWidget(self.navigation_bar, 1)
        self.side_bar_layout.addWidget(self.profile_widget)
        self.side_bar_layout.addWidget(bline)
        self.side_bar_layout.addWidget(self.start_game_widget)
        
        self.navigation_view = QStackedWidget()
        self.navigation_view.setObjectName("navigationView")
        self.navigation_view.setContentsMargins(*[12]*4)
        
        self.main_page_layout.addWidget(self.side_bar)
        self.main_page_layout.addWidget(self.navigation_view)
        
        self.main_stacked_widget.addWidget(self.main_page)
        
        # # Select Game Directory Page - Full Page []
        self.select_game_dir_page = SelectGameDirectory()
        self.select_game_dir_page.onGameFolderSelected.connect(self.onGameFolderSelected)

        self.main_stacked_widget.addWidget(self.select_game_dir_page)

        self.setCentralWidget(self.main_stacked_widget)

        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

        self.restore_geometry()
    
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.profile_dropdown.lineEdit():
            if event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self.profile_dropdown.showPopup()
                    return True
        return super().eventFilter(watched, event)
    
    def add_navigation(self, text: str, view: QWidget, icon: str):
        button = CPushButton(text)
        button.setObjectName("navigationButton")
        button.setProperty("index", self.navigation_view.count())
        button.setProperty("iconName", icon)
        # button.setIcon(QIcon(icon))
        button.setIconSpacing(12)
        button.clicked.connect(lambda: self.change_navigation_page(self.navigation_view.indexOf(view)))
        
        self.navigation_bar_layout.addWidget(button)
        
        self.navigation_view.addWidget(view)

        if self.navigation_view.count() == 1:
            button.set_active(True)
        else:
            self._update_navigation_buttons()
    
    def set_settings_view(self, view: QWidget):
        self.navigation_view.addWidget(view)
        index = self.navigation_view.indexOf(view)
        self.settings_button.setProperty("index", index)
        self.settings_button.setProperty("iconName", "settings_fill")
        self.settings_button.clicked.connect(lambda: self.change_navigation_page(self.settings_button.property("index")))
        
        self.navigation_bar_layout.addWidget(self.settings_button)

    def _create_pulsing_color(self):
        self.brightness = 0.5
        self.is_increasing = False
        self.timer = QTimer()
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._update_pulsing_color)
        self.timer.start()

    def _update_pulsing_color(self):
        step = 0.01
        if self.is_increasing:
            self.brightness += step
            if self.brightness >= 1.0:
                self.brightness = 1.0
                self.is_increasing = False
        else:
            self.brightness -= step
            if self.brightness <= 0.5:
                self.brightness = 0.5
                self.is_increasing = True

        color = QColor("#34d399")
        color.setAlphaF(self.brightness) 

        self.update_label.setStyleSheet(f"color: rgba({color.red()}, {color.green()}, {color.blue()}, {color.alphaF()});")

    def show_main_page(self):
        self.main_stacked_widget.setCurrentIndex(0)

    def show_game_directory_selection_page(self):
        self.main_stacked_widget.setCurrentIndex(1)

    def change_navigation_page(self, index: int):
        self.navigation_view.setCurrentIndex(index)
        self._update_navigation_buttons()

    def set_game_directory_error(self, path: str, error_message: str):
        self.select_game_dir_page.set_folder_text(path)
        self.select_game_dir_page.set_info_text(error_message)
    
    def updateIcons(self):
        # update nav icons
        for btn in self.navigation_bar.findChildren(CPushButton):
            btn.setIcon(ThemeManager.icon(btn.property("iconName")))
        
        self.start_game_button.setIcon(ThemeManager.icon(self.start_game_button.property("iconName")))
        
        # update child icons
        for index in range(self.navigation_view.count()):
            view = self.navigation_view.widget(index)
            if hasattr(view, "updateIcons"):
                view.updateIcons()

    def apply_stylesheet(self, theme: str):
        path = BUNDLE_PATH / "resources" / "styles" / f"{theme}.qss"

        if not path.exists():
            path = BUNDLE_PATH / "resources" / "styles" / "dark.qss"

        try:
            with path.open("r", encoding="utf-8") as f:
                stylesheet = f.read()
                self.setStyleSheet(stylesheet)
                ThemeManager.set_theme(theme)

            # Update all icons
            self.updateIcons()
        except Exception:
            pass
        
    def restore_geometry(self):
        geometry = self.settings.value("mainWindow/geometry")
        if isinstance(geometry, QByteArray):
            self.restoreGeometry(geometry)

    def closeEvent(self, event):
        self.onAppClose.emit()
        
        self.settings.setValue("mainWindow/geometry", self.saveGeometry())
        return super().closeEvent(event)

    def _update_navigation_buttons(self):
        for i in range(self.navigation_bar_layout.count()):
            button = self.navigation_bar_layout.itemAt(i).widget()
            if isinstance(button, CPushButton):
                is_active = self.navigation_view.currentIndex() == button.property("index")
                button.set_active(is_active)
        
        is_settings_active = self.settings_button.property("index") == self.navigation_view.currentIndex()
        self.settings_button.setProperty("active", is_settings_active)
        self.settings_button.style().unpolish(self.settings_button)
        self.settings_button.style().polish(self.settings_button)

    def set_navigation_views(self, mods_view, characters_view, profiles_view, config_view):
        self.navigation_view.addWidget(mods_view)
        self.navigation_view.addWidget(characters_view)
        self.navigation_view.addWidget(profiles_view)
        self.navigation_view.addWidget(config_view)

    def change_nav_page(self, index: int):
        self.navigation_view.setCurrentIndex(index)
        self._update_navigation_buttons()

    # def _apply_language(self, language: str):
    #     if language == "english":
    #         QApplication.instance().removeTranslator(QTranslator())
    #         self.retranslateUI()
    #         return

    #     translator = QTranslator()

    #     if translator.load((BUNDLE_PATH / "resources" / "translations" / f"{language}.qm").as_posix()):
    #         QApplication.instance().installTranslator(translator)
    #         self.retranslateUI()
    #     else:
    #         print(f"Translation for {language} not found.")

    def show_toast(self, title: Optional[str] = None, text: Optional[str] = None, type: Optional[str] = None, duration: int = 3000):
        types = {
            "success": ToastPreset.SUCCESS_DARK,
            "error": ToastPreset.ERROR_DARK
        }
        
        toast = Toast(self)
        toast.setDuration(duration)
        if title:
            toast.setTitle(title)
        if text:
            toast.setText(text)
            
        toast.applyPreset(types.get(type, ToastPreset.SUCCESS_DARK))
        toast.setPositionRelativeToWidget(self.main_stacked_widget)
        toast.setShowDurationBar(False)
        toast.setPosition(ToastPosition.TOP_RIGHT)

        toast.setResetDurationOnHover(False)
        toast.setBackgroundColor(QColor("#1C1D21"))
        toast.setTitleColor(QColor("#ecf0f1"))
        toast.show()