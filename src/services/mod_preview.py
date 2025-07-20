import logging
import subprocess

from src.utils.paths import app_paths

from PySide6.QtCore import QObject, Signal


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# this is the best way to handle spine animations
# python does not have a spine runtime 
# and using qtwebengine makes the app bigger ~+100MB and makes it slower because of the chromium
class BD2ModPreview(QObject):
    errorOccurred = Signal(str)
    
    def __init__(self) -> None:
        super().__init__()
        self.refresh_path()
        
    def refresh_path(self):
        # if it has a updated version in user's path
        self._tool_path = app_paths.user_tools_path / "BD2ModPreview.exe"
        
        # fallback: to bundled mod preview
        if not self._tool_path.is_file():
            self._tool_path = app_paths.tools_path / "BD2ModPreview.exe"
    
    def get_version(self) -> str | None:
        try:
            result = subprocess.run(
                [str(self._tool_path), "--version"],
                capture_output=True,
                text=True,
                timeout=3
            )
            version = result.stdout.strip()
            return version if version else None
        except Exception as error:
            logger.warning(f"Error checking Mod Preview version", exc_info=error)
            return None
    
    def launch_preview(self, path: str) -> None:
        if not self._tool_path.exists():
            return self.errorOccurred.emit("BD2ModPreview.exe not found. Please update or reinstall the tool.")
        
        try:
            subprocess.Popen([self._tool_path.as_posix(), path])
        except Exception as error:
            logger.error(f"An error occurred while launching BD2ModPreview", exc_info=error)
            self.errorOccurred.emit(f"An error occurred while launching BD2ModPreview: {error}")