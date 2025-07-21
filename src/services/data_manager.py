import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any
from packaging import version
import logging

from src.utils.paths import app_paths

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class DataManager:
    """
    Data initialization and validation at app startup
    
    """
    
    def __init__(self):
        self.bundled_manifest: Dict[str, Any] = {}
        self.user_manifest: Dict[str, Any] = {}
        
    def initialize_app_data(self) -> bool:
        try:
            self.maybe_update_preview_tool()
            
            # load and validate bundled manifest
            if not self._load_bundled_manifest():
                return False
                
            # load or create user manifest
            created_user_manifest = self._load_or_create_user_manifest()
            
            # check if manifest needs updating
            manifest_needs_update = self._check_manifest_update_needed()
            
            # handle data files
            if not self._handle_data_files((manifest_needs_update or created_user_manifest)):
                return False
                
            # save updated manifest
            return self._save_user_manifest()

        except Exception as e:
            logger.critical(f"Critical error during data initialization: {e}", exc_info=True)
            self._show_fatal_error(f"Failed to initialize application data: {e}")
            return False
    
    def _load_bundled_manifest(self) -> bool:
        try:
            with app_paths.default_manifest_v2_json.open("r", encoding="UTF-8") as f:
                self.bundled_manifest = json.load(f)
            
            required_keys = ["manifest_version", "data", "assets"]
            if not all(key in self.bundled_manifest for key in required_keys):
                raise ValueError("Bundled manifest missing required keys")
                
            logger.info(f"Loaded bundled manifest v{self.bundled_manifest['manifest_version']}")
            
            return True
            
        except Exception as e:
            logger.critical(f"Failed to load bundled manifest: {e}", exc_info=True)
            self._show_fatal_error(f"Bundled manifest error: {e}")
            return False
    
    def _load_or_create_user_manifest(self):
        created = False
        if not app_paths.manifest_v2_json.exists():
            logger.info("Creating new user manifest from bundled version")
            
            self.user_manifest = self.bundled_manifest.copy()
            created = True
        else:
            logger.info("Loading user manifest from User's AppData")

            try:
                with app_paths.manifest_v2_json.open("r", encoding="UTF-8") as f:
                    self.user_manifest = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load user manifest: {e}, recreating")
                self.user_manifest = self._create_default_user_manifest()
                created = True
                    
        # Validate
        if not self._validate_user_manifest():
            logger.warning("User manifest corrupted, recreating from bundled")
            self.user_manifest = self._create_default_user_manifest()
            created = True
        
        return created
                
    def _create_default_user_manifest(self) -> Dict[str, Any]:
        return {
            "manifest_version": self.bundled_manifest["manifest_version"],
            "data": {},
            "assets": {"version": "0.0.0", "characters": {}}
        }
    
    def _validate_user_manifest(self) -> bool:
        """Validate user manifest structure"""
        required_keys = ["manifest_version", "data", "assets"]
        return all(key in self.user_manifest for key in required_keys)
    
    def _check_manifest_update_needed(self) -> bool:
        """Check if user manifest needs updating from bundled version"""
        try:
            bundled_ver = version.parse(self.bundled_manifest["manifest_version"])
            user_ver = version.parse(self.user_manifest.get("manifest_version", "0.0.0"))
            
            if bundled_ver > user_ver:
                logger.info(f"Manifest update needed: {user_ver} -> {bundled_ver}")
                
                self.user_manifest["manifest_version"] = self.bundled_manifest["manifest_version"]
                
                # do i really need this?
                for file_key, file_info in self.bundled_manifest["data"].items():
                    if file_key not in self.user_manifest["data"]:
                        self.user_manifest["data"][file_key] = {"version": "0.0.0"}
                        
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error checking manifest versions: {e}")
            return True 
    
    def _handle_data_files(self, force_update: bool = False) -> bool:
        data_files = [
            ("characters.csv", app_paths.default_characters_csv, app_paths.characters_csv),
            ("authors.csv", app_paths.default_authors_csv, app_paths.authors_csv),
            ("datings.csv", app_paths.default_datings_csv, app_paths.datings_csv),
            ("npcs.csv", app_paths.default_npcs_csv, app_paths.npcs_csv)
        ]
        
        for file_key, default_path, user_path in data_files:
            try:
                if not self._handle_single_data_file(file_key, default_path, user_path, force_update):
                    return False
            except Exception as e:
                logger.critical(f"Failed to handle {file_key}: {e}", exc_info=True)
                self._show_fatal_error(f"Error with {file_key}: {e}")
                return False
                
        return True
    
    def _handle_single_data_file(self, file_key: str, default_path: Path, 
                                user_path: Path, force_update: bool) -> bool:
        
        user_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Get version 
        bundled_version_str = (self.bundled_manifest
                             .get("data", {})
                             .get(file_key, {})
                             .get("version", "0.0.0"))
        
        user_version_str = (self.user_manifest
                          .get("data", {})
                          .get(file_key, {})
                          .get("version", "0.0.0"))
        
        bundled_version = version.parse(bundled_version_str)
        user_version = version.parse(user_version_str)
        
        bundled_url = (self.bundled_manifest
                             .get("data", {})
                             .get(file_key, {})
                             .get("url"))

        bundled_hash = (self.bundled_manifest
                        .get("data", {})
                        .get(file_key, {})
                        .get("hash"))

        
        should_copy = (
            not user_path.exists() or 
            force_update or 
            user_version < bundled_version
        )
        
        if should_copy:
            logger.info(f"Updating {file_key}: v{user_version} -> v{bundled_version}")
            
            temp_path = user_path.with_suffix('.tmp')
            shutil.copy2(default_path, temp_path)
            shutil.move(temp_path, user_path)
            
            if "data" not in self.user_manifest:
                self.user_manifest["data"] = {}
                
            if file_key not in self.user_manifest["data"]:
                self.user_manifest["data"][file_key] = {}
                
            self.user_manifest["data"][file_key]["version"] = bundled_version_str
            self.user_manifest["data"][file_key]["url"] = bundled_url
            self.user_manifest["data"][file_key]["hash"] = bundled_hash
            
        return True
    
    def _save_user_manifest(self) -> bool:
        try:
            app_paths.manifest_v2_json.parent.mkdir(parents=True, exist_ok=True)
            
            temp_path = app_paths.manifest_v2_json.with_suffix('.tmp')
            with temp_path.open("w", encoding="UTF-8") as f:
                json.dump(self.user_manifest, f, indent=4)
            
            shutil.move(temp_path, app_paths.manifest_v2_json)
            logger.info("User manifest saved successfully")
            return True
            
        except Exception as e:
            logger.critical(f"Failed to save user manifest: {e}", exc_info=True)
            self._show_fatal_error(f"Cannot save manifest: {e}")
            return False
    
    def _show_fatal_error(self, message: str):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(
            None,
            "Fatal Initialization Error",
            f"{message}\n\n"
            "Please check file permissions or try running as administrator. "
            "The application will now exit."
        )
        sys.exit(1)

    def maybe_update_preview_tool(self):
        user_tool = app_paths.user_tools_path / "BD2ModPreview.exe"
        bundled_tool = app_paths.tools_path / "BD2ModPreview.exe"

        def get_tool_version(path: Path) -> str | None:
            try:
                result = subprocess.run([str(path), "--version"], capture_output=True, text=True, timeout=3)
                return result.stdout.strip() or None
            except Exception:
                return None

        user_ver = get_tool_version(user_tool)
        bundled_ver = get_tool_version(bundled_tool)

        if bundled_ver and (not user_ver or version.parse(bundled_ver) > version.parse(user_ver)):
            user_tool.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundled_tool, user_tool)
            logger.info(f"Updated BD2ModPreview in user path with bundled: {user_ver or 'none'} -> {bundled_ver}")