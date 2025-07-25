import logging
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QWidget,
    QHBoxLayout,
    QDialog,
    QVBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QHBoxLayout,
    QWidget,
    QStackedWidget,
    QSpacerItem,
    QSizePolicy,
    QScrollArea,
    QTextBrowser,
    QCheckBox,
    QGridLayout,
    QToolButton
)

from typing import Optional
import json

from src.themes import ThemeManager
import webbrowser

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class ProgressModal(QDialog):
    cancelled = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setObjectName("progressModal")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        self.title_label = QLabel(self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setObjectName("progressModalTitleLabel")
        self.title_label.setWordWrap(True)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setObjectName("progressModalProgressBar")

        self.status_label = QLabel(self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setObjectName("progressModalStatusLabel")
        self.status_label.setWordWrap(True)

        self.button_stack = QStackedWidget(self)
        self._setup_buttons()

        layout.addWidget(self.title_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label, 1)
        layout.addSpacing(10)
        layout.addWidget(self.button_stack)

        self.hide()

    def _setup_buttons(self) -> None:
        in_progress_widget = QWidget()
        progress_layout = QHBoxLayout(in_progress_widget)
        progress_layout.setContentsMargins(0, 0, 0, 0)

        self.cancel_button = QPushButton(self.tr("Wait!"), self)
        self.cancel_button.setObjectName("progressModalCancelButton")
        self.cancel_button.setEnabled(False)
        # self.cancel_button.clicked.connect(self._request_cancel)

        progress_layout.addSpacerItem(
            QSpacerItem(
                40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
            )
        )
        progress_layout.addWidget(self.cancel_button)
        progress_layout.addSpacerItem(
            QSpacerItem(
                40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
            )
        )

        finished_widget = QWidget()
        finished_layout = QHBoxLayout(finished_widget)
        finished_layout.setContentsMargins(0, 0, 0, 0)

        self.close_button = QPushButton(self.tr("Close"), self)
        self.close_button.setObjectName("progressModalButton")
        self.close_button.clicked.connect(self.accept)

        finished_layout.addSpacerItem(
            QSpacerItem(
                40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
            )
        )
        finished_layout.addWidget(self.close_button)
        finished_layout.addSpacerItem(
            QSpacerItem(
                40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
            )
        )

        self.button_stack.addWidget(in_progress_widget)  # Index 0
        self.button_stack.addWidget(finished_widget)  # Index 1

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            if self.button_stack.currentIndex() == 0 and self.cancel_button.isEnabled():
                pass
                # self._request_cancel()
            return
        super().keyPressEvent(event)

    def on_started(self, title: str) -> None:
        self.adjustSize()
        self.setMinimumWidth(int(self.parent().width() * 0.6))
        self.adjustPosition(self.parent())

        self.title_label.setText(title)
        self.status_label.setText(self.tr("Initializing..."))

        # Reset state
        self.progress_bar.setProperty("error", False)
        self.style().unpolish(self.progress_bar)  # Refresh style
        self.style().polish(self.progress_bar)

        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        # currently there's no cancel function
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("Wait!")
        self.button_stack.setCurrentIndex(0)  # Show Cancel button

    def on_finished(self, message: str) -> None:
        self.title_label.setText(message)
        # self.status_label.setText(message)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self.button_stack.setCurrentIndex(1)  # Show Close button

    def on_error(self, error_message: str) -> None:
        self.title_label.setText(self.tr("An Error Occurred"))
        self.status_label.setText(error_message)

        self.progress_bar.setProperty("error", True)
        self.style().unpolish(self.progress_bar)
        self.style().polish(self.progress_bar)

        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self.button_stack.setCurrentIndex(1)

    def update_progress(self, value: int, max_val: int, text: Optional[str] = None):
        if self.progress_bar.maximum() != max_val:
            self.progress_bar.setMaximum(max_val)

        self.progress_bar.setValue(value)

        if text:
            self.status_label.setText(text)

        # self.adjustSize()

    def set_indeterminate(self, status_text: str):
        self.progress_bar.setRange(0, 0)
        self.status_label.setText(status_text)


class EditModfileDialog(QDialog):
    def __init__(self, parent=None, title=None, data=None) -> None:
        super().__init__(parent)
        self.setObjectName("editModfileDialog")
        self.setWindowTitle(self.tr("Edit .modfile"))

        self.modfile_data = data

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title_label = QLabel(text=title)
        title_label.setObjectName("editModfileDialogTitle")

        self.error_label = QLabel()
        self.error_label.setObjectName("editModfileErrorLabel")
        self.error_label.setVisible(False)

        self.data_input = QTextEdit(json.dumps(data, indent=4))
        self.data_input.setObjectName("editModFileData")
        self.data_input.setFontFamily("Courier New")

        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(10)

        close_btn = QPushButton(self.tr("Close"))
        close_btn.setObjectName("editModfileCloseButton")
        close_btn.clicked.connect(self.reject)

        save_btn = QPushButton(self.tr("Save"))
        save_btn.setObjectName("editModfileSaveButton")
        save_btn.clicked.connect(self.save)

        actions_layout.addWidget(save_btn)
        actions_layout.addWidget(close_btn)

        layout.addWidget(title_label)
        layout.addWidget(self.data_input, 1)
        layout.addWidget(self.error_label)
        layout.addWidget(actions_widget, alignment=Qt.AlignmentFlag.AlignRight)

    def save(self):
        self.error_label.setVisible(False)
        data = None
        try:
            data = json.loads(self.data_input.toPlainText())
        except json.JSONDecodeError as e:
            self.error_label.setText(
                self.tr("Invalid JSON: {error}").format(error=e))
            self.error_label.setVisible(True)  # Show the error
            return

        self.modfile_data = data
        self.accept()


class DropFilesWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.setObjectName("dropFilesModal")

        layout = QVBoxLayout()
        label = QLabel(self.tr("Drop your mod files here to add them!"))
        label.setObjectName("dropFilesTitle")

        layout.addWidget(label, 1, Qt.AlignmentFlag.AlignHCenter)

        # THIS WILL SHOW A LIST OF ALL THE MODS AND A BUTTON TO ADD, add all, etc.

        self.setLayout(layout)


class UpdateModal(QDialog):
    # dontShowAgainChecked = Signal(bool, str) # dont show again, version

    def __init__(self, parent, current_version: str, new_version: str, changelog: str, releases_url: str):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setObjectName("UpdateModal")
        self.setFixedSize(650, 550)

        self.current_version = current_version
        self.new_version = new_version
        self.changelog = changelog
        self.releases_url = releases_url

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)

        header_widget = QWidget()
        header_layout = QGridLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        close_button = QToolButton()
        close_button.setObjectName("updateModalCloseButton")
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.setContentsMargins(0, 0, 0, 0)
        close_button.setIconSize(QSize(32, 32))
        close_button.setIcon(ThemeManager.icon("close"))
        close_button.clicked.connect(self._handle_close_modal)
        close_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        title_label = QLabel(self.tr("Update Available!"))
        title_label.setObjectName("updateModalTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        version_info_label = QLabel(
            self.tr("Version {new} is available. Current: {current}").format(
                new=new_version, current=current_version
            )
        )
        version_info_label.setObjectName("updateModalVersionInfo")
        version_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header_layout.setColumnStretch(0, 1)
        header_layout.setColumnStretch(1, 1)
        header_layout.setColumnStretch(2, 0)

        header_layout.addWidget(title_label, 0, 0, 1, 3)

        header_layout.addWidget(version_info_label, 1, 0, 1, 3)

        header_layout.addWidget(close_button, 0, 2)

        changelog_section_widget = QWidget()
        changelog_section_layout = QVBoxLayout(changelog_section_widget)
        changelog_section_layout.setContentsMargins(0, 0, 0, 0)
        changelog_section_layout.setSpacing(10)

        changelog_header = QLabel(self.tr("What's New:"))
        changelog_header.setObjectName("updateModalChangelogHeader")

        scroll_area = QScrollArea()
        scroll_area.setObjectName("updateModalChangelogScroll")
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        changelog_content = QTextBrowser()
        changelog_content.setObjectName("updateModalChangelogContent")
        changelog_content.setMarkdown(changelog)
        changelog_content.setOpenExternalLinks(True)

        scroll_area.setWidget(changelog_content)

        changelog_section_layout.addWidget(changelog_header)
        changelog_section_layout.addWidget(scroll_area)

        footer_widget = QWidget()
        footer_layout = QHBoxLayout(footer_widget)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(15)

        self.dont_show_again_checkbox = QCheckBox(self.tr("Don't show again"))
        self.dont_show_again_checkbox.setObjectName(
            "updateModalDontShowAgainCheckbox")

        later_button = QPushButton(self.tr("Later"))
        later_button.setCursor(Qt.CursorShape.PointingHandCursor)
        later_button.setObjectName("updateModalLaterButton")
        later_button.clicked.connect(self._handle_close_modal)

        download_button = QPushButton(self.tr("Go to Releases"))
        download_button.setCursor(Qt.CursorShape.PointingHandCursor)
        download_button.setObjectName("updateModalDownloadButton")
        download_button.clicked.connect(self._handle_download_click)
        download_button.setDefault(True)

        footer_layout.addWidget(self.dont_show_again_checkbox)
        footer_layout.addStretch()
        footer_layout.addWidget(later_button)
        footer_layout.addWidget(download_button)

        main_layout.addWidget(
            header_widget, alignment=Qt.AlignmentFlag.AlignTop)
        main_layout.addWidget(changelog_section_widget, 1)
        # main_layout.addStretch()
        main_layout.addWidget(footer_widget)

    def _handle_close_modal(self):
        # self.dontShowAgainChecked.emit(self.dont_show_again_checkbox.isChecked(), self.new_version)
        self.reject()

    def _handle_download_click(self):
        # self.dontShowAgainChecked.emit(self.dont_show_again_checkbox.isChecked(), self.new_version)
        try:
            webbrowser.open(self.releases_url)
        except Exception as error:
            logger.error("Failed to open github releases", exc_info=error)

        self.accept()

    def get_dont_show_again_state(self) -> tuple[bool, str]:
        return self.dont_show_again_checkbox.isChecked(), self.new_version
