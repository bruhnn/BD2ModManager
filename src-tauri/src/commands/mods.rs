use std::{fs, path::PathBuf};

use bd2modmanager_lib::{
    mods::{BD2Mod, sync::{SyncError, SyncMethod}},
    utils::path::{get_mod_preview_path, get_staging_dir},
};
use serde::Serialize;
use tauri::AppHandle;
use tauri_plugin_opener::OpenerExt;

use crate::AppState;

#[tauri::command]
pub fn discover_mods(app_handle: tauri::AppHandle, state: tauri::State<AppState>) {
    let config = state.config.lock().unwrap();
    let mut mod_manager = state.mod_manager.lock().unwrap();
    mod_manager.discover_mods(
        &app_handle,
        &get_staging_dir(&config),
        config.search_mods_recursively,
    );
}

#[tauri::command]
pub fn get_mods(state: tauri::State<AppState>) -> Vec<BD2Mod> {
    let mod_manager = state.mod_manager.lock().unwrap();
    let mut mods: Vec<BD2Mod> = mod_manager.cached_mods.values().cloned().collect();

    mods.sort_by(|a, b| a.name.cmp(&b.name));
    mods
}

#[tauri::command]
pub fn enable_mods(
    app_handle: tauri::AppHandle,
    state: tauri::State<AppState>,
    mod_names: Vec<String>,
) {
    let mut mod_manager = state.mod_manager.lock().unwrap();
    mod_manager.enable_mods(&app_handle, mod_names);
}

#[tauri::command]
pub fn disable_mods(
    app_handle: tauri::AppHandle,
    state: tauri::State<AppState>,
    mod_names: Vec<String>,
) {
    let mut mod_manager = state.mod_manager.lock().unwrap();
    mod_manager.disable_mods(&app_handle, mod_names);
}

#[tauri::command]
pub fn enable_mods_in_profile(
    app_handle: tauri::AppHandle,
    state: tauri::State<AppState>,
    profile_id: String,
    mod_names: Vec<String>,
) -> Result<(), bd2modmanager_lib::profiles::types::ProfileError> {
    let mut mod_manager = state.mod_manager.lock().unwrap();
    mod_manager.enable_mods_in_profile(&app_handle, &profile_id, mod_names)
}

/// Replace a profile's entire enabled-mods list.
#[tauri::command]
pub fn set_profile_enabled_mods(
    app_handle: tauri::AppHandle,
    state: tauri::State<AppState>,
    profile_id: String,
    mod_names: Vec<String>,
) -> Result<(), bd2modmanager_lib::profiles::types::ProfileError> {
    let mut mod_manager = state.mod_manager.lock().unwrap();
    mod_manager.set_profile_enabled_mods(&app_handle, &profile_id, mod_names)
}

// Check if the folder is a texture mod
fn is_texture_mod(path: &PathBuf) -> bool {
    if !path.join("textures").is_dir() {
        return false;
    }

    let has_skel = fs::read_dir(path)
        .map(|entries| {
            entries.filter_map(Result::ok).any(|entry| {
                entry
                    .path()
                    .extension()
                    .map(|e| e == "skel")
                    .unwrap_or(false)
            })
        })
        .unwrap_or(false);

    let has_atlas = fs::read_dir(path)
        .map(|entries| {
            entries.filter_map(Result::ok).any(|entry| {
                entry
                    .path()
                    .extension()
                    .map(|e| e == "atlas")
                    .unwrap_or(false)
            })
        })
        .unwrap_or(false);

    !has_skel && !has_atlas
}

fn preview_image(app_handle: AppHandle, path: &PathBuf) -> tauri::Result<()> {
    let dir = path.join("textures");
    if !dir.exists() {
        return Ok(());
    }

    let mut img_path: Option<PathBuf> = None;
    for entry in fs::read_dir(&dir)? {
        let entry = entry?;
        let path = entry.path();

        if path.is_file() && path.extension().map(|e| e == "png").unwrap_or(false) {
            img_path = Some(path);
            break;
        }
    }

    if let Some(img) = img_path {
        let img_str = img.to_string_lossy().to_string();
        app_handle.opener().open_path(img_str, None::<&str>).ok();
    }

    Ok(())
}

// Tauri command
#[tauri::command]
pub fn preview_mod(app_handle: AppHandle, path: String) -> tauri::Result<()> {
    let path_buf = PathBuf::from(&path);

    if is_texture_mod(&path_buf) {
        return preview_image(app_handle, &path_buf);
    }

    if let Some(mod_preview_exe) = get_mod_preview_path(&app_handle) {
        std::process::Command::new(mod_preview_exe)
            .arg(path)
            .spawn()
            .ok();
    }

    Ok(())
}

#[tauri::command]
pub fn install_mod_from_zip(
    app_handle: tauri::AppHandle,
    state: tauri::State<AppState>,
    path: String,
) -> Result<String, bd2modmanager_lib::mods::install::ModInstallError> {
    let config = state.config.lock().unwrap();
    let staging_dir = get_staging_dir(&config);
    let mut mod_manager = state.mod_manager.lock().unwrap();
    mod_manager.install_mod(&app_handle, PathBuf::from(path), &staging_dir)
}

#[tauri::command]
pub fn install_mod_from_folder(
    app_handle: tauri::AppHandle,
    state: tauri::State<AppState>,
    path: String,
) -> Result<String, bd2modmanager_lib::mods::install::ModInstallError> {
    let config = state.config.lock().unwrap();
    let staging_dir = get_staging_dir(&config);
    let mut mod_manager = state.mod_manager.lock().unwrap();
    mod_manager.install_mod(&app_handle, PathBuf::from(path), &staging_dir)
}

#[derive(Serialize, Clone, Debug)]
pub enum SyncCommandError {
    GameDirectoryNotSet,
    SyncMethodInvalid(String),
    SyncFailed(SyncError), 
    UnknownError(String),
}

impl From<SyncError> for SyncCommandError {
    fn from(e: SyncError) -> Self {
        SyncCommandError::SyncFailed(e)
    }
}

#[tauri::command]
pub async fn sync_mods(
    app_handle: tauri::AppHandle,
    state: tauri::State<'_, AppState>,
) -> Result<(), SyncCommandError> {
    let app_handle = app_handle.clone();
    let config_handle = state.config.clone();
    let mod_manager_handle = state.mod_manager.clone();

    let result = tauri::async_runtime::spawn_blocking(move || {
        let config = config_handle.lock().unwrap();
        let mut mod_manager = mod_manager_handle.lock().unwrap();

        let sync_method = match config.sync_method.as_str() {
            "copy" => SyncMethod::Copy,
            "hardlink" => SyncMethod::Hardlink,
            "symlink" => SyncMethod::Symlink,
            other => return Err(SyncCommandError::SyncMethodInvalid(other.to_string())),
        };

        let game_dir = match &config.game_directory {
            Some(dir) => dir.clone(),
            None => return Err(SyncCommandError::GameDirectoryNotSet),
        };

        mod_manager
            .sync_mods(&app_handle, &PathBuf::from(game_dir), sync_method)
            .map_err(SyncCommandError::from)
    })
    .await;

    match result {
        Ok(r) => r,
        Err(e) => {
            eprintln!("Sync task panicked: {:?}", e);
            Err(SyncCommandError::UnknownError(format!("{:?}", e)))
        }
    }
}

#[tauri::command]
pub async fn unsync_mods(
    app_handle: tauri::AppHandle,
    state: tauri::State<'_, AppState>,
) -> Result<(), SyncCommandError> {
    let app_handle_clone = app_handle.clone();
    let mod_manager_handle = state.mod_manager.clone();
    let config_handle = state.config.clone();

    let game_dir = {
        let config = config_handle.lock().unwrap();
        match &config.game_directory {
            Some(dir) => dir.clone(),
            None => return Err(SyncCommandError::GameDirectoryNotSet),
        }
    };

    let result = tauri::async_runtime::spawn_blocking(move || {
        let mut mod_manager = mod_manager_handle.lock().unwrap();
        mod_manager.unsync_mods(&app_handle_clone, &PathBuf::from(game_dir)).map_err(SyncCommandError::from)
    })
    .await;

    match result {
        Ok(r) => r,
        Err(e) => {
            eprintln!("Unsync task panicked: {:?}", e);
            Err(SyncCommandError::UnknownError(format!("{:?}", e)))
        }
    }
}

#[tauri::command]
pub fn is_sync_needed(
    app_handle: tauri::AppHandle,
    state: tauri::State<'_, AppState>,
) -> Result<bool, SyncCommandError> {
    let mod_manager = state.mod_manager.lock().unwrap();
    let config = state.config.lock().unwrap();

    let game_dir = match &config.game_directory {
        Some(dir) => dir.clone(),
        None => return Err(SyncCommandError::GameDirectoryNotSet),
    };

    Ok(mod_manager.is_sync_needed(&app_handle, &PathBuf::from(game_dir)))
}

#[tauri::command]
pub async fn delete_mods(
    app_handle: tauri::AppHandle,
    state: tauri::State<'_, AppState>,
    mod_names: Vec<String>,
) -> Result<(), String> {
    let mod_manager_handle = state.mod_manager.clone();
    let app_handle_clone = app_handle.clone();
    let result = tauri::async_runtime::spawn_blocking(move || {
        let mut mod_manager = mod_manager_handle.lock().unwrap();
        let _ = mod_manager.delete_mods(&app_handle_clone, mod_names);
        Ok(())
    })
    .await;

    match result {
        Ok(r) => r,
        Err(e) => {
            eprintln!("Delete mods task panicked: {:?}", e);
            Err(format!("Delete mods task panicked: {:?}", e))
        }
    }
}

#[tauri::command]
pub async fn rename_mod(
    app_handle: tauri::AppHandle,
    state: tauri::State<'_, AppState>,
    old_name: String,
    new_name: String,
) -> Result<(), String> {
    let mod_manager_handle = state.mod_manager.clone();
    let app_handle_clone = app_handle.clone();
    let result = tauri::async_runtime::spawn_blocking(move || {
        let mut mod_manager = mod_manager_handle.lock().unwrap();
        let _ = mod_manager.rename_mod(&app_handle_clone, old_name, new_name);
        Ok(())
    })
    .await;

    match result {
        Ok(r) => r,
        Err(e) => {
            eprintln!("Rename mod task panicked: {:?}", e);
            Err(format!("Rename mod task panicked: {:?}", e))
        }
    }
}

#[tauri::command]
pub fn set_mod_author(
    app_handle: tauri::AppHandle,
    state: tauri::State<AppState>,
    mod_names: Vec<String>,
    author: Option<String>,
) {
    let mut mod_manager = state.mod_manager.lock().unwrap();
    mod_manager.set_mod_author(&app_handle, mod_names, author);
}