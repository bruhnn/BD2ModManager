from dataclasses import dataclass, field
from faulthandler import is_enabled
from pathlib import Path
import json
import logging
import tempfile
from typing import Any, Dict
from uuid import uuid4
from datetime import datetime
import shutil
from typing import Optional

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class ProfileAlreadyExistsError(Exception):
    pass


class ProfileNotFoundError(Exception):
    pass


class ProfileInUseError(Exception):
    pass


logger = logging.getLogger(__name__)


@dataclass
class ModInfo:
    enabled: bool = False

    def as_dict(self) -> Dict[str, bool]:
        return {"enabled": self.enabled}

    @classmethod
    def from_dict(cls, data: dict) -> 'ModInfo':
        return cls(enabled=data.get("enabled", False))

    def toggle(self) -> bool:
        """Toggle the enabled state and return the new state."""
        self.enabled = not self.enabled
        return self.enabled


@dataclass
class Profile:
    id: str
    _name: str
    _description: Optional[str] = None
    mods: Dict[str, ModInfo] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    active: bool = False

    def __post_init__(self):
        """Validate profile data after initialization."""
        if not self.id:
            raise ValueError("Profile ID cannot be empty")
        if not self._name or not self._name.strip():
            raise ValueError("Profile name cannot be empty")
        
        # Ensure timestamps are datetime objects if loaded from dict
        if isinstance(self.created_at, str):
            self.created_at = datetime.fromisoformat(self.created_at)
        if isinstance(self.updated_at, str):
            self.updated_at = datetime.fromisoformat(self.updated_at)

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        if not value or not value.strip():
            raise ValueError("Profile name cannot be empty")
        
        value = value.strip()
        if self._name != value:
            logger.debug("Profile name changed from '%s' to '%s'", self._name, value)
            self._name = value
            self.update_timestamp()

    @property
    def description(self) -> Optional[str]:
        return self._description

    @description.setter
    def description(self, value: Optional[str]) -> None:
        # Normalize empty strings to None
        if value is not None:
            value = value.strip() if value.strip() else None
            
        if self._description != value:
            logger.debug("Profile description changed for '%s'", self._name)
            self._description = value
            self.update_timestamp()
    
    @property
    def is_default(self) -> bool:
        return self.id == "default"

    @property
    def mod_count(self) -> int:
        """Return the total number of mods in this profile."""
        return len(self.mods)

    @property
    def enabled_mod_count(self) -> int:
        """Return the number of enabled mods in this profile."""
        return sum(1 for mod in self.mods.values() if mod.enabled)

    def update_timestamp(self) -> None:
        """Update the last modified timestamp."""
        _old_timestamp = self.updated_at
        self.updated_at = datetime.now()

    def add_mod(self, mod_name: str, enabled: bool = False) -> ModInfo:
        """Add a mod to the profile. If mod exists, update its state."""
        if not mod_name or not mod_name.strip():
            raise ValueError("Mod name cannot be empty")
        
        mod_name = mod_name.strip()
        
        if mod_name in self.mods:
            logger.debug("Mod '%s' already exists in profile '%s', updating state", 
                        mod_name, self._name)
            self.mods[mod_name].enabled = enabled
        else:
            logger.debug("Adding mod '%s' to profile '%s'", mod_name, self._name)
            mod_info = ModInfo(enabled=enabled)
            self.mods[mod_name] = mod_info
        
        self.update_timestamp()
        return self.mods[mod_name]

    def get_mod(self, mod_name: str) -> Optional[ModInfo]:
        """Get mod info by name."""
        if not mod_name:
            return None
        return self.mods.get(mod_name.strip())

    def has_mod(self, mod_name: str) -> bool:
        """Check if mod exists in profile."""
        return mod_name.strip() in self.mods if mod_name else False

    def remove_mod(self, mod_name: str) -> Optional[ModInfo]:
        """Remove a mod from the profile."""
        if not mod_name:
            return None
            
        mod_name = mod_name.strip()
        removed_mod = self.mods.pop(mod_name, None)
        
        if removed_mod:
            logger.debug("Removed mod '%s' from profile '%s'", mod_name, self._name)
            self.update_timestamp()
        else:
            logger.warning("Attempted to remove non-existent mod '%s' from profile '%s'", 
                          mod_name, self._name)
        
        return removed_mod

    def rename_mod(self, old_name: str, new_name: str) -> bool:
        """Rename a mod in the profile."""
        if not old_name or not new_name:
            raise ValueError("Both old and new mod names must be provided")
        
        old_name = old_name.strip()
        new_name = new_name.strip()
        
        if old_name == new_name:
            return True  # No change needed
        
        if old_name not in self.mods:
            logger.warning("Cannot rename: mod '%s' not found in profile '%s'", 
                          old_name, self._name)
            return False
            
        if new_name in self.mods:
            logger.warning("Cannot rename: mod '%s' already exists in profile '%s'", 
                          new_name, self._name)
            return False

        logger.debug("Renaming mod '%s' to '%s' in profile '%s'", 
                    old_name, new_name, self._name)
        
        self.mods[new_name] = self.mods.pop(old_name)
        self.update_timestamp()
        return True

    def enable_mod(self, mod_name: str) -> bool:
        """Enable a specific mod."""
        mod = self.get_mod(mod_name)
        if mod:
            if not mod.enabled:
                mod.enabled = True
                self.update_timestamp()
                logger.debug("Enabled mod '%s' in profile '%s'", mod_name, self._name)
            return True
        return False

    def disable_mod(self, mod_name: str) -> bool:
        """Disable a specific mod."""
        mod = self.get_mod(mod_name)
        if mod:
            if mod.enabled:
                mod.enabled = False
                self.update_timestamp()
                logger.debug("Disabled mod '%s' in profile '%s'", mod_name, self._name)
            return True
        return False

    def toggle_mod(self, mod_name: str) -> Optional[bool]:
        """Toggle a mod's enabled state. Returns new state or None if mod not found."""
        mod = self.get_mod(mod_name)
        if mod:
            new_state = mod.toggle()
            self.update_timestamp()
            logger.debug("Toggled mod '%s' to %s in profile '%s'", 
                        mod_name, "enabled" if new_state else "disabled", self._name)
            return new_state
        return None

    def enable_all_mods(self) -> int:
        """Enable all mods in the profile. Returns count of mods changed."""
        changed_count = 0
        for mod in self.mods.values():
            if not mod.enabled:
                mod.enabled = True
                changed_count += 1
        
        if changed_count > 0:
            self.update_timestamp()
            logger.debug("Enabled %d mods in profile '%s'", changed_count, self._name)
        
        return changed_count

    def disable_all_mods(self) -> int:
        """Disable all mods in the profile. Returns count of mods changed."""
        changed_count = 0
        for mod in self.mods.values():
            if mod.enabled:
                mod.enabled = False
                changed_count += 1
        
        if changed_count > 0:
            self.update_timestamp()
            logger.debug("Disabled %d mods in profile '%s'", changed_count, self._name)
        
        return changed_count

    def get_enabled_mods(self) -> Dict[str, ModInfo]:
        """Get all enabled mods."""
        return {name: mod for name, mod in self.mods.items() if mod.enabled}

    def get_disabled_mods(self) -> Dict[str, ModInfo]:
        """Get all disabled mods."""
        return {name: mod for name, mod in self.mods.items() if not mod.enabled}

    def clear_mods(self) -> int:
        """Remove all mods from the profile. Returns count of mods removed."""
        count = len(self.mods)
        if count > 0:
            self.mods.clear()
            self.update_timestamp()
            logger.debug("Cleared %d mods from profile '%s'", count, self._name)
        return count

    def copy_mods_from(self, other_profile: 'Profile', overwrite: bool = False) -> int:
        """Copy mods from another profile. Returns count of mods copied."""
        if not isinstance(other_profile, Profile):
            raise TypeError("other_profile must be a Profile instance")
        
        copied_count = 0
        for mod_name, mod_info in other_profile.mods.items():
            if mod_name not in self.mods or overwrite:
                # Create a new ModInfo instance to avoid shared references
                self.mods[mod_name] = ModInfo(enabled=mod_info.enabled)
                copied_count += 1
        
        if copied_count > 0:
            self.update_timestamp()
            logger.debug("Copied %d mods from profile '%s' to '%s'", 
                        copied_count, other_profile._name, self._name)
        
        return copied_count

    def as_dict(self) -> Dict[str, Any]:
        """Convert profile to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,  # Use property to get the actual name
            "description": self.description,  # Use property
            "mods": {
                mod_name: modinfo.as_dict() 
                for mod_name, modinfo in self.mods.items()
            },
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Profile':
        """Create profile from dictionary data."""
        try:
            # Handle both underscore and non-underscore formats for backward compatibility
            name = data.get("name") or data.get("_name")
            description = data.get("description") or data.get("_description")
            
            if not name:
                raise ValueError("Profile name is required")

            profile = cls(
                id=data["id"],
                _name=name,
                _description=description,
                mods={
                    mod_name: ModInfo.from_dict(mod_data)
                    for mod_name, mod_data in data.get("mods", {}).items()
                },
                created_at=data.get("created_at", datetime.now()),
                updated_at=data.get("updated_at", datetime.now()),
                active=data.get("active", False),
            )
            
            return profile
            
        except KeyError as e:
            raise ValueError(f"Missing required field in profile data: {e}")
        except Exception as e:
            raise ValueError(f"Invalid profile data: {e}")

    def validate(self) -> bool:
        """Validate profile data integrity."""
        try:
            if not self.id or not self._name.strip():
                return False
            
            # Validate mod data
            for mod_name, mod_info in self.mods.items():
                if not mod_name or not isinstance(mod_info, ModInfo):
                    return False
            
            return True
        except Exception:
            return False

    def __str__(self) -> str:
        return f"Profile(id='{self.id}', name='{self.name}', mods={self.mod_count}, enabled={self.enabled_mod_count})"

    def __repr__(self) -> str:
        return (f"Profile(id='{self.id}', _name='{self._name}', "
                f"_description='{self._description}', active={self.active}, "
                f"mods={self.mod_count})")

    def __eq__(self, other) -> bool:
        """Compare profiles by ID."""
        if not isinstance(other, Profile):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Hash based on profile ID."""
        return hash(self.id)


class ProfileManager(QObject):
    """Manages the loading, saving, and manipulation of all profiles."""
    profilesChanged = Signal()
    activeProfileChanged = Signal(str)

    def __init__(self, profiles_directory: Path | str) -> None:
        super().__init__()
        self._profiles_folder = Path(profiles_directory)
        self._profiles_folder.mkdir(parents=True, exist_ok=True)

        self._profiles: Dict[str, Profile] = {}
        self._profiles_by_name: Dict[str, Profile] = {}
        self._current_profile: Optional[Profile] = None

        self._create_default_profile()
        self._load_profiles()

        if not self._current_profile and "default" in self._profiles:
            logger.info("No active profile found. Setting 'Default' as active.")
            self.switch_profile("default")
        
        logger.info(f"ProfileManager initialized with {len(self._profiles)} profiles.")

    def _create_default_profile(self) -> None:
        """Loads the default profile or creates it if it doesn't exist or is corrupt."""
        default_path = self._profiles_folder / "default.json"
        if default_path.exists():
            try:
                with default_path.open("r", encoding="utf-8") as f:
                    profile = Profile.from_dict(json.load(f))
                    self._profiles[profile.id] = profile
                    self._profiles_by_name[profile.name.lower().strip()] = profile
                    if profile.active:
                        self._current_profile = profile
                    return
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Default profile is corrupt: {e}. A new one will be created.")

        default_profile = Profile(id="default", _name="Default", _description="The standard profile for managing mods.")
        self.save_profile(default_profile)
        self._profiles["default"] = default_profile
        self._profiles_by_name["default"] = default_profile

    def _load_profiles(self) -> None:
        """Loads all profiles from the profiles directory."""
        for file in self._profiles_folder.glob("*.json"):
            if file.stem == "default" or file.stem in self._profiles:
                continue # Skip default as it's already handled, or if already loaded
            try:
                with file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    profile = Profile.from_dict(data)
                    self._profiles[profile.id] = profile
                    self._profiles_by_name[profile.name.lower().strip()] = profile
                    if profile.active and not self._current_profile:
                        self._current_profile = profile
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.error(f"Could not load profile {file.name}: {e}")

    def get_profiles(self) -> list[Profile]:
        # Sort with "Default" profile first, then by creation date.
        return sorted(
            self._profiles.values(),
            key=lambda p: (p.id != "default", p.created_at)
        )

    def get_current_profile(self) -> Optional[Profile]:
        return self._current_profile

    def create_profile(self, name: str, description: Optional[str] = None) -> Profile:
        norm_name = name.lower().strip()
        if norm_name in self._profiles_by_name:
            raise ProfileAlreadyExistsError(f"Profile with name '{name}' already exists.")

        profile = Profile(id=str(uuid4()), _name=name, _description=description)
        
        self.save_profile(profile)

        self._profiles[profile.id] = profile
        self._profiles_by_name[norm_name] = profile
        self.profilesChanged.emit()
        return profile

    def delete_profile(self, profile_id: str) -> None:
        if profile_id == "default":
            raise ValueError("Cannot delete the default profile.")
        if self._current_profile and profile_id == self._current_profile.id:
            raise ProfileInUseError("Cannot delete the currently active profile.")

        profile = self._profiles.get(profile_id)
        
        if not profile:
            raise ProfileNotFoundError(f"Profile with ID '{profile_id}' not found.")
    
        if profile.is_default:
            raise ProfileInUseError("Cannot delete the default profile.")

        profile_file = self._profiles_folder / f"{profile_id}.json"
        if profile_file.exists():
            profile_file.unlink()

        self._profiles.pop(profile_id, None)
        self._profiles_by_name.pop(profile.name.lower().strip(), None)
        self.profilesChanged.emit()

    def edit_profile(self, profile_id: str, name: str, description: Optional[str]):
        profile = self._profiles.get(profile_id)
        if not profile:
            raise ProfileNotFoundError(f"Profile with ID '{profile_id}' not found.")

        new_name = name.lower().strip()
        if (new_name in self._profiles_by_name and
                self._profiles_by_name[new_name].id != profile_id):
            raise ProfileAlreadyExistsError(f"Profile with name '{name}' already exists.")

        old_name = profile.name.lower().strip()
        
        profile.name = name
        profile.description = description
        
        # Update name cache if it changed
        if old_name != new_name:
            self._profiles_by_name.pop(old_name)
            self._profiles_by_name[new_name] = profile
        
        self.save_profile(profile)
        self.profilesChanged.emit()

    def switch_profile(self, profile_id: str) -> None:
        target_profile = self._profiles.get(profile_id)
        if not target_profile:
            raise ProfileNotFoundError(f"Profile with ID '{profile_id}' not found.")

        # Deactivate the old profile if it exists and is different
        if self._current_profile and self._current_profile.id != target_profile.id:
            self._current_profile.active = False
            self.save_profile(self._current_profile)

        # Activate the new profile
        target_profile.active = True
        self.save_profile(target_profile)
        
        self._current_profile = target_profile
        self.activeProfileChanged.emit(target_profile.id)

    def save_profile(self, profile: Profile) -> None:
        profile.update_timestamp()
        
        profile_file = self._profiles_folder / f"{profile.id}.json"
        
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", delete=False,
                dir=self._profiles_folder, suffix=".tmp"
            ) as temp_f:
                json.dump(profile.as_dict(), temp_f, indent=4)
                temp_path = Path(temp_f.name)
            
            shutil.move(temp_path, profile_file)
        except Exception as e:
            logger.error(f"Failed to save profile '{profile.name}': {e}", exc_info=True)
            raise
        finally:
            if temp_path is not None and temp_path.exists():
                logger.debug(f"Cleaning up temporary file: {temp_path}")
                temp_path.unlink(missing_ok=True)
            