from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class SettingsView(QWidget):
    def __init__(self):
        super().__init__()

        self.layout = QVBoxLayout(self)

        self.label = QLabel(text="Settings")

        self.layout.addWidget(self.label)
