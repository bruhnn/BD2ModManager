use chrono::Utc;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

// #[derive(Serialize, Deserialize, Debug)]
// pub struct ProfileMod {
//     pub name: String,
//     pub enabled: bool
// }

#[derive(Debug, thiserror::Error, Serialize)]
#[serde(tag = "type", content = "message")]
pub enum ProfileError {
    #[error("Profile not found: {0}")]
    ProfileNotFound(String),
    #[error("Invalid profile name: {0}")]
    InvalidName(String),
    #[error("Profile with the same ID already exists: {0}")]
    DuplicateId(String),
    #[error("Profile with the same name already exists: {0}")]
    DuplicateName(String),
    #[error("Failed to save profile: {0}")]
    SaveFailed(String),
    #[error("Failed to load profile: {0}")]
    LoadFailed(String),
    #[error("Cannot delete default profile")]
    CannotDeleteDefault,
    #[error("Failed to delete profile: {0}")]
    DeleteFailed(String),
    #[error("Failed to activate profile: {0}")]
    ActivateFailed(String),
    #[error("Failed to deactivate profile: {0}")]
    DeactivateFailed(String),
    #[error("Failed to list profiles: {0}")]
    ListFailed(String),
    #[error("Failed to update profile: {0}")]
    UpdateFailed(String),
    #[error("Failed to create profile: {0}")]
    CreateFailed(String),
    #[error("Failed to rename profile: {0}")]
    RenameFailed(String),
    #[error("Unknown error: {0}")]
    Other(String),
}

#[derive(Serialize, Deserialize, Debug, Clone)]
#[serde(rename_all = "camelCase")]
pub struct Profile {
    pub id: String,
    pub name: String,
    pub description: String,
    pub created_at: String,
    pub active: bool,
    pub enabled_mods: Vec<String>,
}

impl Profile {
    pub fn new(name: String, description: String, enabled_mods: Vec<String>, created_at: Option<String>) -> Self {
        Self {
            id: Uuid::new_v4().to_string(),
            name: name,
            description: description,
            created_at: created_at.unwrap_or_else(|| Utc::now().to_rfc3339()),
            enabled_mods,
            active: false,
        }
    }

    pub fn get_mod_state(&self, mod_name: &String) -> bool {
        // some mods was stored with '\\' instead of '/' in the name, so we need to check both, but now all mods are stored with '/'
        self.enabled_mods.contains(mod_name) || self.enabled_mods.contains(&mod_name.replace("/", "\\"))
    }

    pub fn set_mod_state(&mut self, mod_name: &String, enabled: bool) {
        if enabled {
            if !self.get_mod_state(mod_name) {
                self.enabled_mods.push(mod_name.to_string());
            }
        } else {
            self.enabled_mods.retain(|m| m != mod_name && m != &mod_name.replace("/", "\\"));
        }
    }
}
