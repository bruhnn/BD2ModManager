use tauri::AppHandle;

use crate::{
    errors::AppError,
    migrate::{
        self,
        migrate::{LegacyProfile, MigrateError},
    },
    AppState,
};

#[tauri::command]
pub fn get_legacy_profiles(app_handle: AppHandle) -> Result<Vec<LegacyProfile>, AppError> {
    migrate::get_profiles(&app_handle).map_err(AppError::from)
}

#[tauri::command]
pub fn import_legacy_profiles(
    app_handle: AppHandle,
    state: tauri::State<AppState>,
    profile_ids: Vec<String>,
) -> Result<bool, AppError> {
    let mut mod_manager = state.mod_manager.lock().map_err(|error| {
        MigrateError::IoError(format!(
            "Failed to acquire lock on mod manager: {:?}",
            error
        ))
    })?;
    migrate::import_profiles(&app_handle, &mut mod_manager, profile_ids).map_err(AppError::from)
}

#[tauri::command]
pub fn import_legacy_mod_authors(
    app_handle: AppHandle,
    state: tauri::State<AppState>,
) -> Result<bool, AppError> {
    let mut mod_manager = state.mod_manager.lock().map_err(|error| {
        MigrateError::IoError(format!(
            "Failed to acquire lock on mod manager: {:?}",
            error
        ))
    })?;
    migrate::import_mod_authors(&app_handle, &mut mod_manager).map_err(AppError::from)
}
