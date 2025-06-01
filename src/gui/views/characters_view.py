"""UI for displaying character costumes in a table view."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QLabel, QHBoxLayout, QSizePolicy, QLineEdit
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap


class CharactersView(QWidget):
    def __init__(self, characters: dict):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setObjectName("charactersView")

        # self.search_field = QLineEdit()
        # self.search_field.setPlaceholderText("Search characters...")
        # self.layout.addWidget(self.search_field)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("scrollArea")
        self.scroll_area.setWidgetResizable(True)

        self.character_list = QWidget()
        self.character_list_layout = QVBoxLayout()
        self.character_list_layout.setContentsMargins(0, 0, 0, 0)
        self.character_list.setLayout(self.character_list_layout)
        self.character_list_layout.setSpacing(16)

        self.scroll_area.setWidget(self.character_list)

        for char, costumes in characters.items():
            character_widget = CharacterWidget(
                character=char, costumes=costumes)
            self.character_list_layout.addWidget(character_widget, 1)

        self.layout.addWidget(self.scroll_area)

        self.setStyleSheet("""
            QLabel#characterLabel {
                font-size: 16px;
                font-weight: bold;
            }
            QLabel#costumeTitle {
                font-size: 16px;
                font-weight: bold;
            }
            QLabel#modStatusLabel {
                font-size: 14px;
                font-weight: bold;
            }
            QLabel#modStatusValue {
                color: #A0A0A0;
                font-size: 12px;
            }
            QLabel#modStatusValue[status="Installed"] {
                color: #57886C;
            }
            QLabel#modStatusValue[status="Not Installed"] {
                color: #DB5461;
            }
            QWidget#costumeWidget {
                background-color: #2E2E2E;
            }
            QWidget#costumeWidget QWidget, 
            QWidget#costumeWidget QLabel {
                background-color: #2E2E2E;
                
            }
        """)


class CharacterWidget(QWidget):
    def __init__(self, character: str, costumes: list):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(12)
        self.setObjectName("characterWidget")

        self.label = QLabel(text=f"{character} ({len(costumes)})")
        self.label.setObjectName("characterLabel")

        self.costume_list = QWidget()
        self.costume_list.setObjectName("costumeList")
        self.costume_list_layout = QVBoxLayout(self.costume_list)
        self.costume_list_layout.setContentsMargins(12, 0, 12, 0)
        self.costume_list_layout.setSpacing(16)

        for costume in costumes:
            costume_widget = CostumeWidget(costume)
            self.costume_list_layout.addWidget(
                costume_widget, 1)

        self.layout.addWidget(self.label)
        self.layout.addWidget(self.costume_list)


class CostumeWidget(QWidget):
    def __init__(self, costume: dict):
        super().__init__()
        self.setObjectName("costumeWidget")

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        pixmap = QPixmap(
            f"src/gui/resources/characters/{costume['character']['id']}.png")

        if pixmap.isNull():
            pixmap = QPixmap("src/gui/resources/characters/000101.png")

        pixmap = pixmap.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)

        self.char_image = QLabel()
        self.char_image.setObjectName("charImage")
        self.char_image.setPixmap(pixmap)

        self.information_widget = QWidget()
        self.information_widget.setObjectName("informationWidget")
        self.information_widget_layout = QVBoxLayout(self.information_widget)
        self.information_widget_layout.setContentsMargins(12, 6, 0, 6)
        self.information_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        self.mod_status_widget = QWidget()
        self.mod_status_widget_layout = QHBoxLayout(self.mod_status_widget)
        self.mod_status_widget_layout.setContentsMargins(0, 0, 0, 0)
        self.mod_status_widget_layout.addWidget(
            ModStatusWidget(
                "Cutscene", "Installed" if costume["cutscene"] else "Not Installed")
        )
        self.mod_status_widget_layout.addWidget(
            ModStatusWidget(
                "Idle", "Installed" if costume["idle"] else "Not Installed")
        )

        self.char_title = QLabel(
            text=f"{costume['character']['character']} - {costume['character']['costume']}")
        self.char_title.setObjectName("costumeTitle")

        self.information_widget_layout.addWidget(
            self.char_title, 0, Qt.AlignmentFlag.AlignTop
        )
        self.information_widget_layout.addWidget(
            self.mod_status_widget, 1, Qt.AlignmentFlag.AlignBottom
        )

        self.layout.addWidget(self.char_image)
        self.layout.addWidget(self.information_widget)


class ModStatusWidget(QWidget):
    def __init__(self, label: str, status: str):
        super().__init__()
        self.setObjectName("modStatusWidget")

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(text=label)
        self.label.setObjectName("modStatusLabel")

        self.status = QLabel(text=status)
        self.status.setObjectName("modStatusValue")
        self.status.setProperty("status", status)

        self.layout.addWidget(self.label)
        self.layout.addWidget(self.status)
