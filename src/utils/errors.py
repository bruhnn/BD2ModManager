from pathlib import Path


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
    default_message = "An error occurred with mod \"{mod_name}\"."

    def __init__(self, mod_name: str | None = None, message: str | None = None) -> None:
        self.mod_name = mod_name
        self.message = self.default_message.format(
            mod_name=mod_name) if not message else message
        super().__init__(self.message)


class ModInvalidError(ModError):
    """Raised when the mod is not a valid Brown Dust X mod."""
    default_message = "Mod \"{mod_name}\" is not a valid mod."


class ModFileNotFoundError(ModInvalidError):
    """Raised when no .modfile is found"""

    def __init__(self, source_path: Path):
        self.source_path = source_path
        super().__init__(f"No .modfile found in: {source_path}")


class MultipleModFoldersError(ModInvalidError):
    """Raised when multiple mod folders are detected"""

    def __init__(self, source_path: Path, folder_count: int):
        self.source_path = source_path
        self.folder_count = folder_count
        super().__init__(f"Multiple mod folders found in {source_path}. Please install mods individually.")


class ModAlreadyExistsError(ModError):
    """Raised when a mod with the same name already exists."""
    default_message = "A mod named \"{mod_name}\" already exists."


class ModNotFoundError(ModError):
    """Raised when a mod is not found in the specified path."""
    default_message = "Mod \"{mod_name}\" was not found."


class InvalidModNameError(ModError):
    """Raised when the mod name is invalid (e.g., contains path separators)."""
    default_message = "Invalid mod name \"{mod_name}\". Check for illegal characters."


class ModInstallError(ModError):
    """Raised when an error occurs during the mod installation process."""

class ModDirectoryNotEmptyError(ModInstallError):
    """Raised when a mod cannot be installed because the target directory is not empty."""

class ModFileConflictError(ModInstallError):
    """Raised when a file exists where the mod directory should be."""
    
class ArchiveError(ModManagerError):
    """Base exception for archive-related errors."""


class UnsupportedArchiveFormatError(ArchiveError):
    """Raised when an archive format is not supported."""


class RarExtractionError(ArchiveError):
    """Raised when RAR extraction fails."""


class ExtractionPasswordError(ArchiveError):
    pass


class AdminRequiredError(ModManagerError):
    """Raised when an operation requires administrative permission."""
