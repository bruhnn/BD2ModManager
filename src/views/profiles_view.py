from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QLineEdit, QTextEdit, QDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

from src.services.profiles import Profile


class ProfileDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Profile")
        self.setModal(True)

        # Widgets
        self.name_label = QLabel("Profile Name:")
        self.name_input = QLineEdit()

        self.desc_label = QLabel("Description:")
        self.desc_input = QTextEdit()
        self.desc_input.setFixedHeight(80)

        # Buttons
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")

        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        # Layouts
        layout = QVBoxLayout()
        layout.addWidget(self.name_label)
        layout.addWidget(self.name_input)
        layout.addWidget(self.desc_label)
        layout.addWidget(self.desc_input)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def get_data(self):
        return self.name_input.text().strip(), self.desc_input.toPlainText().strip()

class ProfilesView(QWidget):
    onSwitchProfileRequested = Signal(str)
    onCreateProfileRequested = Signal()
    
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        
        title = QLabel("Profiles")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        
        new_profile_btn = QPushButton("New Profile")
        new_profile_btn.clicked.connect(self.onCreateProfileRequested.emit)
        new_profile_btn.setIcon(QIcon(":/material/add.svg"))

        header_layout = QHBoxLayout()
        header_layout.addWidget(title, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(new_profile_btn)

        self.profile_list = QWidget()
        
        profile_list_layout = QVBoxLayout(self.profile_list)
        profile_list_layout.setSpacing(12)
        profile_list_layout.setContentsMargins(0, 0, 0, 0)
        
        layout.addLayout(header_layout, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.profile_list, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)


    def update_profiles(self, profiles: list[Profile]):
        for child in self.profile_list.findChildren(QWidget):
            child.deleteLater()
            
        for profile in profiles:
            profile_widget = QWidget()
            profile_layout = QHBoxLayout(profile_widget)
            profile_layout.setContentsMargins(8, 5, 8, 5)
            profile_layout.setSpacing(15)

            label = QLabel(profile.name)
            label.setStyleSheet("font-weight: 600; font-size: 14px;")

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)
            actions_layout.setSpacing(10)

            load_btn = QPushButton("Load")
            load_btn.setIcon(QIcon(":/material/wand_stars.svg"))
            load_btn.clicked.connect(lambda e, profile_id=profile.id: self.onSwitchProfileRequested.emit(profile_id))
            del_btn = QPushButton("Delete")
            del_btn.setIcon(QIcon(":/material/delete.svg"))

            actions_layout.addWidget(load_btn)
            actions_layout.addWidget(del_btn)

            profile_layout.addWidget(label)
            profile_layout.addStretch()
            profile_layout.addWidget(actions_widget)


            self.profile_list.layout().addWidget(profile_widget)
    
    def show_create_profile_modal(self):
        dialog = ProfileDialog(self)
        
        if dialog.exec():
            name, desc = dialog.get_data()
            return True, name, desc
        
        return False, None, None