import logging

from PySide6.QtCore import QObject, Signal

from src.utils.errors import BrownDustXNotInstalled, GameDirectoryNotSetError, AdminRequiredError

logger = logging.getLogger(__name__)

# TODO: DRY

class BaseWorker(QObject):
    started = Signal(str)
    finished = Signal(str)
    error = Signal(str)
    progress = Signal(int, int, str)

    def __init__(
        self, mod_manager_model: "ModManagerModel", symlink: bool = False
    ) -> None:
        super().__init__()
        self._mod_manager_model = mod_manager_model
        self._symlink = symlink
        self._is_canceled = False
        logger.info("BaseWorker initialized.")

    def run(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError


class SyncWorker(BaseWorker):
    def run(self) -> None:
        try:
            logger.info("SyncWorker started.")
            self.started.emit(self.tr("Syncing Mods..."))
            self._mod_manager_model.sync_mods(
                symlink=self._symlink, progress_callback=self.progress.emit
            )
            logger.info("SyncWorker finished successfully.")
            self.finished.emit(self.tr("Sync completed successfully."))
        except GameDirectoryNotSetError:
            logger.error("Game directory not set.")
            return self.error.emit(self.tr("Game directory not set."))
        except AdminRequiredError:
            logger.error("Admin privileges required for symlinks.")
            return self.error.emit(self.tr("You need to run as administrator to use symlinks."))
        except BrownDustXNotInstalled:
            logger.error("BrownDustX not installed.")
            return self.error.emit(self.tr("BrownDustX not installed!"))
        except Exception as error:  # to not freeze the app
            logger.error(
                f"An unexpected error occurred during sync: {error}", exc_info=True
            )
            return self.error.emit(str(error))

    def stop(self) -> None:
        logger.info("SyncWorker stop requested.")


class UnsyncWorker(BaseWorker):
    def run(self) -> None:
        try:
            logger.info("UnsyncWorker started.")
            self.started.emit(self.tr("Unsyncing Mods..."))
            self._mod_manager_model.unsync_mods(
                progress_callback=self.progress.emit)
            self.finished.emit(self.tr("Unsync completed successfully."))
            logger.info("UnsyncWorker finished successfully.")
        except GameDirectoryNotSetError:
            logger.error("Game directory not set.")
            return self.error.emit(self.tr("Game directory not set."))
        except AdminRequiredError:
            logger.error("Admin privileges required for symlinks.")
            return self.error.emit(self.tr("You need to run as administrator to use symlinks."))
        except Exception as error:  # to not freeze the app
            logger.error(
                f"An unexpected error occurred during unsync: {error}", exc_info=True
            )
            return self.error.emit(str(error))

    def stop(self) -> None:
        logger.info("UnsyncWorker stop requested.")
