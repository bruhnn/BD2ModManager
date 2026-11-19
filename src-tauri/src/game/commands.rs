use std::{fs, path::PathBuf};
use crate::{game::{game::{self, VersionResult}, installer::{self, is_bdx_archive, is_bepinex_archive, is_configmanager_archive}, locate::{self, LocatedGame}}, utils::path::get_characters_path};
#[cfg(not(windows))]
use crate::game::{launchers, wine};
use log::info;
use serde::Serialize;
#[cfg(windows)]
use log::warn;

use crate::{errors::AppError, AppState};

fn get_game_path(state: &AppState) -> Option<PathBuf> {
    let config = state.config.lock().unwrap();
    config
        .game_directory
        .as_ref()
        .map(PathBuf::from)
}

#[cfg(not(windows))]
#[tauri::command]
pub fn locate_game() -> Option<Vec<LocatedGame>> {
    // TODO: Steam, Lutris, and Wine prefixes
    let found = launchers::locate();
    info!("found {} game path(s)", found.len());
    if found.is_empty() { None } else { Some(found) }
}

#[cfg(windows)]
#[tauri::command]
pub fn locate_game() -> Option<Vec<LocatedGame>> {
    use winreg::{enums::HKEY_CURRENT_USER, RegKey};

    let hkcu = RegKey::predef(HKEY_CURRENT_USER);

    let Ok(parent_key) = hkcu.open_subkey(r"Software\Neowiz\Browndust2Starter") else {
        warn!("Browndust2Starter registry key not found");
        return None;
    };

    let path_founds: Vec<LocatedGame> = parent_key
        .enum_keys()
        .flatten()
        .filter_map(|subkey_name| parent_key.open_subkey(subkey_name).ok())
        .filter_map(|key| key.get_value::<String, _>("path").ok())
        .map(|path| LocatedGame { path, launcher: None })
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
    locate::is_game_dir(&PathBuf::from(&path))
}

// why a staging folder was rejected; the frontend maps `kind` to a message
#[derive(Serialize, thiserror::Error, Debug)]
#[serde(tag = "kind", rename_all = "camelCase")]
pub enum StagingPathError {
    #[error("staging folder and its parents do not exist")]
    NotFound,
    #[error("staging folder overlaps BrownDustX/mods")]
    OverlapsGameMods,
}

#[tauri::command]
pub fn validate_staging_path(
    state: tauri::State<AppState>,
    path: PathBuf,
) -> Result<(), StagingPathError> {
    let Some(game_directory) = get_game_path(&state) else {
        return Ok(());
    };

    let mut paths = [
        path,
        game_directory.join("BepInEx/plugins/BrownDustX/mods"),
    ];

    for path in &mut paths {
        // resolve the existing part of the path
        let Some(parent) = path.ancestors().find(|parent| parent.exists()) else {
            return Err(StagingPathError::NotFound);
        };

        let Ok(resolved) = parent.canonicalize() else {
            return Err(StagingPathError::NotFound);
        };

        let resolved = resolved.join(path.strip_prefix(parent).unwrap());
        *path = PathBuf::from(resolved.to_string_lossy().to_lowercase());
    }

    let staging = &paths[0];
    let game_mods = &paths[1];

    if staging.starts_with(game_mods) || game_mods.starts_with(staging) {
        return Err(StagingPathError::OverlapsGameMods);
    }

    Ok(())
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

#[cfg(windows)]
#[tauri::command]
pub fn launch_game(state: tauri::State<AppState>, vanilla: bool) -> Result<(), AppError> {
    let game_path = get_game_path(&state).ok_or(AppError::GameDirectoryNotSet)?;

    let exe_path = game_path.join("BrownDust II.exe");

    if !exe_path.exists() {
        return Err(AppError::GameExecutableNotFound {
            path: exe_path.to_string_lossy().to_string(),
        });
    }

    let mut command = std::process::Command::new(exe_path);
    if vanilla {
        command.args(["--doorstop-enable", "false", "--doorstop-enabled", "false"]);
    }
    command
        .spawn()
        .map_err(|e| AppError::GameLaunchFailed { reason: e.to_string() })?;

    Ok(())
}

#[cfg(not(windows))]
#[tauri::command]
pub fn launch_game(state: tauri::State<AppState>, vanilla: bool) -> Result<(), AppError> {
    if vanilla {
        // TODO: launchers can't pass --doorstop-enable false; needs another way to turn BepInEx off
        return Err(AppError::LaunchWithoutModsUnsupported);
    }

    let game_path = get_game_path(&state).ok_or(AppError::GameDirectoryNotSet)?;

    let entry = launchers::entry_for(&game_path).ok_or(AppError::GameLauncherNotFound)?;

    wine::ensure_bepinex_override(&game_path, entry.prefix.as_deref());

    info!("Launching {:?} through {:?} ({})", game_path, entry.app, entry.game_id);
    launchers::launch(&entry).map_err(|e| AppError::GameLaunchFailed { reason: e.to_string() })
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

    let result = match (path, url) {
        (Some(path), None) => installer::install_bepinex_from_archive(&app_handle, game_path.clone(), path).await,
        (None, Some(url)) => installer::install_bepinex_from_url(&app_handle, game_path.clone(), url).await,
        _ => Err(installer::InstallBepInExError::Unknown("Either path or url must be provided".to_string())),
    };

    #[cfg(not(windows))]
    if result.is_ok() {
        let _ = tokio::task::spawn_blocking(move || {
            let prefix = launchers::entry_for(&game_path).and_then(|entry| entry.prefix);
            wine::ensure_bepinex_override(&game_path, prefix.as_deref());
        })
        .await;
    }

    result
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