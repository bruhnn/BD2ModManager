from dataclasses import dataclass, field
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
        old_timestamp = self.updated_at
        self.updated_at = datetime.now()
        logger.debug("Profile '%s' timestamp updated from %s to %s", 
                    self._name, old_timestamp, self.updated_at)

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
    profilesChanged = Signal()
    activeProfileChanged = Signal(str)

    def __init__(self, profiles_directory: Path | str) -> None:
        super().__init__()
        logger.info("Initializing ProfileManager with folder: %s", profiles_directory)

        self._profiles_folder: Path = Path(profiles_directory)

        if not (self._profiles_folder).exists():
            logger.info("Creating profiles folder: %s", str(self._profiles_folder))
            self._profiles_folder.mkdir(parents=True, exist_ok=True)
        else:
            logger.debug("Profiles folder already exists: %s", self._profiles_folder)

        self._profiles: dict[str, Profile] = {}
        self._profiles_by_name: Dict[str, Profile] = {}
        self._default_profile: Profile | None = None
        self._current_profile: Profile | None = None

        logger.debug("Creating default profile.")
        self._create_default_profile()

        logger.debug("Loading profiles.")
        self._load_profiles()

        logger.info("ProfileManager initialized with %d profiles", len(self._profiles))

    def _create_default_profile(self) -> None:
        default_path = self._profiles_folder / "default.json"

        logger.debug("Checking for default profile at: %s", default_path)

        default_profile = Profile(
            id="default",
            _name="Default",
            _description="The standard profile for managing mods.",
        )

        if not default_path.exists():
            logger.info("Default profile not found. Creating new default profile.")
            self.save_profile(default_profile)
        else:
            logger.debug("Default profile file exists. Loading from .json.")
            try:
                with default_path.open("r", encoding="UTF-8") as default_data:
                    default_profile = Profile.from_dict(json.load(default_data))

                logger.debug("Default profile loaded successfully.")
            except json.JSONDecodeError as error:
                logger.error("Invalid JSON in default profile file: %s", error)

                logger.info("Creating new default profile.")
                self.save_profile(default_profile)
            except Exception as error:
                logger.error("Unexpected error loading default profile: %s", error)
                logger.info("Creating new default profile.")
                self.save_profile(default_profile)

        self._default_profile = default_profile

    def _load_profiles(self) -> None:
        files = list(self._profiles_folder.glob("*.json"))
        logger.info("Found %d profiles.", len(files))

        loaded_count = 0
        error_count = 0

        for file in files:
            try:
                with file.open("r", encoding="UTF-8") as pfile:
                    data = json.load(pfile)

                profile = Profile.from_dict(data)
                self._profiles[data["id"]] = profile
                self._profiles_by_name[profile.name.lower().strip()] = profile
                loaded_count += 1

                logger.debug(
                    "Successfully loaded profile: %s (ID: %s)", profile.name, profile.id
                )

                # # Check if this profile should be the active
                if not self._current_profile and profile.active:
                    logger.info("Found active profile: %s", profile.name)
                    self._current_profile = profile

            except json.JSONDecodeError as error:
                logger.error("Invalid JSON in profile file %s: %s", file.name, error)
                error_count += 1
            except KeyError as error:
                logger.error(
                    "Missing required field in profile file %s: %s", file.name, error
                )
                error_count += 1
            except Exception as error:
                logger.error(
                    "Unexpected error loading profile file %s: %s", file.name, error
                )
                error_count += 1

        if self._current_profile is None and self._default_profile:
            logger.info("No active profile found. Activating the default profile.")
            self._default_profile.active = True
            self.save_profile(self._default_profile)
            self._current_profile = self._default_profile

        self.profilesChanged.emit()

        logger.info(
            "Profile loading complete: %d loaded, %d errors.", loaded_count, error_count
        )

    def _get_profile_by_id(self, profile_id: str) -> Profile | None:
        logger.debug("Getting profile by ID: %s", profile_id)

        profile = self._profiles.get(profile_id)

        return profile

    def _get_profile_by_name(self, profile_name: str) -> Profile | None:
        logger.debug("Getting profile by name: %s", profile_name)
        return self._profiles_by_name.get(profile_name.lower().strip())

    def get_profiles(self) -> list[Profile]:
        # put "default" on top, then sort by creation date
        profiles = sorted(
            [profile for _, profile in self._profiles.items()],
            key=lambda p: (p.id != "default", p.created_at),
            reverse=False,
        )
        return profiles

    def get_current_profile(self) -> Profile | None:
        return self._current_profile

    def create_profile(
        self, profile_name: str, description: str | None = None
    ) -> Profile:
        logger.info("Creating new profile: '%s'", profile_name)

        # Check if profile with same name already exists
        if self._get_profile_by_name(profile_name):
            logger.warning("Profile with ID '%s' already exists", profile_name)
            raise ProfileAlreadyExistsError(
                f"Profile with ID '{profile_name}' already exists"
            )

        try:
            profile = Profile(
                id=str(uuid4()), _name=profile_name, _description=description
            )

            self._profiles[profile.id] = profile
            self.save_profile(profile)

            logger.info(
                "Profile '%s' created successfully with ID: %s",
                profile_name,
                profile.id,
            )
            self.profilesChanged.emit()
            return profile

        except Exception as error:
            logger.error("Failed to create profile '%s': %s", profile_name, error)
            raise

    def switch_profile(self, profile_id: str) -> bool:
        logger.info("Switching to profile with ID: %s", profile_id)

        # Get new profile
        profile = self._get_profile_by_id(profile_id)

        if profile is None:
            logger.error("Profile with ID '%s' not found", profile_id)
            raise ProfileNotFoundError(f'Profile with ID "{profile_id}" not found.')

        # Deactivate current profile
        if self._current_profile is not None:
            logger.debug("Deactivating current profile: %s", self._current_profile.name)
            self._current_profile.active = False
            self.save_profile(self._current_profile)

        # Activate new profile
        logger.info("Activating profile: %s", profile.name)

        profile.active = True

        self._current_profile = profile

        self.activeProfileChanged.emit(profile.id)

        self.save_profile(profile)

        logger.info("Successfully switched to profile: %s", profile.name)

        return True

    def save_profile(self, profile: Profile) -> None:
        profile_file = self._profiles_folder / f"{profile.id}.json"

        logger.debug("Saving profile '%s' to: %s", profile.name, profile_file)

        try:
            profile.updated_at = datetime.now()

            with tempfile.NamedTemporaryFile(
                "w",
                encoding="UTF-8",
                delete=False,
                dir=self._profiles_folder,
                suffix=".tmp",
            ) as tempf:
                json.dump(profile.as_dict(), tempf, indent=4)
                temp_path = tempf.name

            shutil.move(temp_path, profile_file)

            logger.debug("Profile '%s' saved successfully", profile.name)

        except Exception as e:
            logger.error("Failed to save profile '%s': %s", profile.name, e)
            raise

    def delete_profile(self, profile_id: str) -> None:
        logger.debug("Deleting profile with ID '%s'", profile_id)

        profile_file = self._profiles_folder / f"{profile_id}.json"
        profile = self._get_profile_by_id(profile_id)

        if not profile_file.exists() or profile is None:
            raise ProfileNotFoundError(f'Profile with ID "{profile_id}" not found!')

        if profile == self._current_profile:
            raise ProfileInUseError("Cannot delete the currently active profile.")

        try:
            profile_file.unlink()
            self._profiles.pop(profile.id)
            self.profilesChanged.emit()
        except Exception as e:
            logger.error("Failed to remove profile with ID '%s': %s", profile_id, e)
            raise

    def edit_profile(self, profile_id: str, name: str, description: str):
        logger.debug("Editing profile with ID '%s'", profile_id)
        
        profile = self._get_profile_by_id(profile_id)
        
        if profile is None:
            raise ProfileNotFoundError(f'Profile with ID "{profile_id}" not found!')

        # if self._current_profile and self._current_profile.id == profile.id:
        #     logger.warning("Cannot edit the currently active profile '%s'.", profile.name)
        #     raise ProfileInUseError("Cannot edit the currently active profile.")

        if profile.name == name and profile.description == description:
            logger.debug("No changes detected for profile '%s'.", profile.name)
            return
        
        # Check if a profile with the new name already exists
        if self._get_profile_by_name(name):
            logger.warning("Profile with name '%s' already exists.", name)
            raise ProfileAlreadyExistsError(f'Profile with name "{name}" already exists.')

        logger.info("Updating profile '%s' with new name '%s' and description '%s'.",
                    profile.name, name, description)
        
        profile.name = name
        profile.description = description
        profile.update_timestamp()
        
        self.save_profile(profile)
        
        self.profilesChanged.emit()
        logger.info("Profile '%s' updated successfully.", profile.name)