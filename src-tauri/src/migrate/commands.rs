use tauri::{AppHandle};

use crate::{AppState, migrate::{self, migrate::{LegacyProfile, MigrateError}}};

#[tauri::command]
pub fn get_legacy_profiles(app_handle: AppHandle) -> Result<Vec<LegacyProfile>, MigrateError> {
    migrate::get_profiles(&app_handle)
}

#[tauri::command]
pub fn import_legacy_profiles(
    app_handle: AppHandle,
    state: tauri::State<AppState>,
    profile_ids: Vec<String>,
) -> Result<bool, MigrateError> {
    let mut mod_manager = state.mod_manager.lock().map_err(|error| MigrateError::IoError(format!("Failed to acquire lock on mod manager: {:?}", error)))?;
    migrate::import_profiles(&app_handle, &mut mod_manager, profile_ids)
}


#[tauri::command]
pub fn import_legacy_mod_authors(app_handle: AppHandle, state: tauri::State<AppState>) -> Result<bool, MigrateError> {
    let mut mod_manager = state.mod_manager.lock().map_err(|error| MigrateError::IoError(format!("Failed to acquire lock on mod manager: {:?}", error)))?;
    migrate::import_mod_authors(&app_handle, &mut mod_manager)
}