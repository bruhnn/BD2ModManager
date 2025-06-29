from PySide6.QtCore import Qt, Signal
import json
from PySide6.QtGui import QKeyEvent
from typing import Optional
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
)


class ProgressModal(QDialog):
    cancelled = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setObjectName("progressModal")

        # --- Main Layout ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # --- Widgets ---
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
        layout.addWidget(self.status_label)
        layout.addSpacing(10)
        layout.addWidget(self.button_stack)

        self.hide()

    def _setup_buttons(self) -> None:
        in_progress_widget = QWidget()
        progress_layout = QHBoxLayout(in_progress_widget)
        progress_layout.setContentsMargins(0, 0, 0, 0)

        self.cancel_button = QPushButton("Wait!", self)
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
                40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
            )
        )

        finished_widget = QWidget()
        finished_layout = QHBoxLayout(finished_widget)
        finished_layout.setContentsMargins(0, 0, 0, 0)

        self.close_button = QPushButton("Close", self)
        self.close_button.setObjectName("progressModalButton")
        self.close_button.clicked.connect(self.accept)

        finished_layout.addSpacerItem(
            QSpacerItem(
                40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
            )
        )
        finished_layout.addWidget(self.close_button)
        finished_layout.addSpacerItem(
            QSpacerItem(
                40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
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

    # def _request_cancel(self) -> None:
    #     """Handles the cancel request, emits the signal, and updates the UI."""
    #     self.cancel_button.setDisabled(True)
    #     self.cancel_button.setText("Cancelling...")
    #     self.status_label.setText("Cancellation requested, please wait...")
    #     self.cancelled.emit()

    def on_started(self, title: str) -> None:
        self.title_label.setText(title)
        self.status_label.setText("Initializing...")

        # Reset state
        self.progress_bar.setProperty("error", False)
        self.style().unpolish(self.progress_bar)  # Refresh style
        self.style().polish(self.progress_bar)

        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        # there's no cancel function
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("Wait!")
        self.button_stack.setCurrentIndex(0)  # Show Cancel button

    def on_finished(self, message: str) -> None:
        self.title_label.setText("Completed")
        # self.status_label.setText(message)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self.button_stack.setCurrentIndex(1)  # Show Close button

    def on_error(self, error_message: str) -> None:
        self.title_label.setText("An Error Occurred")
        self.status_label.setText(error_message)

        self.progress_bar.setProperty("error", True)
        self.style().unpolish(self.progress_bar)
        self.style().polish(self.progress_bar)

        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1) 
        self.button_stack.setCurrentIndex(1) 

    def update_progress(self, value: int, max_val: int, text: Optional[str] = None):
        print(f"Updating progress: {value}/{max_val} - {text if text else ''}")

        if self.progress_bar.maximum() != max_val:
            self.progress_bar.setMaximum(max_val)

        self.progress_bar.setValue(value)

        if text:
            self.status_label.setText(text)

    def set_indeterminate(self, status_text: str):
        self.progress_bar.setRange(0, 0)
        self.status_label.setText(status_text)


class EditModfileDialog(QDialog):
    def __init__(self, parent=None, title=None, data=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Modfile")

        self.modfile_data = data

        layout = QVBoxLayout(self)

        title = QLabel(text=title)
        self.error_label = QLabel()

        self.data_input = QTextEdit(json.dumps(data, indent=4, separators=(",", ": ")))
        self.data_input.setObjectName("editModFileData")

        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save)

        actions_layout.addWidget(save_btn)
        actions_layout.addWidget(close_btn)

        layout.addWidget(title)
        layout.addWidget(self.data_input, 1)
        layout.addWidget(self.error_label)
        layout.addWidget(actions_widget, alignment=Qt.AlignmentFlag.AlignRight)

    def save(self):
        # check if is a json valid
        data = None
        try:
            data = json.loads(self.data_input.toPlainText())
        except json.JSONDecodeError:
            self.error_label.setText("Invalid JSON!")
            return

        self.modfile_data = data

        self.accept()


class DropFilesWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.setObjectName("dropFilesModal")

        layout = QVBoxLayout()
        label = QLabel("Drop your mod files here to add them!")
        label.setObjectName("dropFilesTitle")

        layout.addWidget(label, 1, Qt.AlignmentFlag.AlignHCenter)

        # THIS WILL SHOW A LIST OF ALL THE MODS AND A BUTTON TO ADD, add all, etc.

        self.setLayout(layout)
