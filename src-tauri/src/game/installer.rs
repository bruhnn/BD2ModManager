use std::{fs, path::PathBuf};

use serde::Serialize;
use serde_json::Map;
use tauri::Manager;
use zip::result::ZipError;

use crate::utils::{files::cleanup_empty_dirs, misc::get_dll_version};

use log::error;

const BEPINEX_COMMON_FILES: [&str; 2] = [
    "BepInEx/core/BepInEx.dll",
    "winhttp.dll",
];

const BDX_COMMON_FILES: [&str; 3] = [
    "BepInEx/plugins/BrownDustX/lynesth.bd2.browndustx.dll",
    "BepInEx/plugins/BrownDustX/K4os.Compression.LZ4.dll",
    "BepInEx/plugins/BrownDustX/resources/",
];

const CONFIGMANAGER_COMMON_FILES: [&str; 1] =
    ["BepInEx/plugins/ConfigurationManager/ConfigurationManager.dll"];

fn manifest_path(app_handle: &tauri::AppHandle) -> Result<PathBuf, String> {
    app_handle
        .path()
        .app_data_dir()
        .map(|d| d.join("installer_manifest.json"))
        .map_err(|_| "Failed to get app data directory".to_string())
}

pub fn read_manifest(
    app_handle: &tauri::AppHandle,
    name: &str,
) -> Result<Map<String, serde_json::Value>, String> {
    let path = manifest_path(app_handle)?;

    if !path.exists() {
        return Ok(Map::new());
    }

    let content = match fs::read_to_string(&path) {
        Ok(cnt) => cnt,
        Err(error) => {
            error!("Failed to read manifest: {}", error);
            return Ok(Map::new());
        }
    };

    let manifest: serde_json::Map<String, serde_json::Value> = match serde_json::from_str(&content)
    {
        Ok(data) => data,
        Err(error) => {
            error!("Failed to parse manifest: {}", error);
            return Ok(Map::new());
        }
    };

    Ok(manifest
        .get(name)
        .and_then(|v| v.as_object())
        .cloned()
        .unwrap_or_default())
}

fn read_manifest_files(app_handle: &tauri::AppHandle, name: &str) -> Result<Vec<String>, String> {
    let map = read_manifest(app_handle, name)?;
    Ok(map
        .get("files")
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|v| v.as_str().map(String::from))
                .collect()
        })
        .unwrap_or_default())
}

fn write_manifest(
    app_handle: &tauri::AppHandle,
    name: &str,
    version: &str,
    files: Vec<String>,
) -> Result<(), String> {
    let path = manifest_path(app_handle)?;

    let mut manifest: serde_json::Map<String, serde_json::Value> = if path.exists() {
        let content =
            fs::read_to_string(&path).map_err(|e| format!("Failed to read manifest: {}", e))?;

        match serde_json::from_str(&content) {
            Ok(data) => data,
            Err(e) => {
                error!("Failed to parse manifest, overwriting: {}", e);
                serde_json::Map::new()
            }
        }
    } else {
        serde_json::Map::new()
    };

    manifest.insert(
        name.to_string(),
        serde_json::json!({ "version": version, "files": files }),
    );

    fs::write(&path, serde_json::to_string_pretty(&manifest).unwrap())
        .map_err(|e| format!("Failed to write manifest: {}", e))
}

fn clear_manifest(app_handle: &tauri::AppHandle, name: &str) -> Result<(), String> {
    let path = manifest_path(app_handle)?;

    if !path.exists() {
        return Ok(());
    }

    let content =
        fs::read_to_string(&path).map_err(|e| format!("Failed to read manifest: {}", e))?;

    let mut manifest: serde_json::Map<String, serde_json::Value> =
        match serde_json::from_str(&content) {
            Ok(data) => data,
            Err(e) => {
                error!("Failed to parse manifest, treating as empty: {}", e);
                serde_json::Map::new()
            }
        };

    manifest.remove(name);

    fs::write(&path, serde_json::to_string_pretty(&manifest).unwrap())
        .map_err(|e| format!("Failed to write manifest: {}", e))
}

pub fn migrate_old_manifest(
    app_handle: &tauri::AppHandle,
    old_path: PathBuf,
    name: &str,
) -> Result<(), String> {
    if !old_path.exists() {
        return Ok(());
    }

    let existing = read_manifest(app_handle, name)?;
    if !existing.is_empty() {
        fs::remove_file(&old_path).ok();
        return Ok(());
    }

    let content =
        fs::read_to_string(&old_path).map_err(|e| format!("Failed to read old manifest: {}", e))?;
    let json: serde_json::Value = serde_json::from_str(&content)
        .map_err(|e| format!("Failed to parse old manifest: {}", e))?;

    let files: Vec<String> = json
        .get("installed_files")
        .and_then(|v| v.as_array())
        .unwrap_or(&vec![])
        .iter()
        .filter_map(|v| v.as_str().map(String::from))
        .collect();

    let version = json
        .get("version")
        .and_then(|v| v.as_str())
        .unwrap_or("unknown");

    write_manifest(app_handle, name, version, files)?;
    fs::remove_file(&old_path).ok();

    Ok(())
}

pub fn is_bepinex_archive<R: std::io::Read + std::io::Seek>(
    archive: &mut zip::ZipArchive<R>,
) -> bool {
    BEPINEX_COMMON_FILES
        .iter()
        .all(|f| archive.by_name(f).is_ok())
}

pub fn is_bdx_archive<R: std::io::Read + std::io::Seek>(archive: &mut zip::ZipArchive<R>) -> bool {
    BDX_COMMON_FILES.iter().all(|f| archive.by_name(f).is_ok())
}

pub fn is_configmanager_archive<R: std::io::Read + std::io::Seek>(
    archive: &mut zip::ZipArchive<R>,
) -> bool {
    CONFIGMANAGER_COMMON_FILES
        .iter()
        .all(|f| archive.by_name(f).is_ok())
}

fn extract_zip<R: std::io::Read + std::io::Seek>(
    archive: &mut zip::ZipArchive<R>,
    dest_path: PathBuf,
) -> Result<Vec<String>, ZipError> {
    let mut extracted_files: Vec<String> = Vec::new();

    for i in 0..archive.len() {
        let mut file = archive.by_index(i)?;

        let Some(path) = file.enclosed_name() else {
            continue;
        };

        extracted_files.push(path.to_string_lossy().to_string());
        let outpath = dest_path.join(path);

        if file.is_dir() {
            fs::create_dir_all(&outpath).map_err(ZipError::Io)?;
        } else {
            if let Some(parent) = outpath.parent() {
                fs::create_dir_all(parent).map_err(ZipError::Io)?;
            }
            let mut outfile = fs::File::create(&outpath).map_err(ZipError::Io)?;
            std::io::copy(&mut file, &mut outfile).map_err(ZipError::Io)?;
        }
    }

    Ok(extracted_files)
}

fn check_bepinex_installed(game_path: &PathBuf) -> bool {
    game_path.join("BepInEx/core/BepInEx.dll").exists()
}

fn check_bdx_plugin_installed(game_path: &PathBuf) -> bool {
    game_path
        .join("BepInEx/plugins/BrownDustX/lynesth.bd2.browndustx.dll")
        .exists()
}

#[derive(Serialize, thiserror::Error, Debug)]
pub enum InstallBepInExError {
    #[error("Game path is not set")]
    GamePathNotSet,
    #[error("BepInEx is already installed")]
    BepInExAlreadyInstalled,
    #[error("Invalid BepInEx archive: {0}")]
    InvalidBepInExArchive(String),
    #[error("Download failed: {0}")]
    DownloadFailed(String),
    #[error("Extraction failed: {0}")]
    ExtractionFailed(String),
    #[error("Archive not found: {0}")]
    ArchiveNotFound(String),
    #[error("Unknown error: {0}")]
    Unknown(String),
}

pub async fn install_bepinex_from_archive(
    app_handle: &tauri::AppHandle,
    game_path: PathBuf,
    path: PathBuf,
) -> Result<(), InstallBepInExError> {
    if check_bepinex_installed(&game_path) {
        return Err(InstallBepInExError::BepInExAlreadyInstalled);
    }

    if !path.exists() || !path.is_file() {
        return Err(InstallBepInExError::ArchiveNotFound(
            path.to_string_lossy().to_string(),
        ));
    }

    let game_path_clone = game_path.clone();
    let extracted_files = tokio::task::spawn_blocking(move || {
        let file = fs::File::open(&path)
            .map_err(|e| InstallBepInExError::ArchiveNotFound(e.to_string()))?;
        let mut archive = zip::ZipArchive::new(file)
            .map_err(|_| InstallBepInExError::InvalidBepInExArchive("Failed to open zip".into()))?;
        if !is_bepinex_archive(&mut archive) {
            return Err(InstallBepInExError::InvalidBepInExArchive(
                "Archive does not contain required BepInEx files".into(),
            ));
        }
        extract_zip(&mut archive, game_path_clone)
            .map_err(|e| InstallBepInExError::ExtractionFailed(e.to_string()))
    })
    .await
    .map_err(|e| InstallBepInExError::ExtractionFailed(e.to_string()))??;

    let version = get_dll_version(&game_path.join("BepInEx/core/BepInEx.dll"))
        .unwrap_or_else(|| "unknown".into());

    write_manifest(&app_handle, "BepInEx", &version, extracted_files)
        .map_err(|e| InstallBepInExError::Unknown(e))
}

pub async fn install_bepinex_from_url(
    app_handle: &tauri::AppHandle,
    game_path: PathBuf,
    url: String,
) -> Result<(), InstallBepInExError> {
    if check_bepinex_installed(&game_path) {
        return Err(InstallBepInExError::BepInExAlreadyInstalled);
    }

    let response = reqwest::get(&url)
        .await
        .map_err(|e| InstallBepInExError::DownloadFailed(e.to_string()))?;

    if !response.status().is_success() {
        return Err(InstallBepInExError::DownloadFailed(format!(
            "HTTP {}",
            response.status()
        )));
    }

    let bytes = response
        .bytes()
        .await
        .map_err(|e| InstallBepInExError::DownloadFailed(e.to_string()))?
        .to_vec();

    let game_path_clone = game_path.clone();
    let extracted_files = tokio::task::spawn_blocking(move || {
        let cursor = std::io::Cursor::new(bytes);
        let mut archive = zip::ZipArchive::new(cursor)
            .map_err(|_| InstallBepInExError::InvalidBepInExArchive("Failed to open zip".into()))?;
        if !is_bepinex_archive(&mut archive) {
            return Err(InstallBepInExError::InvalidBepInExArchive(
                "Archive does not contain required BepInEx files".into(),
            ));
        }
        extract_zip(&mut archive, game_path_clone)
            .map_err(|e| InstallBepInExError::ExtractionFailed(e.to_string()))
    })
    .await
    .map_err(|e| InstallBepInExError::ExtractionFailed(e.to_string()))??;

    let version = get_dll_version(&game_path.join("BepInEx/core/BepInEx.dll"))
        .unwrap_or_else(|| "unknown".into());

    write_manifest(&app_handle, "BepInEx", &version, extracted_files)
        .map_err(|e| InstallBepInExError::Unknown(e))
}

#[derive(Serialize, thiserror::Error, Debug)]
pub enum UninstallBepInExError {
    #[error("Game path is not set")]
    GamePathNotSet,
    #[error("BepInEx is not installed")]
    BepInExNotInstalled,
    #[error("Cannot uninstall BepInEx while plugins are still installed: {0:?}")]
    PluginsStillInstalled(Vec<String>),
    #[error("Manifest not found")]
    ManifestNotFound,
    #[error("Unknown error: {0}")]
    Unknown(String),
}

pub async fn uninstall_bepinex(
    app_handle: &tauri::AppHandle,
    game_path: &PathBuf,
) -> Result<(), UninstallBepInExError> {
    if !check_bepinex_installed(&game_path) {
        return Err(UninstallBepInExError::BepInExNotInstalled);
    }

    let mut installed_plugins = vec![];
    if check_bdx_plugin_installed(&game_path) {
        installed_plugins.push("BrownDustX".to_string());
    }
    if game_path
        .join("BepInEx/plugins/ConfigurationManager/ConfigurationManager.dll")
        .exists()
    {
        installed_plugins.push("ConfigurationManager".to_string());
    }
    if !installed_plugins.is_empty() {
        return Err(UninstallBepInExError::PluginsStillInstalled(
            installed_plugins,
        ));
    }

    migrate_old_manifest(
        &app_handle,
        game_path.join("BepInEx/.bd2mm_bepinex_manifest.json"),
        "BepInEx",
    )
    .map_err(|e| UninstallBepInExError::Unknown(e))?;

    let mut files_to_remove = read_manifest_files(&app_handle, "BepInEx")
        .map_err(|e| UninstallBepInExError::Unknown(e))?;

    if files_to_remove.is_empty() {
        return Err(UninstallBepInExError::ManifestNotFound);
    }

    files_to_remove.reverse();

    for file_str in &files_to_remove {
        let file_path = game_path.join(file_str);

        if !file_path.exists() {
            continue;
        }

        if file_path.is_file() {
            fs::remove_file(&file_path).map_err(|e| {
                UninstallBepInExError::Unknown(format!("Failed to remove file {}: {}", file_str, e))
            })?;
        } else if file_path.is_dir() {
            match fs::remove_dir(&file_path) {
                Ok(_) => {}
                Err(e) if e.raw_os_error() == Some(145) || e.raw_os_error() == Some(39) => {
                    continue;
                }
                Err(e) => {
                    return Err(UninstallBepInExError::Unknown(format!(
                        "Failed to remove directory {}: {}",
                        file_str, e
                    )))
                }
            }
        }
    }

    clear_manifest(&app_handle, "BepInEx").map_err(|e| UninstallBepInExError::Unknown(e))?;

    cleanup_empty_dirs(&game_path, &files_to_remove);

    Ok(())
}

// BDX PLUGIN
#[derive(Serialize, thiserror::Error, Debug)]
pub enum InstallPluginError {
    #[error("Game path is not set")]
    GamePathNotSet,
    #[error("BepInEx is not installed")]
    BepInExNotInstalled,
    #[error("Already installed")]
    PluginAlreadyInstalled,
    #[error("Download failed: {0}")]
    DownloadFailed(String),
    #[error("Extraction failed: {0}")]
    ExtractionFailed(String),
    #[error("Archive not found: {0}")]
    ArchiveNotFound(String),
    #[error("Invalid plugin archive: {0}")]
    InvalidPluginArchive(String),
    #[error("Unknown error: {0}")]
    Unknown(String),
}

pub async fn install_browndustx_plugin_from_archive(
    app_handle: &tauri::AppHandle,
    game_path: &PathBuf,
    path: PathBuf,
) -> Result<(), InstallPluginError> {
    if !check_bepinex_installed(&game_path) {
        return Err(InstallPluginError::BepInExNotInstalled);
    }

    if check_bdx_plugin_installed(&game_path) {
        return Err(InstallPluginError::PluginAlreadyInstalled);
    }

    if !path.exists() || !path.is_file() {
        return Err(InstallPluginError::ArchiveNotFound(
            path.to_string_lossy().to_string(),
        ));
    }

    let game_path_clone = game_path.clone();
    let extracted_files = tokio::task::spawn_blocking(move || {
        let file = fs::File::open(&path)
            .map_err(|e| InstallPluginError::ArchiveNotFound(e.to_string()))?;
        let mut archive = zip::ZipArchive::new(file)
            .map_err(|_| InstallPluginError::InvalidPluginArchive("Failed to open zip".into()))?;
        if !is_bdx_archive(&mut archive) {
            return Err(InstallPluginError::InvalidPluginArchive(
                "Archive does not contain required BrownDustX files".into(),
            ));
        }
        extract_zip(&mut archive, game_path_clone)
            .map_err(|e| InstallPluginError::ExtractionFailed(e.to_string()))
    })
    .await
    .map_err(|e| InstallPluginError::ExtractionFailed(e.to_string()))??;

    let version =
        get_dll_version(&game_path.join("BepInEx/plugins/BrownDustX/lynesth.bd2.browndustx.dll"))
            .unwrap_or_else(|| "unknown".into());

    write_manifest(&app_handle, "BrownDustX", &version, extracted_files)
        .map_err(|e| InstallPluginError::Unknown(e))
}

#[derive(Serialize, thiserror::Error, Debug)]
pub enum UninstallPluginError {
    #[error("Game path is not set")]
    GamePathNotSet,
    #[error("BrownDustX is not installed")]
    PluginNotInstalled,
    #[error("Manifest not found")]
    ManifestNotFound,
    #[error("Unknown error: {0}")]
    Unknown(String),
}

pub async fn uninstall_browndustx_plugin(
    app_handle: &tauri::AppHandle,
    game_path: &PathBuf,
) -> Result<(), UninstallPluginError> {
    if !check_bdx_plugin_installed(&game_path) {
        return Err(UninstallPluginError::PluginNotInstalled);
    }

    migrate_old_manifest(
        &app_handle,
        game_path.join("BepInEx/plugins/BrownDustX/.bd2mm_bdx_manifest.json"),
        "BrownDustX",
    )
    .map_err(|e| UninstallPluginError::Unknown(e))?;

    let installed_files = read_manifest_files(&app_handle, "BrownDustX")
        .map_err(|e| UninstallPluginError::Unknown(e))?;

    if installed_files.is_empty() {
        return Err(UninstallPluginError::ManifestNotFound);
    }

    let mut files_to_remove: Vec<String> = installed_files
        .iter()
        .map(|v| v.clone())
        .filter(|f| {
            let f = f.trim_end_matches('/');
            f != "BepInEx"
                && f != "BepInEx/plugins"
                && !f.starts_with("BepInEx/plugins/BrownDustX/mods")
        })
        .collect();

    files_to_remove.reverse();

    for file_str in &files_to_remove {
        let file_path = game_path.join(file_str);

        if !file_path.exists() {
            continue;
        }

        if file_path.is_file() {
            fs::remove_file(&file_path).map_err(|e| {
                UninstallPluginError::Unknown(format!("Failed to remove file {}: {}", file_str, e))
            })?;
        } else if file_path.is_dir() {
            match fs::remove_dir(&file_path) {
                Ok(_) => {}
                Err(e) if e.raw_os_error() == Some(145) || e.raw_os_error() == Some(39) => {
                    continue;
                }
                Err(e) => {
                    return Err(UninstallPluginError::Unknown(format!(
                        "Failed to remove directory {}: {}",
                        file_str, e
                    )))
                }
            }
        }
    }

    clear_manifest(&app_handle, "BrownDustX").map_err(|e| UninstallPluginError::Unknown(e))?;

    cleanup_empty_dirs(&game_path, &files_to_remove);

    Ok(())
}

// config manager
pub async fn install_configmanager_plugin_from_archive(
    app_handle: &tauri::AppHandle,
    game_path: &PathBuf,
    path: PathBuf,
) -> Result<(), InstallPluginError> {
    if !check_bepinex_installed(&game_path) {
        return Err(InstallPluginError::BepInExNotInstalled);
    }

    if game_path
        .join("BepInEx/plugins/ConfigurationManager/ConfigurationManager.dll")
        .exists()
    {
        return Err(InstallPluginError::PluginAlreadyInstalled);
    }

    if !path.exists() || !path.is_file() {
        return Err(InstallPluginError::ArchiveNotFound(
            path.to_string_lossy().to_string(),
        ));
    }

    let game_path_clone = game_path.clone();
    let extracted_files = tokio::task::spawn_blocking(move || {
        let file = fs::File::open(&path)
            .map_err(|e| InstallPluginError::ArchiveNotFound(e.to_string()))?;
        let mut archive = zip::ZipArchive::new(file)
            .map_err(|_| InstallPluginError::InvalidPluginArchive("Failed to open zip".into()))?;
        if !is_configmanager_archive(&mut archive) {
            return Err(InstallPluginError::InvalidPluginArchive(
                "Archive does not contain required ConfigurationManager files".into(),
            ));
        }
        extract_zip(&mut archive, game_path_clone)
            .map_err(|e| InstallPluginError::ExtractionFailed(e.to_string()))
    })
    .await
    .map_err(|e| InstallPluginError::ExtractionFailed(e.to_string()))??;

    let version = get_dll_version(
        &game_path.join("BepInEx/plugins/ConfigurationManager/ConfigurationManager.dll"),
    )
    .unwrap_or_else(|| "unknown".into());

    write_manifest(
        &app_handle,
        "ConfigurationManager",
        &version,
        extracted_files,
    )
    .map_err(|e| InstallPluginError::Unknown(e))
}

pub async fn install_configmanager_plugin_from_url(
    app_handle: &tauri::AppHandle,
    game_path: &PathBuf,
    url: String,
) -> Result<(), InstallPluginError> {
    if !check_bepinex_installed(&game_path) {
        return Err(InstallPluginError::BepInExNotInstalled);
    }

    if game_path
        .join("BepInEx/plugins/ConfigurationManager/ConfigurationManager.dll")
        .exists()
    {
        return Err(InstallPluginError::PluginAlreadyInstalled);
    }

    let response = reqwest::get(&url)
        .await
        .map_err(|e| InstallPluginError::DownloadFailed(e.to_string()))?;

    if !response.status().is_success() {
        return Err(InstallPluginError::DownloadFailed(format!(
            "HTTP {}",
            response.status()
        )));
    }

    let bytes = response
        .bytes()
        .await
        .map_err(|e| InstallPluginError::DownloadFailed(e.to_string()))?
        .to_vec();

    let game_path_clone = game_path.clone();
    let extracted_files = tokio::task::spawn_blocking(move || {
        let cursor = std::io::Cursor::new(bytes);
        let mut archive = zip::ZipArchive::new(cursor)
            .map_err(|_| InstallPluginError::InvalidPluginArchive("Failed to open zip".into()))?;
        if !is_configmanager_archive(&mut archive) {
            return Err(InstallPluginError::InvalidPluginArchive(
                "Archive does not contain required ConfigurationManager files".into(),
            ));
        }
        extract_zip(&mut archive, game_path_clone)
            .map_err(|e| InstallPluginError::ExtractionFailed(e.to_string()))
    })
    .await
    .map_err(|e| InstallPluginError::ExtractionFailed(e.to_string()))??;

    let version = get_dll_version(
        &game_path.join("BepInEx/plugins/ConfigurationManager/ConfigurationManager.dll"),
    )
    .unwrap_or_else(|| "unknown".into());

    write_manifest(
        &app_handle,
        "ConfigurationManager",
        &version,
        extracted_files,
    )
    .map_err(|e| InstallPluginError::Unknown(e))
}

pub async fn uninstall_configmanager_plugin(
    app_handle: &tauri::AppHandle,
    game_path: &PathBuf,
) -> Result<(), UninstallPluginError> {
    if !game_path
        .join("BepInEx/plugins/ConfigurationManager/ConfigurationManager.dll")
        .exists()
    {
        return Err(UninstallPluginError::PluginNotInstalled);
    }

    migrate_old_manifest(
        &app_handle,
        game_path.join("BepInEx/plugins/ConfigurationManager/.bd2mm_configmanager_manifest.json"),
        "ConfigurationManager",
    )
    .map_err(|e| UninstallPluginError::Unknown(e))?;

    let installed_files = read_manifest_files(&app_handle, "ConfigurationManager")
        .map_err(|e| UninstallPluginError::Unknown(e))?;

    if installed_files.is_empty() {
        return Err(UninstallPluginError::ManifestNotFound);
    }

    let mut files_to_remove: Vec<String> = installed_files
        .iter()
        .map(|v| v.clone())
        .filter(|f| {
            let f = f.trim_end_matches('/');
            f != "BepInEx" && f != "BepInEx/plugins"
        })
        .collect();

    files_to_remove.reverse();

    for file_str in &files_to_remove {
        let file_path = game_path.join(file_str);

        if !file_path.exists() {
            continue;
        }

        if file_path.is_file() {
            fs::remove_file(&file_path).map_err(|e| {
                UninstallPluginError::Unknown(format!("Failed to remove file {}: {}", file_str, e))
            })?;
        } else if file_path.is_dir() {
            match fs::remove_dir(&file_path) {
                Ok(_) => {}
                Err(e) if e.raw_os_error() == Some(145) || e.raw_os_error() == Some(39) => {
                    continue;
                }
                Err(e) => {
                    return Err(UninstallPluginError::Unknown(format!(
                        "Failed to remove directory {}: {}",
                        file_str, e
                    )))
                }
            }
        }
    }

    clear_manifest(&app_handle, "ConfigurationManager")
        .map_err(|e| UninstallPluginError::Unknown(e))?;
    Ok(())
}
