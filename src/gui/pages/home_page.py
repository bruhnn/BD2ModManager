from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget, QHBoxLayout
from PySide6.QtCore import Qt, Signal

from ..widgets import NavButton
from ..views import SettingsView, ModsView


class HomePage(QWidget):
    onRefreshMods = Signal()
    onModsLoaded = Signal()
    onAddMod = Signal(str)
    onModStateChanged = Signal(str, bool)
    onSyncModsClicked = Signal()
    onUnsyncModsClicked = Signal()

    def __init__(self, mods: list):
        super().__init__()

        self.layout = QVBoxLayout(self)

        self.navigation_bar = QWidget()
        self.navigation_bar_layout = QHBoxLayout(self.navigation_bar)
        self.navigation_bar_layout.setContentsMargins(0, 0, 0, 0)

        self.nav_mods_button = NavButton("Mods")
        self.nav_chars_button = NavButton("Characters")
        self.nav_settings_button = NavButton("Settings")

        self.navigation_bar_layout.addWidget(
            self.nav_mods_button, 0, Qt.AlignmentFlag.AlignLeft
        )
        self.navigation_bar_layout.addWidget(
            self.nav_chars_button, 0, Qt.AlignmentFlag.AlignLeft
        )
        # self.navigation_bar_layout.addWidget(
        #     self.nav_scenes_button, 0, Qt.AlignmentFlag.AlignLeft
        # )
        self.navigation_bar_layout.addStretch()
        self.navigation_bar_layout.addWidget(
            self.nav_settings_button, 0, Qt.AlignmentFlag.AlignRight
        )

        self.navigation_view = QStackedWidget()

        self.mods_widget = ModsView()
        self.mods_widget.onRefreshMods.connect(self.onRefreshMods)
        self.mods_widget.onAddMod.connect(self.onAddMod)
        self.mods_widget.onModStateChanged.connect(self.onModStateChanged)
        self.mods_widget.onSyncModsClicked.connect(self.onSyncModsClicked)
        self.mods_widget.onUnsyncModsClicked.connect(self.onUnsyncModsClicked)
        self.mods_widget.load_mods(mods)

        self.settings_widget = SettingsView()

        self.navigation_view.addWidget(self.mods_widget)
        self.navigation_view.addWidget(self.settings_widget)

        self.nav_mods_button.clicked.connect(
            lambda: self.navigation_view.setCurrentIndex(0)
        )
        self.nav_chars_button.clicked.connect(
            lambda: self.navigation_view.setCurrentIndex(1)
        )
        self.nav_settings_button.clicked.connect(
            lambda: self.navigation_view.setCurrentIndex(2  )
        )

        self.layout.addWidget(self.navigation_bar)
        self.layout.addWidget(self.navigation_view)
