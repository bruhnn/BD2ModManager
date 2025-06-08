from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QLineEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


from typing import Optional, Union

from pathlib import Path


class SelectFolderPage(QWidget):
    onGameFolderSelected = Signal(str)

    def __init__(self, game_directory: Optional[Union[str, Path]] = None):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(64, 0, 64, 0)

        self.title = QLabel(text="Select <span style='color: #57886C'>Brown Dust 2</span> Directory")
        self.title.setObjectName("selectFolderTitle")
        self.title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))

        self.selection_widget = QWidget()
        self.selection_widget_layout = QHBoxLayout(self.selection_widget)
        self.selection_widget_layout.setContentsMargins(0, 0, 0, 0)

        select_btn_font = QFont("Segoe UI", 12, QFont.Weight.Bold)
        
        self.game_folder_label = QLineEdit(text="No game found!")
        self.game_folder_label.setReadOnly(True)
        self.game_folder_label.setObjectName("directoryInput")

        self.select_game_button = QPushButton("Browse")
        self.select_game_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_game_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.select_game_button.setObjectName("browseButton")
        self.select_game_button.setFont(select_btn_font)
        self.select_game_button.clicked.connect(self._select_game_dialog)

        self.selection_widget_layout.addWidget(self.game_folder_label, 1)
        self.selection_widget_layout.addWidget(self.select_game_button)
        
        info_text_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        self.info_text = QLabel()
        self.info_text.setObjectName("selectFolderInfoText")
        self.info_text.setFont(info_text_font)
        
        # When it shows this page, it starts searching the game
        # Show a list with the paths found.

        layout.addWidget(self.title, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.selection_widget, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.info_text, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)

    def _select_game_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Game Folder")

        if folder:
            self.onGameFolderSelected.emit(folder)

    def set_folder_text(self, text: str):
        self.game_folder_label.setText(text)
    
    def set_info_text(self, text: str):
        self.info_text.setText(text)