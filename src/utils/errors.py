class GameDirectoryNotSetError(Exception):
    """Raised when game directory is not defined."""


class GameNotFoundError(Exception):
    """Raised when the game is not found in the specified path."""

class ModInvalidError(Exception):
    """Raised when the mod is not a valid Brown Dust X mod."""

class ModAlreadyExistsError(Exception):
    """Raised when a mod with the same name already exists."""

class ModNotFoundError(Exception):
    """Raised when a mod is not found in the specified path."""

class InvalidModNameError(Exception):
    """Raised when the mod name is invalid (e.g., contains path separators)."""

class BrownDustXNotInstalled(Exception):
    """Raised when BrownDustX is not found in the game path."""

class AdminRequiredError(Exception):
    """Raised when an operation requires administrative permission."""
    
class UnsupportedArchiveFormatError(Exception):
    pass

class RarExtractionError(Exception):
    pass