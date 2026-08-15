use chrono::Utc;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, thiserror::Error)]
pub enum ProfileError {
    #[error("profile '{profile_id}' was not found")]
    ProfileNotFound { profile_id: String },
    #[error("profile with the name '{profile_name}' already exists.")]
    ProfileAlreadyExists { profile_name: String },
    #[error("'{profile_name}' is not a valid name ({reason})")]
    InvalidName { profile_name: String, reason: String },
    #[error("profile '{profile_name}' is already active")]
    AlreadyActive { profile_name: String },
    #[error("profile '{profile_name}' cannot be deleted because it is active")]
    CannotDeleteActive { profile_name: String },
    #[error("profile cannot be deleted because it is the default profile")]
    CannotDeleteDefault,
    #[error("no active profile is set")]
    NoActiveProfile,

    #[error("failed to load profiles: {source}")]
    LoadFailed {
        #[source]
        source: std::io::Error,
    },

    #[error("failed to save profile '{profile_name}': {source}")]
    SaveFailed {
        profile_name: String,
        #[source]
        source: std::io::Error,
    },

    #[error("failed to create profile '{profile_name}': {source}")]
    CreateFailed {
        profile_name: String,
        #[source]
        source: std::io::Error,
    },

    #[error("failed to serialize profile '{profile_name}': {source}")]
    SerializeFailed {
        profile_name: String,
        #[source]
        source: serde_json::Error,
    },

    #[error("failed to update profile '{profile_name}': {source}")]
    UpdateFailed {
        profile_name: String,
        #[source]
        source: std::io::Error,
    },

    #[error("failed to delete profile '{profile_name}': {source}")]
    DeleteFailed {
        profile_name: String,
        #[source]
        source: std::io::Error,
    },

    #[error("profiles directory '{path}' was not found")]
    ProfilesDirectoryNotFound { path: String },

    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),
}

impl serde::Serialize for ProfileError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        use serde::ser::SerializeStruct;
        use serde_json::json;

        let (type_, details): (&str, Option<serde_json::Value>) = match self {
            ProfileError::ProfileNotFound { profile_id } => (
                "ProfileNotFound",
                Some(json!({ "profile_id": profile_id })),
            ),
            ProfileError::ProfileAlreadyExists { profile_name } => (
                "ProfileAlreadyExists",
                Some(json!({ "profile_name": profile_name })),
            ),
            ProfileError::InvalidName { profile_name, reason } => (
                "InvalidName",
                Some(json!({ "profile_name": profile_name, "reason": reason })),
            ),
            ProfileError::AlreadyActive { profile_name } => (
                "AlreadyActive",
                Some(json!({ "profile_name": profile_name })),
            ),
            ProfileError::CannotDeleteActive { profile_name } => (
                "CannotDeleteActive",
                Some(json!({ "profile_name": profile_name })),
            ),
            ProfileError::CannotDeleteDefault => ("CannotDeleteDefault", None),
            ProfileError::NoActiveProfile => ("NoActiveProfile", None),
            ProfileError::LoadFailed { source } => (
                "LoadFailed",
                Some(json!({ "kind": format!("{:?}", source.kind()) })),
            ),
            ProfileError::SaveFailed { profile_name, source } => (
                "SaveFailed",
                Some(json!({ "profile_name": profile_name, "kind": format!("{:?}", source.kind()) })),
            ),
            ProfileError::CreateFailed { profile_name, source } => (
                "CreateFailed",
                Some(json!({ "profile_name": profile_name, "kind": format!("{:?}", source.kind()) })),
            ),
            ProfileError::SerializeFailed { profile_name, .. } => (
                "SerializeFailed",
                Some(json!({ "profile_name": profile_name })),
            ),
            ProfileError::UpdateFailed { profile_name, source } => (
                "UpdateFailed",
                Some(json!({ "profile_name": profile_name, "kind": format!("{:?}", source.kind()) })),
            ),
            ProfileError::DeleteFailed { profile_name, source } => (
                "DeleteFailed",
                Some(json!({ "profile_name": profile_name, "kind": format!("{:?}", source.kind()) })),
            ),
            ProfileError::ProfilesDirectoryNotFound { path } => (
                "ProfilesDirectoryNotFound",
                Some(json!({ "path": path })),
            ),
            ProfileError::Io(error) => (
                "Io",
                Some(json!({ "kind": format!("{:?}", error.kind()) })),
            ),
        };

        let mut s = serializer.serialize_struct("ProfileError", 3)?;
        s.serialize_field("type", type_)?;
        s.serialize_field("details", &details)?;
        s.serialize_field("message", &self.to_string())?;
        s.end()
    }
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
            name,
            description,
            created_at: created_at.unwrap_or_else(|| Utc::now().to_rfc3339()),
            enabled_mods,
            active: false,
        }
    }

    pub fn get_mod_state(&self, mod_name: &String) -> bool {
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