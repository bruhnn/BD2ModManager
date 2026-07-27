use std::{collections::HashMap, fs, path::PathBuf};

use serde::{Deserialize, Serialize};
use tauri::Manager;

use log::{info, warn};

use crate::BD2ModManager;

// C:\Users\x\AppData\Local\Bruhnn\BD2ModManager

#[derive(Serialize, Deserialize, Debug)]
#[serde(rename_all = "camelCase")]
pub struct LegacyProfile {
    pub id: String,
    pub name: String,
    pub description: Option<String>,
    pub mods: HashMap<String, HashMap<String, bool>>,
    pub created_at: Option<String>,
    pub updated_at: Option<String>,
    pub active: Option<bool>,
}

pub fn get_legacy_app_local_dir(app_handle: &tauri::AppHandle) -> PathBuf {
    app_handle
        .path()
        .local_data_dir()
        .unwrap()
        .join("Bruhnn")
        .join("BD2ModManager")
}

#[derive(thiserror::Error, Serialize, Debug)]
#[serde(tag = "type", content = "message")]
pub enum MigrateError {
    #[error("I/O Error: {0}")]
    IoError(String),

    #[error("Profile Import Error: {0}")]
    ProfileImportError(String),
    #[error("Profile Delete Error: {0}")]
    ProfileDeleteError(String),

    #[error("Mods Import Error: {0}")]
    ModsImportError(String),
    #[error("Mods Parse Error: {0}")]
    ModsParseError(String),
    #[error("Mods Delete Error: {0}")]
    ModsDeleteError(String),
    #[error("Mods Refresh Error: {0}")]
    ModsRefreshError(String),
}

pub fn get_profiles(app_handle: &tauri::AppHandle) -> Result<Vec<LegacyProfile>, MigrateError> {
    let legacy_profiles_dir = get_legacy_app_local_dir(app_handle).join("profiles");

    if !legacy_profiles_dir.exists() {
        info!("No legacy profiles directory found at: {}", legacy_profiles_dir.display());

        return Ok(vec![]);
    }

    info!("Searching for legacy profiles in: {}", legacy_profiles_dir.display());

    Ok(fs::read_dir(legacy_profiles_dir)
        .map_err(|e| MigrateError::IoError(format!("Failed to read legacy profiles directory: {:?}", e)))?
        .filter_map(|entry| {
            let entry = entry.ok()?;
            if entry.path().extension()?.to_str()? == "json" {
                Some(entry.path())
            } else {
                None
            }
        })
        .filter_map(|path| {
            let content = fs::read_to_string(&path).ok()?;
            info!("Reading profile JSON: {}", path.display());
            serde_json::from_str::<LegacyProfile>(&content)
                .ok()
                .or_else(|| {
                    warn!("Failed to parse profile file: {}", path.display());
                    None
                })
        })
        .collect::<Vec<LegacyProfile>>())
}

pub fn import_profiles(
    app_handle: &tauri::AppHandle,
    mod_manager: &mut BD2ModManager,
    profile_ids: Vec<String>,
) -> Result<bool, MigrateError> {
    let legacy_profiles = get_profiles(&app_handle)?;

    if legacy_profiles.is_empty() {
        info!("No legacy profiles found to import.");
        return Ok(false);
    }

    let selected_profiles: Vec<LegacyProfile> = legacy_profiles
        .into_iter()
        .filter(|p| profile_ids.contains(&p.id))
        .collect();

    for profile in selected_profiles {
        info!("Importing legacy profile: {:?}", profile);

        let enabled_mods_names = profile
            .mods
            .iter()
            .filter_map(|(mod_name, mod_info)| {
                if mod_info.get("enabled").cloned().unwrap_or(false) {
                    Some(mod_name.clone())
                } else {
                    None
                }
            })
            .collect::<Vec<String>>();

        let profile_name = profile.name.clone();

        mod_manager.profile_manager
            .create_profile(
                profile_name.clone(),
                profile.description,
                Some(enabled_mods_names),
                profile.created_at,
                None

            )
            .map_err(|error| MigrateError::ProfileImportError(format!("Failed to import profile '{}': {:?}", profile_name, error)))?;

        // delete legacy profile file
        let legacy_profiles_dir = get_legacy_app_local_dir(&app_handle).join("profiles");
        let legacy_profile_path = legacy_profiles_dir.join(format!("{}.json", profile.id));
        if legacy_profile_path.exists() {
            std::fs::remove_file(&legacy_profile_path).map_err(|e| {
                MigrateError::ProfileDeleteError(format!(
                    "Failed to delete legacy profile file {}: {:?}",
                    legacy_profile_path.display(),
                    e
                ))
            })?;
        }
    }

    Ok(true)
}

pub fn import_mod_authors(app_handle: &tauri::AppHandle, mod_manager: &mut BD2ModManager) -> Result<bool, MigrateError> {
    let legacy_mods_path = get_legacy_app_local_dir(&app_handle).join("mods.json");

    if !legacy_mods_path.exists() {
        // its ok
        info!("No legacy mods file found at: {}", legacy_mods_path.display());
        return Ok(false);
    }

    let data = std::fs::read_to_string(&legacy_mods_path).map_err(|e| {
        MigrateError::ModsImportError(format!(
            "Failed to read legacy mods file {}: {:?}",
            legacy_mods_path.display(),
            e
        ))
    })?;

    let legacy_mods: serde_json::Value = serde_json::from_str(&data).map_err(|e| {
        MigrateError::ModsParseError(format!(
            "Failed to parse legacy mods file {}: {:?}",
            legacy_mods_path.display(),
            e
        ))
    })?;

    if let Some(mods_map) = legacy_mods.as_object() {
        mod_manager.metadata_store.import_from_legacy(
            &mods_map
                .iter()
                .map(|(k, v)| {
                    let map = v.as_object()
                        .cloned()
                        .map(|m| m.into_iter().collect::<std::collections::HashMap<String, serde_json::Value>>())
                        .unwrap_or_default();
                    (k.clone(), map)
                })
                .collect::<std::collections::HashMap<String, std::collections::HashMap<String, serde_json::Value>>>()
        );

        mod_manager.refresh_mods_authors(&app_handle).map_err(|e| {
            MigrateError::ModsRefreshError(format!(
                "Failed to refresh mods cache after importing legacy mod authors: {:?}",
                e
            ))
        })?;

        // delete legacy mods file
        std::fs::remove_file(&legacy_mods_path).map_err(|e| {
            MigrateError::ModsDeleteError(format!(
                "Failed to delete legacy mods file {}: {:?}",
                legacy_mods_path.display(),
                e
            ))
        })?;
    }

    Ok(true)
}
