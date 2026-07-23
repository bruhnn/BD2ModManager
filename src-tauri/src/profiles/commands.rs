use crate::profiles::types::{Profile, ProfileError};
use serde::{Deserialize, Serialize};

use crate::{AppState};

#[derive(Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProfilesResult {
    active_profile: Profile,
    profiles: Vec<Profile>,
}

#[tauri::command]
pub fn get_profiles(state: tauri::State<AppState>) -> ProfilesResult {
    let mut mod_manager = state.mod_manager.lock().unwrap();
    let profiles: Vec<Profile> = mod_manager.get_profiles();
    let active_profile: Profile = mod_manager.get_active_profile().unwrap().clone();

    ProfilesResult {
        active_profile: active_profile,
        profiles: profiles,
    }
}

#[tauri::command]
pub fn switch_profile(
    state: tauri::State<AppState>,
    app_handle: tauri::AppHandle,
    id: String,
) -> Result<(), ProfileError> {
    let mut mod_manager = state.mod_manager.lock().unwrap();
    mod_manager.switch_profile(&app_handle, id)
}

#[tauri::command]
pub fn edit_profile(
    state: tauri::State<AppState>,
    id: String,
    name: String,
    description: Option<String>,
) -> Result<(), ProfileError> {
    let mut mod_manager = state.mod_manager.lock().unwrap();
    mod_manager.edit_profile(id, name, description)
}

#[tauri::command]
pub fn create_profile(
    state: tauri::State<AppState>,
    name: String,
    description: Option<String>,
    template_id: Option<String>,
) -> Result<(), ProfileError> {
    let mut mod_manager = state.mod_manager.lock().unwrap();
    mod_manager.create_profile(name, description, template_id)
}

#[tauri::command]
pub fn delete_profile(
    app_handle: tauri::AppHandle,
    state: tauri::State<AppState>,
    id: String,
) -> Result<(), ProfileError> {
    let mut mod_manager = state.mod_manager.lock().unwrap();
    mod_manager.delete_profile(&app_handle, id)
}
