use std::{path::PathBuf};

use bd2modmanager_lib::{
    ModError, mods::{BD2Mod, install::ModInstallError, preview::{PreviewError, is_texture_mod, preview_image}, sync::SyncMethod, types::BD2ModError}, utils::path::{get_mod_preview_path, get_staging_dir},
};
use serde::Serialize;
use tauri::{AppHandle, ipc::Channel};

use crate::AppState;
use log::{error};

#[tauri::command]
pub async fn discover_mods(
    _app_handle: tauri::AppHandle,
    state: tauri::State<'_, AppState>,
) -> Result<Vec<BD2Mod>, ModError> {
    let config = state.config.lock().unwrap().clone();
    let mod_manager = state.mod_manager.clone();

    let result = tauri::async_runtime::spawn_blocking(move || {
        let mut mod_manager = mod_manager.lock().unwrap();

        mod_manager.discover_mods(
            &get_staging_dir(&config),
            config.search_mods_recursively,
        )
    })
    .await;

    result.map_err(|error| {
        error!("Discover mods task panicked: {:?}", error);
        ModError::Unknown(format!("{:?}", error))
    })
}

#[tauri::command]
pub fn get_mods(state: tauri::State<AppState>) -> Vec<BD2Mod> {
    let mod_manager = state.mod_manager.lock().unwrap();
    mod_manager.get_mods()
}

#[tauri::command]
pub fn enable_mods(
    _app_handle: tauri::AppHandle,
    state: tauri::State<AppState>,
    mod_names: Vec<String>,
) -> Vec<BD2Mod> {
    let mut mod_manager = state.mod_manager.lock().unwrap();
    mod_manager.enable_mods(mod_names)
}

#[tauri::command]
pub fn disable_mods(
    _app_handle: tauri::AppHandle,
    state: tauri::State<AppState>,
    mod_names: Vec<String>,
) -> Vec<BD2Mod> {
    let mut mod_manager = state.mod_manager.lock().unwrap();
    mod_manager.disable_mods(mod_names)
}

#[tauri::command]
pub fn preview_mod(app_handle: AppHandle, state: tauri::State<AppState>, mod_name: String) -> Result<(), ModError> {
    let mod_manager = state.mod_manager.lock().unwrap();
    let _mod: BD2Mod = mod_manager.get_mod_by_name(&mod_name).ok_or_else(|| PreviewError::NotFound(mod_name.clone()))?;
    
    // check if the mod has errors, like it is a zip file that is not extracted, or a folder that is missing required files, but for example it is only missing modfile there is no problem
    // BD2ModError
    if _mod.errors.iter().any(|e| !matches!(e, BD2ModError::MissingModfile | BD2ModError::HasConflict)) {
        return Err(PreviewError::ModHasErrors(mod_name))?;
    }

    let path_buf = PathBuf::from(&_mod.path);

    if !path_buf.exists() {
        return Err(PreviewError::NotFound(mod_name))?;
    }

    if is_texture_mod(&path_buf) {
        return Ok(preview_image(app_handle, &path_buf)?);
    }

    if let Some(mod_preview_exe) = get_mod_preview_path(&app_handle) {
        std::process::Command::new(mod_preview_exe)
            .arg(&path_buf)
            .spawn()
            .map_err(|e| PreviewError::Failed(e.to_string()))?;
    }

    Ok(())
}

#[tauri::command]
pub fn install_mod_from_zip(
    _app_handle: tauri::AppHandle,
    state: tauri::State<AppState>,
    path: String,
) -> Result<BD2Mod, ModInstallError> {
    let config = state.config.lock().unwrap();
    let staging_dir = get_staging_dir(&config);
    let mut mod_manager = state.mod_manager.lock().unwrap();
    Ok(mod_manager.install_mod(PathBuf::from(path), &staging_dir)?)
}

#[tauri::command]
pub fn install_mod_from_folder(
    _app_handle: tauri::AppHandle,
    state: tauri::State<AppState>,
    path: String,
) -> Result<BD2Mod, ModError> {
    let config = state.config.lock().unwrap();
    let staging_dir = get_staging_dir(&config);
    let mut mod_manager = state.mod_manager.lock().unwrap();
    Ok(mod_manager.install_mod(PathBuf::from(path), &staging_dir)?)
}

// Sync and unsync uses global events
// sync-start
// sync-progress
// sync-end
#[tauri::command]
pub async fn sync_mods(
    app_handle: tauri::AppHandle,
    state: tauri::State<'_, AppState>,
) -> Result<(), ModError> {
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
            other => return Err(ModError::SyncMethodInvalid(other.to_string())),
        };

        let game_dir = match &config.game_directory {
            Some(dir) => dir.clone(),
            None => return Err(ModError::GameDirectoryNotSet),
        };

        mod_manager
            .sync_mods(&app_handle, &PathBuf::from(game_dir), sync_method)
            .map_err(ModError::from)
    })
    .await;

    match result {
        Ok(r) => r,
        Err(e) => {
            eprintln!("Sync task panicked: {:?}", e);
            Err(ModError::Unknown(format!("{:?}", e)))
        }
    }
}

#[tauri::command]
pub async fn unsync_mods(
    app_handle: tauri::AppHandle,
    state: tauri::State<'_, AppState>,
) -> Result<(), ModError> {
    let app_handle_clone = app_handle.clone();
    let mod_manager_handle = state.mod_manager.clone();
    let config_handle = state.config.clone();

    let game_dir = {
        let config = config_handle.lock().unwrap();
        match &config.game_directory {
            Some(dir) => dir.clone(),
            None => return Err(ModError::GameDirectoryNotSet),
        }
    };

    let result = tauri::async_runtime::spawn_blocking(move || {
        let mut mod_manager = mod_manager_handle.lock().unwrap();
        mod_manager
            .unsync_mods(&app_handle_clone, &PathBuf::from(game_dir))
            .map_err(ModError::from)
    })
    .await;

    match result {
        Ok(r) => r,
        Err(e) => {
            eprintln!("Unsync task panicked: {:?}", e);
            Err(ModError::Unknown(format!("{:?}", e)))
        }
    }
}


#[tauri::command]
pub fn is_sync_needed(
    _app_handle: tauri::AppHandle,
    state: tauri::State<'_, AppState>,
) -> Result<bool, ModError> {
    let mod_manager = state.mod_manager.lock().unwrap();
    let config = state.config.lock().unwrap();
    let game_dir = config
        .game_directory
        .clone()
        .ok_or(ModError::GameDirectoryNotSet)?;
    Ok(mod_manager.is_sync_needed(&PathBuf::from(game_dir)))
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DeleteModsProgress {
    pub current: usize,
    pub total: usize,
    pub mod_name: String,
}

#[derive(Clone, Serialize)]
pub struct DeleteModsResult {
    pub mods: Vec<BD2Mod>,
    pub deleted: Vec<String>,
    pub failed: Vec<(String, String)>,
}

#[tauri::command]
pub async fn delete_mods(
    state: tauri::State<'_, AppState>,
    mod_names: Vec<String>,
    on_progress: Channel<DeleteModsProgress>
) -> Result<DeleteModsResult, ModError> {
    let mod_manager_handle = state.mod_manager.clone();
    let result = tauri::async_runtime::spawn_blocking(move || {
        let mut mod_manager = mod_manager_handle.lock().unwrap();

        let total = mod_names.len();
        let mut deleted = Vec::new();
        let mut failed = Vec::new();

        for (index, mod_name) in mod_names.iter().enumerate() {
            let _ = on_progress.send(DeleteModsProgress {
                current: index + 1,
                total,
                mod_name: mod_name.clone(),
            });

            match mod_manager.delete_mod(mod_name.clone()) {
                Ok(()) => {
                    deleted.push(mod_name.clone());
                }
                Err(error) => {
                    failed.push((mod_name.clone(), error.to_string()));
                }
            }
        }

        let all_mods: Vec<BD2Mod> = mod_manager.get_mods();

        DeleteModsResult {
            mods: all_mods, deleted, failed
        }
    })
    .await;

    result.map_err(|e| {
        error!("Delete mods task panicked: {:?}", e);
        ModError::Unknown(format!("{:?}", e))
    })
}

#[tauri::command]
pub async fn rename_mod(
    _app_handle: tauri::AppHandle,
    state: tauri::State<'_, AppState>,
    mod_name: String,
    new_name: String,
) -> Result<BD2Mod, ModError> {
    // [TODO] improve renaming
    let mod_manager_handle = state.mod_manager.clone();
    let result = tauri::async_runtime::spawn_blocking(move || {
        let mut mod_manager = mod_manager_handle.lock().unwrap();
        mod_manager.rename_mod(mod_name, new_name)
    })
    .await;

    result
        .map_err(|e| {
            error!("Rename mod task panicked: {:?}", e);
            ModError::Unknown(format!("{:?}", e))
        })?
        .map_err(ModError::from)
}







/// [INFO] Metadata commnds

#[tauri::command]
pub fn set_mod_author(
    state: tauri::State<AppState>,
    mod_names: Vec<String>,
    author: Option<String>,
) -> Result<Vec<BD2Mod>, ModError> {
    let mut mod_manager = state.mod_manager.lock().unwrap();
    mod_manager.set_mod_author(mod_names, author).map_err(ModError::Metadata)
}