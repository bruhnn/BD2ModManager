use std::{
    collections::HashMap,
    fs::{create_dir, read_to_string, File},
    io::Write,
    path::PathBuf,
};

use chrono::Utc;
use log::{error, info, warn, debug};
use tempfile::NamedTempFile;

use crate::profiles::types::{Profile, ProfileError};

use std::fs::read_dir;

pub struct ProfileManager {
    directory: PathBuf,
    profiles: HashMap<String, Profile>,
    active_profile_id: Option<String>,
}

impl ProfileManager {
    const DEFAULT_PROFILE_ID: &'static str = "default";
    const DEFAULT_PROFILE_NAME: &'static str = "Default";
    const DEFAULT_PROFILE_DESC: &'static str = "d3f4ult";

    pub fn new(directory: PathBuf) -> ProfileManager {
        Self {
            directory,
            profiles: HashMap::new(),
            active_profile_id: None,
        }
    }

    fn _create_default_profile(&mut self) -> Result<(), ProfileError> {
        let default_profile = Profile {
            id: String::from(Self::DEFAULT_PROFILE_ID),
            name: String::from(Self::DEFAULT_PROFILE_NAME),
            description: String::from(Self::DEFAULT_PROFILE_DESC),
            created_at: Utc::now().to_rfc3339(),
            active: false,
            enabled_mods: Vec::new(),
        };

        self._create_profile_json(&default_profile)?;
        self.profiles
            .insert(default_profile.id.clone(), default_profile);
        Ok(())
    }

    fn _create_profile_json(&mut self, profile: &Profile) -> Result<(), ProfileError> {
        let mut path = self.directory.clone();
        path.push(format!("{}.json", profile.id));

        if path.exists() {
            error!("Profile JSON already exists: {:?}", path);
            return Err(ProfileError::ProfileAlreadyExists {
                profile_name: profile.name.clone(),
            });
        }

        info!("Creating Profile -> {:?}", path);

        let file = File::create(&path).map_err(|source| {
            error!("Failed to create profile JSON '{}': {:?}", profile.name, source);
            ProfileError::CreateFailed {
                profile_name: profile.name.clone(),
                source,
            }
        })?;

        serde_json::to_writer_pretty(&file, profile).map_err(|source| {
            error!("Failed to write profile JSON '{}': {:?}", profile.name, source);
            ProfileError::SerializeFailed {
                profile_name: profile.name.clone(),
                source,
            }
        })?;

        info!("Profile created successfully -> {:?}", profile);

        Ok(())
    }

    pub fn save_profile(&self, profile: &Profile) -> Result<(), ProfileError> {
        let mut path = self.directory.clone();
        path.push(format!("{}.json", profile.id));

        info!("Saving Profile -> {:?}", path);

        let mut tmp = NamedTempFile::new_in(path.parent().unwrap()).map_err(|source| {
            error!(
                "Failed to create temporary file for profile '{}': {:?}",
                profile.name, source
            );
            ProfileError::SaveFailed {
                profile_name: profile.name.clone(),
                source,
            }
        })?;

        serde_json::to_writer_pretty(&mut tmp, profile).map_err(|source| {
            error!("Failed to write profile json {:?}: {}", path, source);
            ProfileError::SerializeFailed {
                profile_name: profile.name.clone(),
                source,
            }
        })?;

        tmp.flush().map_err(|source| {
            error!("Failed to flush profile json {:?}: {}", path, source);
            ProfileError::SaveFailed {
                profile_name: profile.name.clone(),
                source,
            }
        })?;

        tmp.persist(&path).map_err(|e| ProfileError::SaveFailed {
            profile_name: profile.name.clone(),
            source: e.error,
        })?;

        info!("Profile saved successfully -> {:?}", profile);

        Ok(())
    }

    pub fn load_profiles(&mut self) -> Result<(), ProfileError> {
        if !self.directory.exists() {
            if let Err(source) = create_dir(&self.directory) {
                error!(
                    "Failed to create profiles directory {:?}: {}",
                    self.directory, source
                );
                return Err(ProfileError::ProfilesDirectoryNotFound {
                    path: self.directory.to_string_lossy().into_owned(),
                });
            };
        }

        if let Ok(entries) = read_dir(&self.directory) {
            entries
                .filter_map(Result::ok)
                .filter(|entry| {
                    if let Some(ext) = entry.path().extension() {
                        ext == "json"
                    } else {
                        false
                    }
                })
                .for_each(|profile_path| {
                    let path = profile_path.path();

                    debug!("Profile found {:?}", path);

                    if let Ok(data) = read_to_string(&path) {
                        match serde_json::from_str::<Profile>(&data) {
                            Ok(mut profile) => {
                                info!("Profile {} ({}) was loaded.", profile.name, profile.id);

                                profile.enabled_mods = profile
                                    .enabled_mods
                                    .into_iter()
                                    .map(|m| m.replace("\\", "/"))
                                    .collect();

                                if profile.active {
                                    self.active_profile_id = Some(profile.id.clone());
                                }

                                self.profiles.insert(profile.id.clone(), profile);
                            }
                            Err(error) => warn!("Failed to parse profile {:?}: {}", path, error),
                        }
                    }
                });
        }

        if self.profiles.get(Self::DEFAULT_PROFILE_ID).is_none() {
            warn!("Default profile not found. Creating a new.");
            if let Err(error) = self._create_default_profile() {
                error!("Failed to create default profile: {}", error);
            }
        }

        if self.active_profile_id.is_none() {
            if let Some(default_profile) = self.profiles.get_mut(Self::DEFAULT_PROFILE_ID) {
                warn!("No active profile found. Setting 'Default' as active.");

                self.active_profile_id = Some(default_profile.id.clone());
                default_profile.active = true;
            } else {
                error!("Default profile not found, cannot set it as active.");
            }
        }

        Ok(())
    }

    pub fn create_profile(
        &mut self,
        name: String,
        description: Option<String>,
        enabled_mods: Option<Vec<String>>,
        created_at: Option<String>,
        template_id: Option<String>,
    ) -> Result<(), ProfileError> {
        let desc = description.unwrap_or_default();
        let created = Some(created_at.unwrap_or_else(|| chrono::Utc::now().to_rfc3339()));
        let enabled_mods = enabled_mods.unwrap_or_default();

        let profile: Profile;

        if let Some(template_id) = template_id {
            if let Some(template_profile) = self.profiles.get(&template_id) {
                profile = Profile::new(name, desc, template_profile.enabled_mods.clone(), created);
            } else {
                warn!(
                    "Template profile with id '{}' not found. Creating profile without template.",
                    template_id
                );
                profile = Profile::new(name, desc, enabled_mods, created);
            }
        } else {
            profile = Profile::new(name, desc, enabled_mods, created);
        }

        self.save_profile(&profile)?;
        self.profiles.insert(profile.id.clone(), profile.clone());
        Ok(())
    }

    pub fn delete_profile(&mut self, profile_id: String) -> Result<(), ProfileError> {
        if profile_id == Self::DEFAULT_PROFILE_ID {
            return Err(ProfileError::CannotDeleteDefault);
        }

        if (profile_id == self.active_profile_id.clone().unwrap_or_default())
            && (self.profiles.len() > 1)
        {
            self.set_active_profile(Self::DEFAULT_PROFILE_ID.to_string())?;
        }

        let profile = self
            .profiles
            .get(&profile_id)
            .ok_or_else(|| ProfileError::ProfileNotFound {
                profile_id: profile_id.clone(),
            })?;

        let mut path = self.directory.clone();
        path.push(format!("{}.json", profile.id));

        if !path.exists() {
            error!(
                "Profile JSON file not found for profile '{}': {:?}",
                profile.name, path
            );
            return Err(ProfileError::ProfileNotFound { profile_id });
        }

        std::fs::remove_file(&path).map_err(|source| {
            error!("Failed to delete profile JSON '{}': {:?}", profile.name, source);
            ProfileError::DeleteFailed {
                profile_name: profile.name.clone(),
                source,
            }
        })?;

        self.profiles.remove(&profile_id);
        Ok(())
    }

    pub fn edit_profile(
        &mut self,
        profile_id: String,
        name: String,
        description: Option<String>,
    ) -> Result<(), ProfileError> {
        if let Some(profile) = self.profiles.get_mut(&profile_id) {
            profile.name = name;
            profile.description = description.unwrap_or_default();
        } else {
            return Err(ProfileError::ProfileNotFound { profile_id });
        }

        self.save_profile(self.profiles.get(&profile_id).unwrap())?;
        Ok(())
    }

    pub fn get_profiles(&self) -> Vec<Profile> {
        self.profiles.values().cloned().collect()
    }

    pub fn get_active_profile(&mut self) -> Option<&mut Profile> {
        self.active_profile_id
            .as_ref()
            .and_then(|id| self.profiles.get_mut(id))
    }

    pub fn set_active_profile(&mut self, profile_id: String) -> Result<(), ProfileError> {
        if !self.profiles.contains_key(&profile_id) {
            return Err(ProfileError::ProfileNotFound { profile_id });
        }

        self.active_profile_id = Some(profile_id.clone());

        let mut changed_profiles = Vec::new();
        for profile in self.profiles.values_mut() {
            let should_be_active = profile.id == profile_id;
            if profile.active != should_be_active {
                profile.active = should_be_active;
                changed_profiles.push(profile.clone());
            }
        }

        for profile in changed_profiles {
            if let Err(e) = self.save_profile(&profile) {
                error!(
                    "Failed to save profile '{}' when setting active profile: {}",
                    profile.name, e
                );
            }
        }

        Ok(())
    }

    pub fn save_active_profile(&mut self) -> Result<(), ProfileError> {
        if let Some(active_profile) = self.get_active_profile() {
            let profile_to_save = active_profile.clone();
            self.save_profile(&profile_to_save)?;
            Ok(())
        } else {
            error!("No active profile to save.");
            Err(ProfileError::NoActiveProfile)
        }
    }

    pub fn remove_mod_from_profiles(&mut self, mod_name: &str) {
        let mut changed_profiles = Vec::new();
        for profile in self.profiles.values_mut() {
            if profile.enabled_mods.iter().any(|m| m == mod_name) {
                profile.enabled_mods.retain(|m| m != mod_name);
                changed_profiles.push(profile.clone());
            }
        }
        for profile in changed_profiles {
            if let Err(e) = self.save_profile(&profile) {
                error!(
                    "Failed to save profile '{}' after removing mod '{}': {}",
                    profile.name, mod_name, e
                );
            }
        }
    }
}