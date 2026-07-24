use std::{
    collections::HashMap,
    fs::{create_dir, read_to_string, File},
    io::Write,
    path::PathBuf,
};

use chrono::Utc;
use log::{info, warn, error};
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
        self.profiles.insert(default_profile.id.clone(), default_profile);
        Ok(())
    }

    fn _create_profile_json(&mut self, profile: &Profile) -> Result<(), ProfileError> {
        let mut path = self.directory.clone();
        path.push(format!("{}.json", profile.id));

        info!("Creating Profile -> {:?}", path);

        let file = File::create(&path)
            .map_err(|e| ProfileError::CreateFailed(format!("Failed to create profile json {:?}: {}", path, e)))?;
        serde_json::to_writer_pretty(&file, profile)
            .map_err(|e| ProfileError::CreateFailed(format!("Failed to write profile json {:?}: {}", path, e)))?;

        info!("Profile created successfully -> {:?}", profile);

        Ok(())
    }

    pub fn save_profile(&self, profile: &Profile) -> Result<(), ProfileError> {
        let mut path = self.directory.clone();
        path.push(format!("{}.json", profile.id));

        info!("Saving Profile -> {:?}", path);

        let mut tmp = NamedTempFile::new_in(path.parent().unwrap())
            .map_err(|e| ProfileError::SaveFailed(format!("Failed to create tmp file for {:?}: {}", path, e)))?;
        serde_json::to_writer_pretty(&mut tmp, profile)
            .map_err(|e| ProfileError::SaveFailed(format!("Failed to write profile json {:?}: {}", path, e)))?;
        tmp.flush()
            .map_err(|e| ProfileError::SaveFailed(format!("Failed to flush profile json {:?}: {}", path, e)))?;
        tmp.persist(&path)
            .map_err(|e| ProfileError::SaveFailed(format!("Failed to persist profile json {:?}: {}", path, e.error)))?;

        info!("Profile saved successfully -> {:?}", profile);

        Ok(())
    }

    pub fn load_profiles(&mut self) -> Result<(), ProfileError> {
        if !self.directory.exists() {
            if let Err(error) = create_dir(&self.directory) {
                return Err(ProfileError::LoadFailed(format!("An error ocurred when creating the profiles directory: ({})", error)));
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

                    info!("Profile found {:?}", path);

                    if let Ok(data) = read_to_string(&path) {
                        match serde_json::from_str::<Profile>(&data) {
                            Ok(mut profile) => {
                                info!("Profile {} ({}) was loaded.", profile.name, profile.id);

                                // mod names backward compatibility all mod names uses / instea of \\
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

        let profile_deleted: bool;

        if (profile_id == self.active_profile_id.clone().unwrap_or_default())
            && (self.profiles.len() > 1)
        {
            // If the profile to be deleted is the active one, switch to default first
            self.set_active_profile(Self::DEFAULT_PROFILE_ID.to_string())?;
        }

        if let Some(profile) = self.profiles.get(&profile_id) {
            let mut path = self.directory.clone();
            path.push(format!("{}.json", profile.id));

            if path.exists() {
                match std::fs::remove_file(&path) {
                    Ok(()) => {
                        profile_deleted = true;
                    }
                    Err(error) => return Err(ProfileError::DeleteFailed(format!("Failed to delete profile json {:?}: {}", path, error))),
                }
            } else {
                return Err(ProfileError::NotFound(profile_id));
            }
        } else {
            return Err(ProfileError::NotFound(profile_id));
        }

        if profile_deleted {
            self.profiles.remove(&profile_id);
            Ok(())
        } else {
            Err(ProfileError::DeleteFailed(format!("Failed to delete profile with id '{}'", profile_id)))
        }
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
            return Err(ProfileError::NotFound(profile_id));
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
            return Err(ProfileError::NotFound(profile_id));
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
                error!("Failed to save profile '{}' when setting active profile: {}", profile.name, e);
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
            Err(ProfileError::NotFound(
                "No active profile to save.".to_string(),
            ))
        }
    }
    pub fn enable_mods_in_profile(
        &mut self,
        profile_id: &str,
        mod_names: &[String],
    ) -> Result<bool, ProfileError> {
        let profile = self
            .profiles
            .get_mut(profile_id)
            .ok_or_else(|| ProfileError::NotFound(profile_id.to_string()))?;

        for mod_name in mod_names {
            profile.set_mod_state(mod_name, true);
        }

        let profile_to_save = profile.clone();
        self.save_profile(&profile_to_save)?;

        Ok(self.active_profile_id.as_deref() == Some(profile_id))
    }

    pub fn set_profile_enabled_mods(
        &mut self,
        profile_id: &str,
        mod_names: Vec<String>,
    ) -> Result<bool, ProfileError> {
        let profile = self
            .profiles
            .get_mut(profile_id)
            .ok_or_else(|| ProfileError::NotFound(profile_id.to_string()))?;

        let mut seen = std::collections::HashSet::new();
        let normalized: Vec<String> = mod_names
            .into_iter()
            .map(|m| m.replace('\\', "/").trim().to_string())
            .filter(|m| !m.is_empty())
            .filter(|m| seen.insert(m.clone()))
            .collect();

        profile.enabled_mods = normalized;

        let profile_to_save = profile.clone();
        self.save_profile(&profile_to_save)?;

        Ok(self.active_profile_id.as_deref() == Some(profile_id))
    }

}
