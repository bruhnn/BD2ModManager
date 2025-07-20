import hashlib
import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from packaging import version

from src.services.mod_preview import BD2ModPreview
from src.utils.files import get_file_hash
from src.utils.paths import app_paths
from src.version import __version__

logger = logging.getLogger(__name__)

class UpdateManager(QObject):
    appUpdateAvailable = Signal(str, str, str)

    # Signals for data files
    dataUpdateAvailable = Signal(str)  # key of the data file
    dataUpdated = Signal(str)  # key of the data file

    # Signals for asset files
    assetUpdateAvailable = Signal(str)  # key of the asset
    assetUpdated = Signal(str)  # key of the asset
    
    # Signals for tools
    toolUpdateAvailable = Signal(str)
    toolUpdated = Signal(str)

    updateCheckFinished = Signal()
    allDownloadsFinished = Signal()
    errorOccurred = Signal(str)

    def __init__(
        self, 
        manifest_url: str, 
        releases_url: str,
        modpreview_releases_url: str,
        parent: QObject | None = None
    ) -> None:
        super().__init__(parent)

        self._remote_manifest_url = manifest_url
        self._releases_url = releases_url
        self._network_manager = QNetworkAccessManager(self)

        self._remote_manifest_data: Dict[str, Any] = {}
        self._local_manifest_data = self._load_local_manifest()
        self._modpreview_releases_url = modpreview_releases_url
        
        self._active_downloads = 0

        logger.info("UpdateManager initialized.")

    def _load_local_manifest(self) -> Dict[str, Any]:
        """Loads the local manifest file. If it doesn't exist or is corrupted, returns a default manifest."""
        default_manifest = {"data": {}, "assets": {}}

        if not app_paths.manifest_v2_json.exists():
            logger.warning(
                "Local manifest not found at %s. A new one will be created.",
                app_paths.manifest_v2_json,
            )
            return default_manifest

        logger.debug("Loading local manifest from %s", app_paths.manifest_v2_json)
        
        try:
            with open(app_paths.manifest_v2_json, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "data" not in data or "assets" not in data:
                logger.error(
                    "Local manifest at %s is corrupted. A new one will be created.",
                    app_paths.manifest_v2_json,
                )
                self.errorOccurred.emit(
                    "Local manifest is corrupted. A new one will be created."
                )
                return default_manifest

            logger.debug("Local manifest loaded successfully.")
            return data
        except (json.JSONDecodeError, IOError) as e:
            logger.error("Could not read local manifest: %s", e)
            self.errorOccurred.emit(f"Could not read local manifest: {e}")
            return default_manifest

    def _save_local_manifest(self) -> None:
        """Saves the local manifest to a file atomically."""
        temp_path = None
        try:
            app_paths.manifest_v2_json.parent.mkdir(parents=True, exist_ok=True)

            logger.info("Saving local manifest to %s", app_paths.manifest_v2_json)

            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                delete=False,
                dir=app_paths.manifest_v2_json.parent,
                suffix=".tmp",
            ) as f:
                json.dump(self._local_manifest_data, f, indent=4)
                temp_path = Path(f.name)

            shutil.move(temp_path, app_paths.manifest_v2_json)
            logger.info("Local manifest saved successfully.")
        except (IOError, json.JSONDecodeError) as e:
            logger.error("Could not save local manifest: %s", e)
            self.errorOccurred.emit(f"Could not save local manifest: {e}")
            if temp_path and temp_path.exists():
                temp_path.unlink()

    def start_update_process(self) -> None:
        logger.info("Checking for updates...")
        self._get_remote_manifest()

    def check_app_version(self) -> None:
        """Checks for a new application version from the releases URL."""
        logger.info("Checking for new application version from %s", self._releases_url)
        request = QNetworkRequest(QUrl(self._releases_url))
        reply = self._network_manager.get(request)
        reply.finished.connect(self._on_app_version_received)
        
    @Slot()
    def _on_app_version_received(self) -> None:
        reply: QNetworkReply = self.sender()
        if reply.error() != QNetworkReply.NetworkError.NoError:
            logger.error("App version check failed: %s", reply.errorString())
            self.errorOccurred.emit(f"App version check failed: {reply.errorString()}")
        else:
            try:
                data = json.loads(reply.readAll().data())
                
                # finds the latest version that is not pre-release
                if data and isinstance(data, list):
                    latest_release = None
                    for release in data:
                        if not release["prerelease"]:
                            latest_release = release
                            break
                     
                    if not latest_release:
                        return logger.critical("Latest release not found.")
    
                    
                    latest_version = latest_release["tag_name"].lstrip("v")
                    
                    logger.info(
                        "Current version: %s, Latest version: %s",
                        __version__,
                        latest_version,
                    )
                    
                    if version.parse(__version__) < version.parse(latest_version):
                        body = latest_release["body"]
                        url = latest_release["html_url"]
                        logger.info(
                            "New application version available: %s", latest_version
                        )
                        self.appUpdateAvailable.emit(latest_version, body, url)
            except (json.JSONDecodeError, IndexError, KeyError) as e:
                logger.error("Failed to parse app version data: %s", e)
                self.errorOccurred.emit(f"Failed to parse app version data: {e}")
        reply.deleteLater()

    def _get_remote_manifest(self) -> None:
        logger.info("Fetching remote manifest from %s", self._remote_manifest_url)
        request = QNetworkRequest(QUrl(self._remote_manifest_url))

        # it doesn't work, i don't know why ):
        request.setAttribute(
            QNetworkRequest.Attribute.CacheLoadControlAttribute,
            QNetworkRequest.CacheLoadControl.AlwaysNetwork,
        )
        request.setAttribute(QNetworkRequest.Attribute.CacheSaveControlAttribute, False)
        request.setRawHeader(b"Cache-Control", b"no-cache, no-store, must-revalidate")
        request.setRawHeader(b"Pragma", b"no-cache")
        request.setRawHeader(b"Expires", b"0")

        reply = self._network_manager.get(request)
        reply.finished.connect(self._on_remote_manifest_received)

    @Slot()
    def _on_remote_manifest_received(self) -> None:
        reply: QNetworkReply = self.sender()

        if reply.error() != QNetworkReply.NetworkError.NoError:
            logger.error("Could not fetch remote manifest: %s", reply.errorString())
            self.errorOccurred.emit(f"Could not fetch remote manifest: {reply.errorString()}")
            self.updateCheckFinished.emit()
            reply.deleteLater()
            return

        try:
            self._remote_manifest_data = json.loads(reply.readAll().data())
            logger.debug("Remote manifest data loaded successfully.")
        except json.JSONDecodeError as e:
            logger.error("Failed to parse remote manifest: %s", e)
            self.errorOccurred.emit(f"Failed to parse remote manifest: {e}")
            self.updateCheckFinished.emit()
            reply.deleteLater()
            return
        finally:
            reply.deleteLater()

        self._compare_data_files()
        self._compare_character_assets()

        logger.info("Update check finished.")
        self.updateCheckFinished.emit()

        if self._active_downloads == 0:
            logger.info("No downloads required.")
            self.allDownloadsFinished.emit()

    def _compare_data_files(self) -> None:
        remote_data = self._remote_manifest_data.get("data", {})
        local_data_manifest = self._local_manifest_data.get("data", {})

        for key, remote_info in remote_data.items():
            local_info = local_data_manifest.get(key, {})
            
            local_version = version.parse(local_info.get("version"))
            remote_version = version.parse(remote_info.get("version"))
            
            logger.debug("Manifest [%s] => Local %s, Remote %s", key, local_version, remote_version)
            
            if local_version < remote_version:
                logger.info("Update available for data file: '%s'", key)
                self.dataUpdateAvailable.emit(key)
                self._download_file(key, remote_info, self._on_download_data_finished)

    def _compare_character_assets(self) -> None:
        remote_assets = self._remote_manifest_data.get("assets", {})
        local_assets = self._local_manifest_data.get("assets", {})
        
        # check if we need to update the assets manifest
        remote_version = version.parse(remote_assets.get("version", "0.0.0"))
        local_version = version.parse(local_assets.get("version", "0.0.0"))
        
        if remote_version > local_version:
            logger.info(f"Assets manifest updated from {local_version} to {remote_version}")
            
            remote_characters = remote_assets.get("characters", {})
            local_characters = local_assets.get("characters", {})
            
            removed_from_tracking = set(local_characters.keys()) - set(remote_characters.keys())
            if removed_from_tracking:
                logger.info(f"Removing {len(removed_from_tracking)} assets from manifest tracking: {removed_from_tracking}")
                logger.info("Note: Asset files remain in user directory, just no longer managed")
            
            self._local_manifest_data["assets"] = remote_assets.copy()

        remote_characters = remote_assets.get("characters", {})
        for char_id, asset_info in remote_characters.items():
            local_asset_path = app_paths.user_characters_assets / f"{char_id}.png"

            if not local_asset_path.exists():
                logger.info("New asset available for character '%s'", char_id)
                
                self.assetUpdateAvailable.emit(char_id)
                
                self._download_file(
                    char_id,
                    asset_info,
                    self._on_download_char_asset_finished,
                    is_asset=True,
                )
                
            else:
                local_asset_hash = get_file_hash(local_asset_path)
                if local_asset_hash != asset_info.get("hash"):
                    logger.info("Update available for character asset '%s'", char_id)
                    self.assetUpdateAvailable.emit(char_id)
                    self._download_file(
                        char_id,
                        asset_info,
                        self._on_download_char_asset_finished,
                        is_asset=True,
                    )

    def _download_file(
        self,
        key: str,
        item_info: Dict[str, Any],
        callback_slot: Slot,
        is_asset: bool = False,
    ) -> None:
        url = item_info.get("url")
        if not url:
            logger.error("No URL found for key '%s' in manifest.", key)
            self.errorOccurred.emit(f"No URL found for key '{key}' in manifest.")
            return

        logger.info("Starting download for '%s' from %s", key, url)
        request = QNetworkRequest(QUrl(url))
        reply = self._network_manager.get(request)
        reply.setProperty("key", key)
        reply.setProperty("is_asset", is_asset)
        reply.finished.connect(callback_slot)

        self._active_downloads += 1

    @Slot()
    def _on_download_data_finished(self) -> None:
        reply: QNetworkReply = self.sender()
        key = reply.property("key")

        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                logger.error(
                    "Download for data '%s' failed: %s", key, reply.errorString()
                )
                self.errorOccurred.emit(f"Download for '{key}' failed: {reply.errorString()}")
                return

            data = reply.readAll().data()
            logger.info("Download for data '%s' completed successfully.", key)

            # file != content
            expected_hash = self._remote_manifest_data.get("data", {}).get(key, {}).get("hash")
            if expected_hash and hashlib.sha256(data).hexdigest() != expected_hash:
                print(data)
                logger.error("Hash mismatch for '%s'. Download may be corrupted.", key)
                self.errorOccurred.emit(f"Hash mismatch for '{key}'. Download may be corrupted.")
                return

            destination_path = self._get_destination_path(key)
            if not destination_path:
                return

            self._save_downloaded_file(data, destination_path)

            self._local_manifest_data["data"][key] = self._remote_manifest_data["data"][
                key
            ]
            self.dataUpdated.emit(key)
        finally:
            self._decrement_active_downloads()
            reply.deleteLater()

    @Slot()
    def _on_download_char_asset_finished(self) -> None:
        reply: QNetworkReply = self.sender()
        char_id = reply.property("key")

        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                logger.error(
                    "Download for asset ID '%s' failed: %s",
                    char_id,
                    reply.errorString(),
                )
                self.errorOccurred.emit(
                    f"Download for asset ID '{char_id}' failed: {reply.errorString()}"
                )
                return

            data = reply.readAll().data()
            logger.info("Download for asset ID '%s' completed successfully.", char_id)

            expected_hash = (
                self._remote_manifest_data.get("assets", {})
                .get("characters", {})
                .get(char_id, {})
                .get("hash")
            )
            if expected_hash and hashlib.sha256(data).hexdigest() != expected_hash:
                logger.error(
                    "Hash mismatch for asset '%s'. Download may be corrupted.", char_id
                )
                self.errorOccurred.emit(
                    f"Hash mismatch for asset '{char_id}'. Download may be corrupted."
                )
                return

            destination_path = app_paths.user_characters_assets / f"{char_id}.png"
            self._save_downloaded_file(data, destination_path)

            if "assets" not in self._local_manifest_data:
                self._local_manifest_data["assets"] = {"version": "0.0.0", "characters": {}}
            if "characters" not in self._local_manifest_data["assets"]:
                self._local_manifest_data["assets"]["characters"] = {}
                
            self._local_manifest_data["assets"]["characters"][char_id] = (
                self._remote_manifest_data["assets"]["characters"][char_id]
            )
            self.assetUpdated.emit(char_id)
        finally:
            self._decrement_active_downloads()
            reply.deleteLater()

    def _get_destination_path(self, key: str) -> Path | None:
        path_map = {
            "characters.csv": app_paths.characters_csv,
            "authors.csv": app_paths.authors_csv,
            "datings.csv": app_paths.datings_csv,
            "npcs.csv": app_paths.npcs_csv
        }
        destination_path = path_map.get(key)
        if not destination_path:
            logger.error("No destination path configured for data key '%s'.", key)
            self.errorOccurred.emit(f"No destination path configured for data key '{key}'.")
        return destination_path

    def _save_downloaded_file(self, data: bytes, destination_path: Path) -> None:
        temp_path = None
        try:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "wb", delete=False, dir=destination_path.parent, suffix=".tmp"
            ) as temp_f:
                temp_f.write(data)
                temp_path = Path(temp_f.name)
            shutil.move(temp_path, destination_path)
            logger.info("Successfully saved file to %s", destination_path)
        except IOError as e:
            logger.error(
                "Could not save downloaded file to %s: %s", destination_path, e
            )
            self.errorOccurred.emit(f"Could not save file {destination_path.name}: {e}")
            if temp_path and temp_path.exists():
                temp_path.unlink()

    def _decrement_active_downloads(self) -> None:
        self._active_downloads -= 1
        if self._active_downloads == 0:
            logger.info("All downloads finished.")
            self._save_local_manifest()
            self.allDownloadsFinished.emit()

    def check_bd2modpreview_version(self) -> None:
        logger.info("Checking for a new version of BD2ModPreview from %s", self._modpreview_releases_url)
        request = QNetworkRequest(QUrl(self._modpreview_releases_url))
        reply = self._network_manager.get(request)
        reply.finished.connect(self._on_bd2modpreview_version_received)
    
    @Slot()
    def _on_bd2modpreview_version_received(self):
        reply: QNetworkReply = self.sender()
        
        if reply.error() != QNetworkReply.NetworkError.NoError:
            logger.error("BD2ModPreview version check failed: %s", reply.errorString())
            self.errorOccurred.emit(f"BD2ModPreview version check failed: {reply.errorString()}")
            reply.deleteLater()
            return

        try:
            data = json.loads(reply.readAll().data())

            if data and isinstance(data, list) and "tag_name" in data[0]:
                releases = list(filter(lambda release: not release["prerelease"], data))
                if len(releases) > 0:
                    latest_version = releases[0]["tag_name"].lstrip("v")
                else:
                    return logger.critical("No releases was found.")

                tool = BD2ModPreview()
                current_version = tool.get_version()

                logger.info("BD2ModPreview: Current: %s, Latest: %s", current_version, latest_version)

                if current_version is None or version.parse(current_version) < version.parse(latest_version):
                    self.toolUpdateAvailable.emit("BD2ModPreview")
                    for asset in data[0].get("assets", []):
                        if asset["name"] == "BD2ModPreview.exe":
                            url = asset["browser_download_url"]
                            self._download_bd2modpreview(url)
                            break
                        
        except Exception as e:
            logger.error("Failed to parse BD2ModPreview version info: %s", e)
            self.errorOccurred.emit(f"BD2ModPreview version parsing failed: {e}")
        finally:
            reply.deleteLater()
    
    def _download_bd2modpreview(self, url: str):
        request = QNetworkRequest(QUrl(url))
        reply = self._network_manager.get(request)
        reply.finished.connect(self._on_bd2modpreview_downloaded)

    @Slot()
    def _on_bd2modpreview_downloaded(self):
        reply: QNetworkReply = self.sender()
        
        if reply.error() != QNetworkReply.NetworkError.NoError:
            logger.error("Failed to download BD2ModPreview: %s", reply.errorString())
            self.errorOccurred.emit(f"Failed to download BD2ModPreview: {reply.errorString()}")
            reply.deleteLater()
            return

        try:
            data = reply.readAll().data()

            app_paths.user_tools_path.mkdir(parents=True, exist_ok=True)

            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=app_paths.user_cache_path,
                delete=False,
                suffix=".exe"
            ) as temp_file:
                temp_file.write(data)
                temp_path = Path(temp_file.name)

            final_path = app_paths.user_tools_path / "BD2ModPreview.exe"
            
            shutil.move(temp_path, final_path)

            logger.info("BD2ModPreview.exe updated successfully.")
            self.toolUpdated.emit("BD2ModPreview")

        except Exception as error:
            logger.error("Error updating BD2ModPreview: %s", error)
            self.errorOccurred.emit(f"Error updating BD2ModPreview: {error}")
        finally:
            reply.deleteLater()
                
