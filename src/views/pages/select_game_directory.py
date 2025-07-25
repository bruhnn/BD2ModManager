from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QLineEdit,
    QListWidget,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal

from pathlib import Path


class SelectGameDirectory(QWidget):
    onGameFolderSelected = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*[64] * 4)
        layout.setSpacing(32)

        self.title = QLabel()
        self.title.setObjectName("selectTitle")

        self.selection_widget = QWidget()
        self.selection_widget_layout = QHBoxLayout(self.selection_widget)
        self.selection_widget_layout.setContentsMargins(0, 0, 0, 0)

        self.game_folder_label = QLineEdit()
        self.game_folder_label.setReadOnly(True)
        self.game_folder_label.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.game_folder_label.setObjectName("selectInput")

        self.browse_game_button = QPushButton()
        self.browse_game_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_game_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.browse_game_button.setObjectName("selectBrowseButton")
        self.browse_game_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )
        self.browse_game_button.clicked.connect(self._select_game_dialog)

        self.selection_widget_layout.addWidget(self.game_folder_label, 1)
        self.selection_widget_layout.addWidget(self.browse_game_button)

        self.path_list = QListWidget()
        self.path_list.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection)
        self.path_list.setObjectName("selectPathList")
        self.path_list.itemClicked.connect(self._path_clicked)

        self.info_text = QLabel()
        self.info_text.setObjectName("selectInfoText")

        layout.addWidget(self.title, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.selection_widget, 0)
        layout.addWidget(self.path_list, 1)
        layout.addWidget(
            self.info_text,
            0,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
        )

        # Initialize UI text
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.title.setText(
            self.tr("Select {game} Directory").format(
                game="<span style='color: #57886C'>Brown Dust 2</span>")
        )
        self.game_folder_label.setPlaceholderText(
            self.tr("Select BrownDust II.exe")
        )
        self.browse_game_button.setText(self.tr("Browse"))
        self.info_text.setText(
            self.tr("Please locate and select the BrownDust II.exe executable")
        )

    def _path_clicked(self, item) -> None:
        self.path_list.clearSelection()
        self.onGameFolderSelected.emit(item.text())

    def _select_game_dialog(self) -> None:
        current_path = Path(self.game_folder_label.text())
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select BrownDust II.exe"),
            str(current_path.resolve())
            if current_path.exists()
            else "",  # Start Browse in the last known directory
            "Executable files (*.exe)",
            # "BrownDust 2 Executable (BrownDust II.exe)" # doesnt work because of the space -> "browndust;ii.exe"
        )

        path = Path(file_path)

        if path.exists() and path.name.lower() == "BrownDust II.exe".lower():
            return self.onGameFolderSelected.emit(str(path.parent))

        if path.exists():
            if path.is_dir():
                self.game_folder_label.setText(str(path))
            else:
                self.game_folder_label.setText(str(path.parent))

        return self.info_text.setText(self.tr("Please select 'BrownDust II.exe'"))

    def set_folder_text(self, text: str) -> None:
        self.game_folder_label.setText(text)

    def set_info_text(self, text: str) -> None:
        self.info_text.setText(text)

    def add_path(self, path: str) -> None:
        self.path_list.addItem(path)