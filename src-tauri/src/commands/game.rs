use std::{fs, path::PathBuf};
use bd2modmanager_lib::{game::{game::{self, VersionResult}, installer::{self, is_bdx_archive, is_bepinex_archive, is_configmanager_archive}}, utils::path::{get_characters_path, get_dating_path}};
use winreg::{enums::HKEY_CURRENT_USER, RegKey};
use log::{info, warn};

use crate::AppState;

fn get_game_path(state: &AppState) -> Option<PathBuf> {
    let config = state.config.lock().unwrap();
    config
        .game_directory
        .as_ref()
        .map(PathBuf::from)
}

#[tauri::command]
pub fn locate_game() -> Option<Vec<String>> {
    let hkcu = RegKey::predef(HKEY_CURRENT_USER);

    let Ok(parent_key) = hkcu.open_subkey(r"Software\Neowiz\Browndust2Starter") else {
        warn!("Browndust2Starter registry key not found");
        return None;
    };

    let path_founds: Vec<String> = parent_key
        .enum_keys()
        .flatten()
        .filter_map(|subkey_name| parent_key.open_subkey(subkey_name).ok())
        .filter_map(|key| key.get_value::<String, _>("path").ok())
        .collect();

    info!("found {} game path(s)", path_founds.len());

    if path_founds.is_empty() {
        info!("no game path(s) found");
        None
    } else {
        Some(path_founds)
    }
}

#[tauri::command]
pub fn validate_game_path(path: String) -> bool {
    PathBuf::from(&path).join("BrownDust II.exe").exists() && PathBuf::from(&path).join("BrownDust II_Data").exists()
}

#[tauri::command]
pub fn get_game_version(state: tauri::State<AppState>) -> Option<String> {
    let game_path = get_game_path(&state)?;
    game::get_game_version(&game_path)
}

#[tauri::command]
pub fn get_characters(app_handle: tauri::AppHandle) -> Result<serde_json::Value, String> {
    let chars_path = get_characters_path(&app_handle).ok_or("failed to get characters path")?;

    let content = std::fs::read_to_string(&chars_path).map_err(|e| e.to_string())?;

    serde_json::from_str(&content).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn get_dating(app_handle: tauri::AppHandle) -> Result<serde_json::Value, String> {
    let dating_path = get_dating_path(&app_handle).ok_or("failed to get dating path")?;

    let content = std::fs::read_to_string(&dating_path).map_err(|e| e.to_string())?;

    serde_json::from_str(&content).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn launch_game(state: tauri::State<AppState>, vanilla: bool) -> Result<(), String> {
    let game_path = get_game_path(&state).ok_or("Game path not set")?;

    let exe_path = game_path.join("BrownDust II.exe");

    if !exe_path.exists() {
        return Err("Game executable not found".to_string());
    }

    if vanilla {
        std::process::Command::new(exe_path)
            .args(["--doorstop-enable", "false", "--doorstop-enabled", "false"])
            .spawn()
            .map_err(|e| e.to_string())?;
    } else {
        std::process::Command::new(exe_path)
            .spawn()
            .map_err(|e| e.to_string())?;
    }

    Ok(())
}

#[tauri::command]
pub fn get_bepinex_version(app_handle: tauri::AppHandle, state: tauri::State<AppState>) -> Option<VersionResult> {
    let game_path = get_game_path(&state)?;
    game::get_bepinex_version(&app_handle, &game_path)
}

#[tauri::command]
pub fn get_browndustx_version(app_handle: tauri::AppHandle, state: tauri::State<AppState>) -> Option<VersionResult> {
    let game_path = get_game_path(&state)?;
    game::get_browndustx_version(&app_handle, &game_path)
}

#[tauri::command]
pub fn get_configmanager_version(app_handle: tauri::AppHandle, state: tauri::State<AppState>) -> Option<VersionResult> {
    let game_path = get_game_path(&state)?;
    game::get_configmanager_version(&app_handle, &game_path)
}

#[tauri::command]
pub async fn install_bepinex(
    state: tauri::State<'_, AppState>, 
    app_handle: tauri::AppHandle,
    path: Option<PathBuf>,
    url: Option<String>
) -> Result<(), installer::InstallBepInExError> {
    let game_path = {
        let config = state.config.lock().map_err(|_| installer::InstallBepInExError::Unknown("Failed to lock config".into()))?;
        config
            .game_directory
            .as_ref()
            .map(PathBuf::from)
            .ok_or_else(|| installer::InstallBepInExError::GamePathNotSet)?
    };

    
    match (path, url) {
        (Some(path), None) => installer::install_bepinex_from_archive(&app_handle, game_path.clone(), path).await,
        (None, Some(url)) => installer::install_bepinex_from_url(&app_handle, game_path.clone(), url).await,
        _ => Err(installer::InstallBepInExError::Unknown("Either path or url must be provided".to_string())),
    }
}

#[tauri::command]
pub async fn uninstall_bepinex(state: tauri::State<'_, AppState>, app_handle: tauri::AppHandle) -> Result<(), installer::UninstallBepInExError> {
    let game_path = {
        let config = state.config.lock().map_err(|_| installer::UninstallBepInExError::Unknown("Failed to lock config".into()))?;
        config
            .game_directory
            .as_ref()
            .map(PathBuf::from)
            .ok_or_else(|| installer::UninstallBepInExError::GamePathNotSet)?
    };

    installer::uninstall_bepinex(&app_handle, &game_path).await
}

#[tauri::command]
pub async fn install_browndustx(
    state: tauri::State<'_, AppState>, 
    app_handle: tauri::AppHandle,
    path: PathBuf
) -> Result<(), installer::InstallPluginError> {
    let game_path = {
        let config = state.config.lock().map_err(|_| installer::InstallPluginError::Unknown("Failed to lock config".into()))?;
        config
            .game_directory
            .as_ref()
            .map(PathBuf::from)
            .ok_or_else(|| installer::InstallPluginError::GamePathNotSet)?
    };

    installer::install_browndustx_plugin_from_archive(&app_handle, &game_path, path).await
}

#[tauri::command]
pub async fn uninstall_browndustx(
    state: tauri::State<'_, AppState>, 
    app_handle: tauri::AppHandle,
) -> Result<(), installer::UninstallPluginError> {
    let game_path = {
        let config = state.config.lock().map_err(|_| installer::UninstallPluginError::Unknown("Failed to lock config".into()))?;
        config
            .game_directory
            .as_ref()
            .map(PathBuf::from)
            .ok_or_else(|| installer::UninstallPluginError::GamePathNotSet)?
    };

    installer::uninstall_browndustx_plugin(&app_handle, &game_path).await
}

#[tauri::command]
pub async fn install_configmanager(
    state: tauri::State<'_, AppState>, 
    app_handle: tauri::AppHandle,
    path: Option<PathBuf>,
    url: Option<String>
) -> Result<(), installer::InstallPluginError> {
    let game_path = {
        let config = state.config.lock().map_err(|_| installer::InstallPluginError::Unknown("Failed to lock config".into()))?;
        config
            .game_directory
            .as_ref()
            .map(PathBuf::from)
            .ok_or_else(|| installer::InstallPluginError::GamePathNotSet)?
    };

    match (path, url) {
        (Some(path), None) => installer::install_configmanager_plugin_from_archive(&app_handle, &game_path, path).await,
        (None, Some(url)) => installer::install_configmanager_plugin_from_url(&app_handle, &game_path, url).await,
        _ => Err(installer::InstallPluginError::Unknown("Either path or url must be provided".to_string())),
    }
}

#[tauri::command]
pub async fn uninstall_configmanager(
    state: tauri::State<'_, AppState>, 
    app_handle: tauri::AppHandle,
) -> Result<(), installer::UninstallPluginError> {
    let game_path = {
        let config = state.config.lock().map_err(|_| installer::UninstallPluginError::Unknown("Failed to lock config".into()))?;
        config
            .game_directory
            .as_ref()
            .map(PathBuf::from)
            .ok_or_else(|| installer::UninstallPluginError::GamePathNotSet)?
    };

    installer::uninstall_configmanager_plugin(&app_handle, &game_path).await
}

#[tauri::command]
pub fn determine_archive_type(path: String) -> Result<Option<String>, String> {
    let archive_path = PathBuf::from(path);
    if !archive_path.exists() {
        return Ok(None);
    }

    let file = fs::File::open(&archive_path).map_err(|e| e.to_string())?;
    let mut archive = zip::ZipArchive::new(file).map_err(|e| e.to_string())?;

    if is_bepinex_archive(&mut archive) {
        return Ok(Some("BEPINEX".to_string()));
    }

    if is_bdx_archive(&mut archive) {
        return Ok(Some("BROWNDUSTX".to_string()));
    }

    if is_configmanager_archive(&mut archive) {
        return Ok(Some("CONFIGMANAGER".to_string()));
    }

    Ok(None)
}