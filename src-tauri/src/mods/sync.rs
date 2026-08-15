use std::{
    fs,
    io::{self, Write},
    path::PathBuf,
};

use chrono::Utc;
use log::{debug, warn, error};
use serde::{Deserialize, Serialize};
use tauri::Emitter;
use tempfile::NamedTempFile;

use crate::{
    mods::BD2Mod,
    utils::{
        files::{ensure_dir_exists, sync_dirs},
        misc::{can_create_symlink},
    },
};

#[derive(Serialize, Deserialize, PartialEq, Debug)]
pub enum SyncMethod {
    Copy,
    Hardlink,
    Symlink,
}

#[derive(Serialize, Deserialize, PartialEq, Debug)]
pub struct SyncManifest {
    pub method: SyncMethod,
    // pub synced_mods: HashMap<String, SyncedMod>, // mod name, disabled for now
    pub synced_mods: Vec<String>, // mod name
    pub synced_at: chrono::DateTime<chrono::Utc>,
}

#[derive(Serialize, Deserialize, PartialEq, Debug)]
pub struct SyncedMod {
    pub mod_path: PathBuf,      // staging path
    pub game_mod_path: PathBuf, // game mod path
}

// events
#[derive(Serialize, Clone)]
struct SyncStartEvent {
    r#type: SyncType,
}

#[derive(Serialize, Clone)]
#[serde(rename_all = "camelCase")]
struct SyncProgressEvent {
    r#type: SyncType,
    status: SyncStatus,
    mod_name: String,
    current: usize,
    total: usize,
    error: Option<Arc<ModSyncError>>,
}

#[derive(Serialize, Clone)]
struct SyncEndEvent {
    r#type: SyncType,
    success: bool,
    synced: usize,
    total: usize,
    error: Option<Arc<ModSyncError>>,
}

#[derive(thiserror::Error, Debug)]
pub enum ModSyncError {
    #[error("Symlink requires admin privileges")]
    SymlinkAdminRequired,

    #[error("the path '{path}' was not found")]
    PathNotFound { path: String },

    #[error("failed to copy mod '{mod_name}': {source}")]
    CopyFailed {
        mod_name: String,
        #[source]
        source: std::io::Error,
    },

    #[error("failed to create symlink for mod '{mod_name}': {source}")]
    SymlinkFailed {
        mod_name: String,
        #[source]
        source: std::io::Error,
    },

    #[error("failed to create hardlink for mod '{mod_name}': {source}")]
    HardlinkFailed {
        mod_name: String,
        #[source]
        source: std::io::Error,
    },

    #[error("failed to remove '{path}': {source}")]
    RemovalFailed {
        path: String,
        #[source]
        source: std::io::Error,
    },

    #[error("failed to create directory: {source}")]
    DirectoryCreationFailed {
        #[source]
        source: std::io::Error,
    },

    #[error("Game mods directory not found")]
    GameModsDirectoryNotFound,

    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),
}

impl serde::Serialize for ModSyncError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        use serde::ser::SerializeStruct;
        use serde_json::json;

        let (type_, details): (&str, Option<serde_json::Value>) = match self {
            ModSyncError::SymlinkAdminRequired => ("SymlinkAdminRequired", None),
            ModSyncError::PathNotFound { path } => (
                "PathNotFound",
                Some(json!({ "path": path })),
            ),
            ModSyncError::CopyFailed { mod_name, source } => (
                "CopyFailed",
                Some(json!({ "mod_name": mod_name, "kind": format!("{:?}", source.kind()) })),
            ),
            ModSyncError::SymlinkFailed { mod_name, source } => (
                "SymlinkFailed",
                Some(json!({ "mod_name": mod_name, "kind": format!("{:?}", source.kind()) })),
            ),
            ModSyncError::HardlinkFailed { mod_name, source } => (
                "HardlinkFailed",
                Some(json!({ "mod_name": mod_name, "kind": format!("{:?}", source.kind()) })),
            ),
            ModSyncError::RemovalFailed { path, source } => (
                "RemovalFailed",
                Some(json!({ "path": path, "kind": format!("{:?}", source.kind()) })),
            ),
            ModSyncError::DirectoryCreationFailed { source } => (
                "DirectoryCreationFailed",
                Some(json!({ "kind": format!("{:?}", source.kind()) })),
            ),
            ModSyncError::GameModsDirectoryNotFound => ("GameModsDirectoryNotFound", None),
            ModSyncError::Io(source) => (
                "Io",
                Some(json!({ "kind": format!("{:?}", source.kind()) })),
            ),
        };

        let mut s = serializer.serialize_struct("ModSyncError", 3)?;
        s.serialize_field("type", type_)?;
        s.serialize_field("details", &details)?;
        s.serialize_field("message", &self.to_string())?;
        s.end()
    }
}

#[derive(Serialize, Deserialize, Clone)]
enum SyncStatus {
    Synced,
    Removed,
    UpToDate, // no need to do anything
    Failed,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
enum SyncType {
    Sync,
    Unsync,
}

fn remove_mod_path(path: &PathBuf) -> io::Result<()> {
    // symlnik is not removed by remove_dir_all
    if path.is_symlink() {
        fs::remove_dir(path).or_else(|_| fs::remove_file(path))
    } else {
        fs::remove_dir_all(path).or_else(|_| fs::remove_file(path))
    }
}

pub fn load_manifest(path: &PathBuf) -> Option<SyncManifest> {
    let content = fs::read_to_string(path).ok()?;
    serde_json::from_str(&content).ok()
}

pub fn save_manifest(path: &PathBuf, manifest: SyncManifest) -> Result<(), io::Error> {
    let temp_file = NamedTempFile::new_in(path.parent().unwrap())?;
    let content = serde_json::to_string_pretty(&manifest)?;
    temp_file.as_file().write_all(content.as_bytes())?;
    temp_file.persist(path)?;
    Ok(())
}

pub fn sync_mods(
    app_handle: &tauri::AppHandle,
    game_directory: &PathBuf,
    mods: Vec<&BD2Mod>,
    method: SyncMethod,
) -> Result<(), ModSyncError> {
    app_handle
        .emit(
            "sync-start",
            SyncStartEvent {
                r#type: SyncType::Sync,
            },
        )
        .ok();

    // TODO: calculate the size that will be required to transfer, check if has space available
    // if is disk full or permission denied => sync end

    let manifest_path = game_directory.join(".bd2mm.json");
    let game_mods_path = game_directory.join("BepInEx/plugins/BrownDustX/mods/BD2MM");

    if let Err(error) = ensure_dir_exists(&game_mods_path) {
        app_handle
            .emit(
                "sync-end",
                SyncEndEvent {
                    r#type: SyncType::Sync,
                    success: false,
                    error: Some(Arc::new(ModSyncError::GameModsDirectoryNotFound)),
                    synced: 0,
                    total: 0,
                },
            )
            .ok();

        error!("Failed to create game mods directory: {:?}, error: {:?}", game_mods_path, error);

        return Err(ModSyncError::GameModsDirectoryNotFound);
    }

    if method == SyncMethod::Symlink {
        if !can_create_symlink() {
            debug!("Needs to be running as admin to use symlinks.");

            app_handle
                .emit(
                    "sync-end",
                    SyncEndEvent {
                        r#type: SyncType::Sync,
                        success: false,
                        error: Some(Arc::new(ModSyncError::SymlinkAdminRequired)),
                        total: 0,
                        synced: 0,
                    },
                )
                .ok();
            return Err(ModSyncError::SymlinkAdminRequired);
        }
    }

    let mut mods_to_remove = Vec::new();

    if let Some(previous_manifest) = load_manifest(&manifest_path) {
        // if method changed, then clean all synced
        if previous_manifest.method != method {
            debug!("sync method changed, removing all synced mods.");
            for entry in game_mods_path
                .read_dir()
                .unwrap_or_else(|_| fs::read_dir(".").unwrap())
            {
                if let Ok(entry) = entry {
                    let path = entry.path();
                    if path.symlink_metadata().is_err() {
                        debug!("no metadata, skipping.");
                        continue;
                    }
                    mods_to_remove.push(path);
                }
            }
        } else {
            // Remove mods that are in game mod folder but are no longer in the staging dir
            // the path is the parent of .modfile
            let current_mod_names: Vec<String> = mods.iter().map(|m| m.name.clone()).collect();

            debug!("current mod names in staging: {:?}", current_mod_names);

            let mut installed_mods: Vec<PathBuf> = Vec::new();

            for entry in walkdir::WalkDir::new(&game_mods_path)
                .follow_links(true)
                .min_depth(2)
            {
                match entry {
                    Ok(e) => {
                        let path = e.path();
                        if path
                            .extension()
                            .and_then(|ext| ext.to_str())
                            .map(|ext| ext == "modfile")
                            .unwrap_or(false)
                        {
                            if let Some(parent) = path.parent() {
                                if !installed_mods.contains(&parent.to_path_buf()) {
                                    installed_mods.push(parent.to_path_buf());
                                }
                            }
                        }
                    }
                    Err(e) => {
                        // broken symlink
                        // no .modfile to find
                        if let Some(path) = e.path() {
                            warn!("broken symlink detected: {:?}", path);
                            if !installed_mods.contains(&path.to_path_buf()) {
                                installed_mods.push(path.to_path_buf());
                            }
                        }
                    }
                }
            }

            debug!("installed mods in game folder: {:?}", installed_mods);

            mods_to_remove.extend(installed_mods.into_iter().filter(|mod_path| {
                if let Ok(relative) = mod_path.strip_prefix(&game_mods_path) {
                    // normalize separator so  / and \ paths match
                    let name = relative.to_string_lossy().replace("\\", "/");
                    // debug!("Checking if mod '{}' is in current mod names: {:?}", name, current_mod_names);
                    !current_mod_names.contains(&name)
                } else {
                    false
                }
            }));
        }
    } else {
        // No manifest  remove anything in game mods folder not in current mod list
        let current_mod_names: Vec<String> = mods.iter().map(|m| m.name.clone()).collect();

        for entry in game_mods_path
            .read_dir()
            .unwrap_or_else(|_| fs::read_dir(".").unwrap())
        {
            if let Ok(entry) = entry {
                let path = entry.path();
                if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
                    if !current_mod_names.contains(&name.to_string()) {
                        mods_to_remove.push(path);
                    }
                }
            }
        }
    }

    // skip disabled mods that are not in game folder or mods with errors that are enabled, we don't need to remove because it is never synced
    let mut index = 0;
    let mods_to_sync: Vec<_> = mods
        .clone()
        .into_iter()
        .filter(|_mod| {
            let dst_path = game_mods_path.join(&_mod.name);

            if !dst_path.exists() && !_mod.enabled || !_mod.errors.is_empty() && _mod.enabled {
                false
            } else {
                true
            }
        })
        .collect();
    let total_mods_count = mods_to_sync.len() + mods_to_remove.len();

    debug!(
        "Total mods to sync: {}, total mods to remove: {}",
        total_mods_count - mods_to_remove.len(),
        mods_to_remove.len()
    );

    #[cfg(debug_assertions)]
    {
        println!("Mods to sync:");
        for _mod in &mods_to_sync {
            println!(
                "+ {} (enabled: {}, errors: {:?})",
                _mod.name, _mod.enabled, _mod.errors
            );
        }
    }

    #[cfg(debug_assertions)]
    {
        println!("Mods to remove:");
        for path in &mods_to_remove {
            println!(
                "- {}",
                path.file_name()
                    .and_then(|n| n.to_str())
                    .unwrap_or_default()
            );
        }
    }

    for path in mods_to_remove {
        debug!("Removing mod at path: {:?}", path);

        let (status, error) = match remove_mod_path(&path) {
            Ok(_) => {
                // remove parent dir if  empty
                if let Some(parent) = path.parent() {
                    if parent != game_mods_path {
                        let _ = fs::remove_dir(parent);
                    }
                }
                (SyncStatus::Removed, None)
            }
            Err(source) => (
                SyncStatus::Failed,
                Some(ModSyncError::RemovalFailed {
                    path: path.to_string_lossy().to_string(),
                    source,
                }),
            ),
        };

        index += 1;
        app_handle
            .emit(
                "sync-progress",
                SyncProgressEvent {
                    r#type: SyncType::Sync,
                    mod_name: path
                        .file_name()
                        .and_then(|f| f.to_str().map(|s| s.to_string()))
                        .unwrap_or_default(),
                    current: index,
                    total: total_mods_count,
                    status,
                    error: error.map(Arc::new),
                },
            )
            .ok();
    }

    // let mut synced_mods: HashMap<String, SyncedMod> = HashMap::new();
    let mut synced_mods: Vec<String> = Vec::new();
    for _mod in mods {
        // if mod has errors and is enabled, skip syncing
        if !_mod.errors.is_empty() && _mod.enabled {
            warn!(
                "mod {:?} has errors, skipping sync. Errors: {:?}",
                _mod.name, _mod.errors
            );
            continue;
        }

        let dst_path = game_mods_path.join(&_mod.name);

        if !_mod.path.exists() {
            warn!("mod {:?} does not exist in staging.", _mod.name);

            // if it was previously synced, remove it from game folder
            let (status, error) = if dst_path.exists() || dst_path.is_symlink() {
                match remove_mod_path(&dst_path) {
                    Ok(_) => {
                        // remove parent dir if now empty
                        if let Some(parent) = dst_path.parent() {
                            if parent != game_mods_path {
                                let _ = fs::remove_dir(parent);
                            }
                        }
                        (
                            SyncStatus::Removed,
                            Some(Arc::new(ModSyncError::PathNotFound {
                                path: _mod.path.to_string_lossy().to_string(),
                            })),
                        )
                    }
                    Err(source) => (
                        SyncStatus::Failed,
                        Some(Arc::new(ModSyncError::RemovalFailed {
                            path: dst_path.to_string_lossy().to_string(),
                            source,
                        })),
                    ),
                }
            } else {
                // was not in game folder, just report missing
                (
                    SyncStatus::Failed,
                    Some(Arc::new(ModSyncError::PathNotFound {
                        path: _mod.path.to_string_lossy().to_string(),
                    })),
                )
            };

            index = index + 1;
            app_handle
                .emit(
                    "sync-progress",
                    SyncProgressEvent {
                        r#type: SyncType::Sync,
                        current: index,
                        mod_name: _mod.name.clone(),
                        total: total_mods_count,
                        status,
                        error,
                    },
                )
                .ok();
            continue;
        }

        if !_mod.enabled {
            if dst_path.exists() || dst_path.is_symlink() {
                debug!(
                    "mod {:?} is disabled but exists in game folder, removing.",
                    _mod.name
                );
                if let Err(source) = remove_mod_path(&dst_path) {
                    error!("Failed to remove mod {:?} at path {:?}: {}", _mod.name, dst_path, source);
                    index = index + 1;
                    app_handle
                        .emit(
                            "sync-progress",
                            SyncProgressEvent {
                                r#type: SyncType::Sync,
                                current: index,
                                mod_name: _mod.name.clone(),
                                total: total_mods_count,
                                status: SyncStatus::Failed,
                                error: Some(Arc::new(ModSyncError::RemovalFailed {
                                    path: dst_path.to_string_lossy().to_string(),
                                    source,
                                })),
                            },
                        )
                        .ok();
                    continue;
                }

                // get parents until BD2MM/, check if any of them has other content, if not remove, this is to remove empty dirs left by mods in subdirs
                debug!("Checking for empty parent directories to remove for mod: {}", _mod.name);
                
                for parent in dst_path.ancestors().skip(1).take_while(|p| *p != game_mods_path) {
                    let is_empty = parent.read_dir().map(|mut i| i.next().is_none()).unwrap_or(false);
                    if is_empty {
                        debug!("Removing empty parent directory: {:?}", parent);
                        if let Err(e) = fs::remove_dir(parent) {
                            error!("Failed to remove empty parent directory {:?}: {}", parent, e);
                        }
                    } else {
                        break;
                    }
                }

                index = index + 1;

                app_handle
                    .emit(
                        "sync-progress",
                        SyncProgressEvent {
                            r#type: SyncType::Sync,
                            current: index,
                            mod_name: _mod.name.clone(),
                            total: total_mods_count,
                            status: SyncStatus::Removed,
                            error: None,
                        },
                    )
                    .ok();
            }

            continue;
        }

        let mut was_updated = false;
        let mut sync_error: Option<ModSyncError> = None;

        match method {
            SyncMethod::Copy => match sync_dirs(&_mod.path, &dst_path) {
                Ok(updated) => {
                    if updated {
                        was_updated = true;
                    }
                }
                Err(source) => {
                    sync_error = Some(ModSyncError::CopyFailed {
                        mod_name: _mod.name.clone(),
                        source,
                    });
                }
            },
            SyncMethod::Symlink => {
                let needs_update = if dst_path.is_symlink() {
                    dst_path.read_link().ok() != Some(_mod.path.clone())
                } else if dst_path.exists() {
                    true
                } else {
                    true
                };

                if needs_update {
                    // Remove existing if it's not a symlink pointing to the right place
                    if dst_path.exists() || dst_path.is_symlink() {
                        if let Err(source) = remove_mod_path(&dst_path) {
                            sync_error = Some(ModSyncError::RemovalFailed {
                                path: dst_path.to_string_lossy().to_string(),
                                source,
                            });
                        }
                    }

                    // Create parent dirs
                    if sync_error.is_none() {
                        if let Some(parent) = dst_path.parent() {
                            if let Err(source) = fs::create_dir_all(parent) {
                                sync_error = Some(ModSyncError::DirectoryCreationFailed { source });
                            }
                        }
                    }

                    if sync_error.is_none() {
                        #[cfg(target_family = "unix")]
                        {
                            use std::os::unix::fs::symlink;
                            if let Err(source) = symlink(&_mod.path, &dst_path) {
                                sync_error = Some(ModSyncError::SymlinkFailed {
                                    mod_name: _mod.name.clone(),
                                    source,
                                });
                            } else {
                                was_updated = true;
                            }
                        }
                        #[cfg(target_family = "windows")]
                        {
                            use std::os::windows::fs::symlink_dir;
                            if let Err(source) = symlink_dir(&_mod.path, &dst_path) {
                                sync_error = Some(ModSyncError::SymlinkFailed {
                                    mod_name: _mod.name.clone(),
                                    source,
                                });
                            } else {
                                was_updated = true;
                            }
                        }
                    }
                }
            }
            SyncMethod::Hardlink => {
                if dst_path.exists() {
                    if let Err(source) = fs::remove_dir_all(&dst_path) {
                        sync_error = Some(ModSyncError::RemovalFailed {
                            path: dst_path.to_string_lossy().to_string(),
                            source,
                        });
                    }
                }

                if sync_error.is_none() {
                    if let Err(source) = ensure_dir_exists(&dst_path) {
                        sync_error = Some(ModSyncError::DirectoryCreationFailed { source });
                    } else {
                        for entry in walkdir::WalkDir::new(&_mod.path) {
                            let entry = match entry {
                                Ok(e) => e,
                                Err(e) => {
                                    sync_error = Some(ModSyncError::HardlinkFailed {
                                        mod_name: _mod.name.clone(),
                                        source: e.into(),
                                    });
                                    break;
                                }
                            };
                            let relative = entry.path().strip_prefix(&_mod.path).unwrap();
                            let target = dst_path.join(relative);

                            if entry.file_type().is_dir() {
                                if let Err(source) = fs::create_dir_all(&target) {
                                    sync_error = Some(ModSyncError::DirectoryCreationFailed { source });
                                    break;
                                }
                            } else {
                                if let Err(source) = fs::hard_link(entry.path(), &target) {
                                    sync_error = Some(ModSyncError::HardlinkFailed {
                                        mod_name: _mod.name.clone(),
                                        source,
                                    });
                                    break;
                                }
                            }
                        }

                        if sync_error.is_none() {
                            was_updated = true;
                        }
                    }
                }
            }
        }

        index = index + 1;

        let (status, error) = match sync_error {
            Some(err) => (SyncStatus::Failed, Some(err)),
            None if was_updated => (SyncStatus::Synced, None),
            None => (SyncStatus::UpToDate, None),
        };

        let no_error = error.is_none();

        app_handle
            .emit(
                "sync-progress",
                SyncProgressEvent {
                    r#type: SyncType::Sync,
                    current: index,
                    mod_name: _mod.name.clone(),
                    total: total_mods_count,
                    status,
                    error: error.map(Arc::new),
                },
            )
            .ok();

        // Only add to synced_mods if there was no error
        // mod that was disabled and removed, should we add to sync error?
        if no_error {
            synced_mods.push(_mod.name.clone());
        }
    }

    // if cancel sync, remove synced mods?
    debug!(
        "{:?} mods was synced to game folder.",
        synced_mods.iter().count()
    );

    let manifest = SyncManifest {
        method,
        synced_at: Utc::now(),
        synced_mods,
    };

    save_manifest(&manifest_path, manifest).ok();

    app_handle
        .emit(
            "sync-end",
            SyncEndEvent {
                r#type: SyncType::Sync,
                success: true,
                synced: index,
                total: total_mods_count,
                error: None,
            },
        )
        .ok();

    Ok(())
}
pub fn unsync_mods(
    app_handle: &tauri::AppHandle,
    game_directory: &PathBuf,
) -> Result<(), ModSyncError> {
    let manifest_path = game_directory.join(".bd2mm.json");
    let game_mods_path = game_directory.join("BepInEx/plugins/BrownDustX/mods/BD2MM");

    app_handle
        .emit(
            "sync-start",
            SyncStartEvent {
                r#type: SyncType::Unsync,
            },
        )
        .ok();

    let mut index = 0;
    let total_mods: usize = game_mods_path
        .read_dir()
        .unwrap_or_else(|_| fs::read_dir(".").unwrap())
        .count();

    for entry in game_mods_path
        .read_dir()
        .unwrap_or_else(|_| fs::read_dir(".").unwrap())
    {
        if let Ok(entry) = entry {
            let path = entry.path();
            debug!("Removing mod at path: {:?}", path);

            let result = remove_mod_path(&path);

            let (status, error) = match result {
                Ok(_) => (SyncStatus::Removed, None),
                Err(source) => (
                    SyncStatus::Failed,
                    Some(ModSyncError::RemovalFailed {
                        path: path.to_string_lossy().to_string(),
                        source,
                    }),
                ),
            };

            index += 1;
            app_handle
                .emit(
                    "sync-progress",
                    SyncProgressEvent {
                        r#type: SyncType::Unsync,
                        mod_name: path
                            .file_name()
                            .and_then(|f| f.to_str().map(|s| s.to_string()))
                            .unwrap_or_default(),
                        current: index,
                        total: total_mods,
                        status,
                        error: error.map(Arc::new),
                    },
                )
                .ok();
        }
    }

    let _ = fs::remove_file(&manifest_path);

    app_handle
        .emit(
            "sync-end",
            SyncEndEvent {
                r#type: SyncType::Unsync,
                success: true,
                synced: index,
                total: total_mods,
                error: None,
            },
        )
        .ok();

    Ok(())
}

pub fn is_sync_needed(game_directory: &PathBuf, staging_mods: &[&BD2Mod]) -> bool {
    // simple check, todo: improve this by checking content too like sync do
    let manifest_path = game_directory.join(".bd2mm.json");
    let game_mods_path = game_directory.join("BepInEx/plugins/BrownDustX/mods/BD2MM");

    if !game_mods_path.exists() {
        debug!("Game mods path does not exist, sync is needed.");
        return true;
    }

    let manifest = match load_manifest(&manifest_path) {
        Some(m) => m,
        None => {
            debug!("Manifest cannot be loaded, sync is needed.");
            return true;
        }
    };

    let manifest_mods_set: std::collections::HashSet<&str> =
        manifest.synced_mods.iter().map(|s| s.as_str()).collect();

    let expected_mods_set: std::collections::HashSet<&str> = staging_mods
        .iter()
        .filter(|m| m.enabled && m.errors.is_empty())
        .map(|m| m.name.as_str())
        .collect();

    if manifest_mods_set != expected_mods_set {
        debug!(
            "Manifest mods and expected mods differ, sync is needed. Manifest: {:?}, Expected: {:?}",
            manifest_mods_set, expected_mods_set
        );
        return true;
    }

    for mod_name in &expected_mods_set {
        let dst_path = game_mods_path.join(mod_name);
        if !dst_path.exists() {
            debug!(
                "Mod {:?} missing from game folder, sync is needed.",
                mod_name
            );
            return true;
        }
    }
    let installed_mods: std::collections::HashSet<String> = {
        let mut set = std::collections::HashSet::new();
        for entry in walkdir::WalkDir::new(&game_mods_path).follow_links(true) {
            match entry {
                Ok(e) => {
                    if e.path()
                        .extension()
                        .and_then(|ext| ext.to_str())
                        .map(|ext| ext == "modfile")
                        .unwrap_or(false)
                    {
                        if let Some(parent) = e.path().parent() {
                            if let Ok(rel) = parent.strip_prefix(&game_mods_path) {
                                set.insert(rel.to_string_lossy().replace("\\", "/"));
                            }
                        }
                    }
                }
                Err(e) => {
                    // broken symlink is installed
                    if let Some(path) = e.path() {
                        if let Ok(rel) = path.strip_prefix(&game_mods_path) {
                            set.insert(rel.to_string_lossy().replace("\\", "/"));
                        }
                    }
                }
            }
        }
        set
    };

    for installed in &installed_mods {
        if !expected_mods_set.contains(installed.as_str()) {
            debug!(
                "Extra mod {:?} found in game folder, sync is needed.",
                installed
            );
            return true;
        }
    }

    false
}
