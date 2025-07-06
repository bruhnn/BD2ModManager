import subprocess

from src.utils.paths import app_paths

from PySide6.QtCore import QObject, Signal

class BD2ModPreview(QObject):
    errorOccurred = Signal(str)
    
    def __init__(self) -> None:
        super().__init__()
        
        self._tool_path = app_paths.user_tools_path / "BD2ModPreview.exe"
        
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
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
            print(f"Error checking mod preview version: {e}")
            return None
    
    def launch_preview(self, path: str) -> None:
        if not self._tool_path.exists():
            return self.errorOccurred.emit("BD2ModPreview.exe not found. Please update or reinstall the tool.")
        
        try:
            subprocess.Popen([self._tool_path.as_posix(), path])
        except Exception as e:
            self.errorOccurred.emit(f"An error occurred while launching BD2ModPreview: {e}")