from dataclasses import dataclass, field
from pathlib import Path
import json
import logging
from typing import Dict
from uuid import uuid4
from datetime import datetime


# Configure logger for the module
logger = logging.getLogger(__name__)


@dataclass
class ModInfo:
    enabled: bool = False
    
    def as_dict(self):
        return {
            "enabled": self.enabled
        }
        
    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            enabled=data.get("enabled", False)
        )


@dataclass
class Profile:
    id: str
    name: str
    description: str = ""
    mods: Dict[str, ModInfo] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    active: bool = False

    def as_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "mods": {
                mod_name: modinfo.as_dict() for mod_name, modinfo in self.mods.items()
            },
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "active": self.active
        }

    @classmethod
    def from_dict(cls, data: dict):
        logger.debug(f"Creating Profile from dictionary data: {data.get('name', 'Unknown')}")
        try:
            return cls(
                id=data["id"],
                name=data["name"],
                description=data["description"],
                mods={
                    mod_name: ModInfo.from_dict(mod_data) for mod_name, mod_data in data.get("mods", {}).items()
                },
                created_at=datetime.fromisoformat(data["created_at"]),
                updated_at=datetime.fromisoformat(data["updated_at"]),
                active=data["active"]
            )
        except KeyError as e:
            logger.error(f"Missing required key when creating Profile: {e}")
            raise
        except ValueError as e:
            logger.error(f"Invalid value when creating Profile: {e}")
            raise


class ProfileManager:
    def __init__(self, profiles_folder: Path | str):
        logger.info(f"Initializing ProfileManager with folder: {profiles_folder}")
        self._profiles_folder: Path = Path(profiles_folder)

        if not (self._profiles_folder).exists():
            logger.info(f"Creating profiles folder: {self._profiles_folder}")
            self._profiles_folder.mkdir(parents=True, exist_ok=True)
        else:
            logger.debug(f"Profiles folder already exists: {self._profiles_folder}")

        self._profiles: dict[str, Profile] = {}
        self._current_profile: Profile | None = None

        logger.debug("Ensuring default profile exists")
        self._ensure_default_profile()

        logger.debug("Loading all profiles")
        self._load_profiles()
        
        logger.info(f"ProfileManager initialized with {len(self._profiles)} profiles")

    def _ensure_default_profile(self):
        default_file = self._profiles_folder / "default.json"
        logger.debug(f"Checking for default profile at: {default_file}")
        
        default_profile = Profile(
            id="default",
            name="default",
        )
        
        if not default_file.exists():
            logger.info("Default profile not found, creating new default profile")
            self._save_profile(default_profile)
        else:
            logger.debug("Default profile file exists, loading it")
            try:
                with default_file.open("r", encoding="UTF-8") as default_data:
                    default_profile = Profile.from_dict(json.load(default_data))
                logger.debug("Default profile loaded successfully")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in default profile file: {e}")
                logger.info("Creating new default profile to replace corrupted one")
                self._save_profile(default_profile)
            except Exception as e:
                logger.error(f"Unexpected error loading default profile: {e}")
                logger.info("Creating new default profile")
                self._save_profile(default_profile)

        if not self._current_profile:
            logger.info("Setting default profile as active")
            default_profile.active = True
            self._current_profile = default_profile

    def _load_profiles(self):
        files = list(self._profiles_folder.glob("**/*.json"))
        logger.info(f"Found {len(files)} profile files to load")

        loaded_count = 0
        error_count = 0

        for file in files:
            logger.debug(f"Loading profile from: {file}")
            try:
                with file.open("r", encoding="UTF-8") as pfile:
                    data = json.load(pfile)
                
                profile = Profile.from_dict(data)
                self._profiles[data["id"]] = profile
                loaded_count += 1
                
                logger.debug(f"Successfully loaded profile: {profile.name} (ID: {profile.id})")
                
                # Check if this profile should be the active one
                if profile.active and self._current_profile != profile:
                    logger.info(f"Found active profile: {profile.name}")
                    if self._current_profile:
                        logger.warning(f"Multiple active profiles found. Keeping {profile.name} as active")
                    self._current_profile = profile
                    
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in profile file {file.name}: {e}")
                error_count += 1
            except KeyError as e:
                logger.error(f"Missing required field in profile file {file.name}: {e}")
                error_count += 1
            except Exception as e:
                logger.error(f"Unexpected error loading profile file {file.name}: {e}")
                error_count += 1

        logger.info(f"Profile loading complete: {loaded_count} loaded, {error_count} errors")

    def _save_profile(self, profile: Profile):
        profile_file = self._profiles_folder / f"{profile.name}.json"
        logger.debug(f"Saving profile '{profile.name}' to: {profile_file}")
        
        try:
            profile.updated_at = datetime.now()
            with open(profile_file, "w", encoding="UTF-8") as f:
                json.dump(profile.as_dict(), f, indent=4)
            logger.debug(f"Profile '{profile.name}' saved successfully")
        except Exception as e:
            logger.error(f"Failed to save profile '{profile.name}': {e}")
            raise

    def _get_profile_by_id(self, profile_id: str) -> Profile | None:
        logger.debug(f"Looking up profile by ID: {profile_id}")
        profile = self._profiles.get(profile_id)
        if profile:
            logger.debug(f"Found profile: {profile.name}")
        else:
            logger.debug(f"Profile with ID {profile_id} not found")
        return profile

    def get_all_profiles(self) -> list[Profile]:
        logger.debug(f"Returning all profiles (count: {len(self._profiles)})")
        return [profile for _, profile in self._profiles.items()] 

    def get_active_profile(self) -> Profile | None:
        if self._current_profile:
            logger.debug(f"Active profile: {self._current_profile.name}")
        else:
            logger.debug("No active profile set")
        return self._current_profile

    def create_profile(self, profile_name: str, description: str) -> str:
        logger.info(f"Creating new profile: '{profile_name}'")
        
        # Check if profile with same name already exists
        existing_profiles = [p for p in self._profiles.values() if p.name == profile_name]
        if existing_profiles:
            logger.warning(f"Profile with name '{profile_name}' already exists")
        
        try:
            profile = Profile(
                id=str(uuid4()),
                name=profile_name,
                description=description
            )
            
            self._profiles[profile.id] = profile
            self._save_profile(profile)
            
            logger.info(f"Profile '{profile_name}' created successfully with ID: {profile.id}")
            return profile.id
            
        except Exception as e:
            logger.error(f"Failed to create profile '{profile_name}': {e}")
            raise

    def switch_profile(self, profile_id: str) -> bool:
        logger.info(f"Switching to profile with ID: {profile_id}")
        
        try:
            # Deactivate current profile
            if self._current_profile is not None:
                logger.debug(f"Deactivating current profile: {self._current_profile.name}")
                self._current_profile.active = False
                self._save_profile(self._current_profile)

            # Get new profile
            profile = self._get_profile_by_id(profile_id)
            if profile is None:
                logger.error(f"Profile with ID '{profile_id}' not found")
                raise ValueError(f"Profile with \"{profile_id}\" id not found.")

            # Activate new profile
            logger.info(f"Activating profile: {profile.name}")
            profile.active = True
            self._current_profile = profile
            self._save_profile(profile)
            
            logger.info(f"Successfully switched to profile: {profile.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to switch to profile {profile_id}: {e}")
            raise

    def save_profile(self, profile: Profile):
        logger.info(f"Saving profile: {profile.name}")
        try:
            self._save_profile(profile)
            logger.info(f"Profile '{profile.name}' saved successfully")
        except Exception as e:
            logger.error(f"Failed to save profile '{profile.name}': {e}")
            raise