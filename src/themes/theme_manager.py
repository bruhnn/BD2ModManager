from PySide6.QtGui import QColor, QPixmap, QPainter, QIcon, QAction
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QSize, Qt
from PySide6.QtSvg import QSvgRenderer

import json
from functools import singledispatchmethod

from src.utils.paths import app_paths


class ThemeManager:
    current_theme = "dark"
    DEFAULT_COLOR = "#FF00FF" 
    
    themes = {}
    _icon_cache = {}
    
    APP_THEMES_FOLDER = app_paths.source_path / "themes" 
    USER_THEMES_FOLDER = app_paths.user_data_path / "themes"

    @classmethod
    def load_themes(cls):
        cls.themes = {}
        theme_folders = [cls.APP_THEMES_FOLDER, cls.USER_THEMES_FOLDER]

        for folder in theme_folders:
            if not folder.exists():
                continue
            
            for theme_file in folder.glob("**/colors.json"):
                print(theme_file)
                if not (theme_file.parent / "theme.qss").exists():
                    continue
                
                try:
                    with open(theme_file, "r", encoding="UTF-8") as f:
                        theme_colors = json.load(f)
                        theme_name = theme_file.parent.name
                        cls.themes[theme_name] = {
                            "name": theme_name,
                            "style_path": str((theme_file.parent / "theme.qss").resolve()),
                            "colors": theme_colors
                        }
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Error loading theme file {theme_file}: {e}")
    
    @classmethod
    def get_available_themes(cls) -> list[str]:
        return list(cls.themes.keys())

    @classmethod
    def color(cls, key: str) -> QColor:
        color_hex = cls.themes.get(cls.current_theme, {}).get("colors", {}).get(key)
        if color_hex:
            return QColor(color_hex)
        print(f"Warning: Color key '{key}' not found in theme '{cls.current_theme}'.")
        return QColor(cls.DEFAULT_COLOR)

    @classmethod
    def set_theme(cls, theme_name: str):
        if theme_name in cls.themes and cls.current_theme != theme_name:
            cls.current_theme = theme_name
            cls._icon_cache.clear()
            print(f"Theme set to '{theme_name}'. Icon cache cleared.")
        elif theme_name not in cls.themes:
            print(f"Warning: Theme '{theme_name}' not found.")

    @singledispatchmethod
    @classmethod
    def icon(cls, icon_name: str, color_key: str = "icon_color") -> QIcon:
        cache_key = (icon_name, cls.current_theme, color_key)
        
        if cache_key in cls._icon_cache:
            return cls._icon_cache[cache_key]
        
        color_hex = cls.themes.get(cls.current_theme, {}).get("colors", {}).get(color_key)
        
        if color_hex:
            icon_path = f":/icons/material/base/{icon_name}.svg"
            generated_icon = cls._create_recolored_icon(icon_path, QColor(color_hex))
        else:
            icon_path = f":/icons/material/{cls.current_theme}/{icon_name}.svg"
            renderer = QSvgRenderer(icon_path)
            if not renderer.isValid():
                 print(f"Warning: Could not load fallback icon at path: {icon_path}")
                 generated_icon = QIcon() # Return empty icon
            else:
                 generated_icon = QIcon(icon_path)

        cls._icon_cache[cache_key] = generated_icon
        
        return generated_icon

    @icon.register
    @classmethod
    def _(cls, widget: QWidget, color_key: str = "icon_color") -> QIcon:
        icon_name = widget.property("iconName")
        if not icon_name:
            print(f"Warning: Widget {widget} does not have an 'iconName' property.")
            return QIcon()
        return cls.icon(icon_name, color_key)

    @icon.register
    @classmethod
    def _(cls, action: QAction) -> QIcon:
        icon_name = action.property("iconName")
        if not icon_name:
            print(f"Warning: Action {action.text()} does not have an 'iconName' property.")
            return QIcon()
        return cls.icon(icon_name)

    @classmethod
    def _create_recolored_icon(cls, icon_path: str, color: QColor, size=QSize(24, 24)) -> QIcon:
        renderer = QSvgRenderer(icon_path)
        if not renderer.isValid():
            print(f"Warning: Could not load icon for recoloring at path: {icon_path}")
            return QIcon()

        pixmap = QPixmap(size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        try:
            renderer.render(painter)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), color)
        finally:
            painter.end()  # Ensure cleanup even if exception occurs

        return QIcon(pixmap)
