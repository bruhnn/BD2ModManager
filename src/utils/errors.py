class ModManagerError(Exception):
    """Base exception for all mod manager errors."""


class GameDirectoryNotSetError(ModManagerError):
    """Raised when game directory is not defined."""


class GameNotFoundError(ModManagerError):
    """Raised when the game is not found in the specified path."""


class BrownDustXNotInstalled(ModManagerError):
    """Raised when BrownDustX is not found in the game path."""


class ModError(ModManagerError):
    """Base exception for mod-related errors."""


class ModInvalidError(ModError):
    """Raised when the mod is not a valid Brown Dust X mod."""


class ModAlreadyExistsError(ModError):
    """Raised when a mod with the same name already exists."""


class ModNotFoundError(ModError):
    """Raised when a mod is not found in the specified path."""


class InvalidModNameError(ModError):
    """Raised when the mod name is invalid (e.g., contains path separators)."""


class ArchiveError(ModManagerError):
    """Base exception for archive-related errors."""


class UnsupportedArchiveFormatError(ArchiveError):
    """Raised when an archive format is not supported."""


class RarExtractionError(ArchiveError):
    """Raised when RAR extraction fails."""


class AdminRequiredError(ModManagerError):
    """Raised when an operation requires administrative permission."""
