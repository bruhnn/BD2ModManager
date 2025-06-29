from PySide6.QtWidgets import (
    QPushButton,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QTextEdit,
    QLabel,
    QWidget,
    QListWidget,
    QListWidgetItem,
    QDialogButtonBox,
    QMessageBox,
    QStyledItemDelegate,
    QStyle,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPainter, QFontMetrics

from src.models.profile_manager_model import Profile
from src.themes.theme_manager import ThemeManager


class ProfileDialog(QDialog):
    def __init__(self, parent=None, name="", description="") -> None:
        super().__init__(parent)
        self.setMinimumWidth(450)
        self.setModal(True)
        self.setObjectName("profileDialog")

        self.profile_name = name
        self.profile_description = description

        self._setup_ui()

        self.name_input.setText(self.profile_name)
        self.description_input.setPlainText(self.profile_description)

        if name:
            self.setWindowTitle(self.tr("Edit Profile"))
            self.ok_button.setText(self.tr("Save Changes"))
        else:
            self.setWindowTitle(self.tr("Create New Profile"))
            self.ok_button.setText(self.tr("Create Profile"))

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        title_label_text = (
            self.tr("Edit Profile Details")
            if self.profile_name
            else self.tr("Create a New Profile")
        )
        title_label = QLabel(title_label_text)
        title_label.setObjectName("profileDialogTitle")
        layout.addWidget(title_label)

        name_label = QLabel(self.tr("Profile Name (Required)"))
        self.name_input = QLineEdit()
        self.name_input.setObjectName("profileInput")
        self.name_input.setPlaceholderText(self.tr("e.g., 'Nimloth's mods'"))
        self.name_input.textChanged.connect(self._update_button_state)
        layout.addWidget(name_label)
        layout.addWidget(self.name_input)
        layout.addSpacing(10)

        description_label = QLabel(self.tr("Description (Optional)"))
        self.description_input = QTextEdit()
        self.description_input.setObjectName("profileInput")
        self.description_input.setPlaceholderText("Description of the profile.")
        self.description_input.setMinimumHeight(60)
        layout.addWidget(description_label)
        layout.addWidget(self.description_input)

        button_box = QDialogButtonBox()
        self.ok_button = button_box.addButton(
            "Create", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.ok_button.setObjectName("profileButton")
        self.cancel_button = button_box.addButton(
            "Cancel", QDialogButtonBox.ButtonRole.RejectRole
        )
        self.cancel_button.setObjectName("profileButton")

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box, 0, Qt.AlignmentFlag.AlignRight)

        self._update_button_state()

    def _update_button_state(self) -> None:
        has_text = bool(self.name_input.text().strip())
        self.ok_button.setEnabled(has_text)

    def get_data(self) -> tuple[str, str]:
        return self.profile_name, self.profile_description

    def accept(self) -> None:
        self.profile_name = self.name_input.text().strip()
        self.profile_description = self.description_input.toPlainText().strip()
        super().accept()


class ProfileItemDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option, index) -> None:
        painter.save()

        profile = index.data(Qt.ItemDataRole.UserRole)
        if not profile:
            super().paint(painter, option, index)
            painter.restore()
            return

        name_color = ThemeManager.color("text_primary")
        desc_color = ThemeManager.color("text_secondary")

        # Check for Hover state first
        if option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(option.rect, ThemeManager.color("hover"))

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, ThemeManager.color("color_primary"))
            name_color = ThemeManager.color("color_secondary")
            desc_color = ThemeManager.color("color_secondary")
            desc_color.setAlpha(200)

        padding = 12
        line_spacing = 5
        content_rect = option.rect.adjusted(padding, padding, -padding, -padding)

        name_font = painter.font()
        name_font.setBold(True)
        painter.setFont(name_font)
        painter.setPen(name_color)
        painter.drawText(
            content_rect,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            profile.name,
        )

        desc_font = painter.font()
        desc_font.setBold(False)
        painter.setFont(desc_font)

        name_metrics = QFontMetrics(name_font)
        desc_rect = content_rect.adjusted(0, name_metrics.height() + line_spacing, 0, 0)

        painter.setPen(desc_color)

        elided_desc = painter.fontMetrics().elidedText(
            profile.description or self.tr("No description."),
            Qt.TextElideMode.ElideRight,
            desc_rect.width(),
        )
        painter.drawText(
            desc_rect,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            elided_desc,
        )

        painter.restore()

    def sizeHint(self, option, index) -> QSize:
        name_font = option.font
        name_font.setBold(True)
        name_metrics = QFontMetrics(name_font)

        desc_font = option.font
        desc_font.setBold(False)
        desc_metrics = QFontMetrics(desc_font)

        padding = 12
        line_spacing = 5

        height = (
            padding
            + name_metrics.height()
            + line_spacing
            + desc_metrics.height()
            + padding
        )

        return QSize(-1, height)


class ManageProfilesView(QWidget):
    addProfile = Signal(str, str)  # Name, Description
    deleteProfile = Signal(str)  # id
    editProfile = Signal(str, str, str)  # id, name, description

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("profilesPage")

        self.profiles = {}

        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        header_layout = QHBoxLayout()
        title = QLabel("Manage Profiles")
        title.setObjectName("profilesPageTitle")
        header_layout.addWidget(title)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        self.profile_list_widget = QListWidget()
        self.profile_list_widget.setObjectName("profilesList")
        self.profile_list_widget.itemSelectionChanged.connect(
            self._update_button_states
        )
        main_layout.addWidget(self.profile_list_widget)

        delegate = ProfileItemDelegate()
        self.profile_list_widget.setItemDelegate(delegate)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.edit_button = QPushButton("Edit Selected")
        self.edit_button.setObjectName("profilesPageButton")
        self.edit_button.clicked.connect(self.edit_profile)
        button_layout.addWidget(self.edit_button)

        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.setObjectName("profilesPageButton")
        self.delete_button.clicked.connect(self.delete_profile)
        button_layout.addWidget(self.delete_button)

        self.create_button = QPushButton("Create New Profile")
        self.create_button.setObjectName("profilesPageButton")
        self.create_button.clicked.connect(self.create_profile)
        button_layout.addWidget(self.create_button)
        main_layout.addLayout(button_layout)

        self._update_button_states()

    def refresh_profiles_list(self, profiles: list[Profile]) -> None:
        self.profile_list_widget.clear()
        self.profiles = {profile.id: profile for profile in profiles}
        for pid, profile in self.profiles.items():
            item = QListWidgetItem(pid)
            item.setData(Qt.ItemDataRole.UserRole, profile)
            self.profile_list_widget.addItem(item)
            self.profile_list_widget.addItem(item)

    def _update_button_states(self) -> None:
        selected_items = self.profile_list_widget.selectedItems()
        is_item_selected = bool(selected_items)

        if (
            len(selected_items) > 0
            and selected_items[0].data(Qt.ItemDataRole.UserRole).id == "default"
        ):
            self.edit_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            return

        self.edit_button.setEnabled(is_item_selected)
        self.delete_button.setEnabled(is_item_selected)

    def create_profile(self) -> None:
        dialog = ProfileDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, desc = dialog.get_data()
            if not name.strip():
                QMessageBox.warning(
                    self,
                    "Invalid Profile Name",
                    "Profile name cannot be empty.",
                )
                return
            self.addProfile.emit(name, desc)

    def edit_profile(self) -> None:
        selected_items = self.profile_list_widget.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        profile = item.data(Qt.ItemDataRole.UserRole)

        dialog = ProfileDialog(self, name=profile.name, description=profile.description)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_name, new_desc = dialog.get_data()
            
            if new_name == profile.name and new_desc == profile.description:
                return

            self.editProfile.emit(profile.id, new_name, new_desc)

    def delete_profile(self) -> None:
        selected_items = self.profile_list_widget.selectedItems()
        
        if not selected_items:
            return

        item = selected_items[0]
        profile = item.data(Qt.ItemDataRole.UserRole)

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete the profile '{profile.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.deleteProfile.emit(profile.id)
