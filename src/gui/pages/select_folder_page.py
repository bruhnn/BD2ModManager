from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


from typing import Optional, Union

from pathlib import Path


class SelectFolderPage(QWidget):
    onGameFolderSelected = Signal(str)

    def __init__(self, game_directory: Optional[Union[str, Path]] = None):
        super().__init__()

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.title = QLabel(
            text="Select <span style='color: #57886C'>Brown Dust 2</span> Directory"
        )
        self.title.setObjectName("title")
        self.title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))

        self.selection_widget = QWidget()
        self.selection_widget_layout = QHBoxLayout()
        self.selection_widget.setLayout(self.selection_widget_layout)
        self.selection_widget_layout.setContentsMargins(0, 0, 0, 0)
        self.selection_widget_layout.setSpacing(128)

        select_btn_font = QFont("Segoe UI", 14, QFont.Weight.Bold)

        self.find_game_button = QPushButton(text="Find Game")
        self.find_game_button.setFixedSize(150, 150)
        self.find_game_button.setFont(select_btn_font)
        self.find_game_button.setObjectName("selectButton")
        self.select_game_button = QPushButton(text="Select Game")
        self.select_game_button.setFixedSize(150, 150)
        self.select_game_button.setFont(select_btn_font)
        self.select_game_button.setObjectName("selectButton")
        self.select_game_button.clicked.connect(self._select_game_dialog)

        self.selection_widget_layout.addWidget(self.find_game_button)
        self.selection_widget_layout.addWidget(self.select_game_button)

        self.bottom_information_widget = QWidget()
        self.bottom_information_widget_layout = QHBoxLayout(
            self.bottom_information_widget
        )
        self.bottom_information_widget_layout.setContentsMargins(32, 0, 32, 32)

        self.bottom_info_left_widget = QWidget()
        self.bottom_info_left_widget_layout = QVBoxLayout(self.bottom_info_left_widget)
        self.bottom_info_left_widget_layout.setContentsMargins(0, 0, 0, 0)

        self.current_dir_label = QLabel(text="Current Directory:")
        self.current_dir_value = QLabel(text="Not Set")
        if game_directory:
            self.current_dir_value.setText(game_directory.as_posix())

        self.bottom_info_left_widget_layout.addWidget(self.current_dir_label)
        self.bottom_info_left_widget_layout.addWidget(self.current_dir_value)

        self.bottom_info_error_label = QLabel()
        self.bottom_info_error_label.setObjectName("errorText")

        self.bottom_info_skip_button = QPushButton("Skip")

        self.bottom_information_widget_layout.addWidget(
            self.bottom_info_left_widget, 0, Qt.AlignmentFlag.AlignLeft
        )
        self.bottom_information_widget_layout.addWidget(
            self.bottom_info_error_label, 0, Qt.AlignmentFlag.AlignHCenter
        )
        self.bottom_information_widget_layout.addWidget(
            self.bottom_info_skip_button, 0, Qt.AlignmentFlag.AlignRight
        )

        self.layout.addWidget(self.title, 0, Qt.AlignmentFlag.AlignHCenter)
        self.layout.addWidget(
            self.selection_widget,
            0,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
        )
        self.layout.addWidget(
            self.bottom_information_widget,
            0,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignBottom,
        )

        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet("""
        QLabel#title {
            color: #E0E1DD;
        }       
        
        QPushButton#selectButton {

        }
        
        QLabel#errorText {
            color: #ff0000
        }
        """)

    def _select_game_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Game Folder")

        if folder:
            self.onGameFolderSelected.emit(folder)

    def set_error_text(self, text: str):
        self.bottom_info_error_label.setText(text)
