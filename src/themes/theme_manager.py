from PySide6.QtGui import QColor, QPixmap, QPainter, QIcon, QAction
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QSize, Qt
from PySide6.QtSvg import QSvgRenderer

from functools import singledispatchmethod


class ThemeManager:
    # Set the default theme to "light"
    current_theme = "light"

    THEMES = {
        "light": {
            "background": "#f9fafb",  # gray-50
            "sidebar": "#f3f4f6",  # gray-100
            "surface": "#ffffff",  # white
            "text_primary": "#1f2937",  # gray-800
            "text_secondary": "#6b7280",  # gray-500
            "color_primary": "#3b82f6",  # blue-500
            "color_secondary": "#ffffff",  # white (for text on primary color)
            "border": "#d1d5db",  # gray-300
            "hover": "#e5e7eb",  # gray-200
            "success": "#16a34a",  # green-600
            "icon_color": "#6b7280",
            "success": "#34d399",  # Success / Highlight
            "error": "#f87171",
            "info": "#60a5fa",
            "warning": "#f59e0b", 
        },
        "dark": {
            "background": "#111827",  # Background
            "sidebar": "#1f2937",  # Sidebar
            "surface": "#374151",  # Card / Surface
            # f0f0f0
            "text_primary": "#9ca3af",  # Primary Text
            "text_secondary": "#d1d5db",  # Secondary Text (inverted for dark)
            "color_primary": "#6b7280",  # Primary Color (Accent)
            "color_secondary": "#d1d5db",  # Secondary Color (Accent)
            "border": "#4b5563",  # Border
            "hover": "#374151",  # Hover
            
            "success": "#34d399",  # Success / Highlight
            "error": "#f87171",
            "info": "#60a5fa",
            "warning": "#f59e0b", 
            
        },
    }

    DEFAULT_COLOR = "#000"

    @classmethod
    def color(cls, key):
        color = cls.THEMES.get(cls.current_theme, {}).get(key, None)
        if color:
            return QColor(color)

        return QColor(cls.DEFAULT_COLOR)

    @classmethod
    def set_theme(cls, theme_name):
        if theme_name in cls.THEMES:
            cls.current_theme = theme_name

    @singledispatchmethod
    @classmethod
    def icon(cls, icon_name: str, color_key: str = "icon_color"):
        icon_color = cls.THEMES[cls.current_theme].get(color_key)
        if icon_color:
            return cls.recolored_icon(icon_name, icon_color)
        path = f":/material/{cls.current_theme}/{icon_name}.svg"
        return QIcon(path)

    @icon.register
    @classmethod
    def _(cls, widget: QWidget, color_key: str = "icon_color"):
        return cls.icon(widget.property("iconName"), color_key)

    @icon.register
    @classmethod
    def _(cls, action: QAction):
        return cls.icon(action.property("iconName"))

    @classmethod
    def recolored_icon(cls, icon_name, hex_color, size=QSize(24, 24)):
        path = f":/material/{cls.current_theme}/{icon_name}.svg"

        renderer = QSvgRenderer(path)

        pixmap = QPixmap(size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), hex_color)
        painter.end()

        return QIcon(pixmap)
