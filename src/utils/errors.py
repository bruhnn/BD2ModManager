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
    message = "An error occurred with mod \"{mod_name}\"."
    
    def __init__(self, mod_name: str | None = None, message: str | None = None):
        err_msg = self.message.format(mod_name=mod_name) if not message else message
        super().__init__(err_msg)


class ModInvalidError(ModError):
    """Raised when the mod is not a valid Brown Dust X mod."""
    message = "Mod \"{mod_name}\" is not a valid mod."


class ModAlreadyExistsError(ModError):
    """Raised when a mod with the same name already exists."""
    message = "A mod named \"{mod_name}\" already exists."


class ModNotFoundError(ModError):
    """Raised when a mod is not found in the specified path."""
    message = "Mod \"{mod_name}\" was not found."


class InvalidModNameError(ModError):
    """Raised when the mod name is invalid (e.g., contains path separators)."""
    message = "Invalid mod name \"{mod_name}\". Check for illegal characters."


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