use bd2modmanager_lib::config::config::{AppConfig, PartialAppConfig};
use log::debug;

use crate::AppState;

#[tauri::command]
pub fn get_settings(state: tauri::State<AppState>) -> AppConfig {
    let config = state.config.lock().unwrap();
    config.get_config().clone()
}

#[tauri::command]
pub fn set_settings(state: tauri::State<AppState>, value: PartialAppConfig) -> Result<(), String> {
    let mut config = state.config.lock().map_err(|_| "Lock poisoned")?;
    debug!("Updating config with: {:?}", value);
    config.update_config(value).map_err(|e| e.to_string())
}
