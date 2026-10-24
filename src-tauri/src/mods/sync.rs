use std::{
    collections::{HashMap, HashSet},
    fs,
    io::{self, Write},
    path::{Path, PathBuf},
    sync::Arc,
    time::Instant,
};

use log::{debug, error, info, warn};
use serde::{Deserialize, Serialize};
use std::os::windows::fs::MetadataExt;
use tauri::{AppHandle, Emitter};
use tempfile::NamedTempFile;
use walkdir::WalkDir;

use crate::{
    mods::{BD2Mod, types::BD2ModError, utils::game_folder_name}, utils::{
        files::{dirs_match, ensure_dir_exists, get_directory_size},
        misc::can_create_symlink,
    },
};

use crate::utils::files::{get_available_size, sync_dirs};

#[derive(Serialize, Deserialize, PartialEq, Debug, Clone, Copy)]
pub enum SyncMethod {
    Copy,
    // Hardlink,
    Symlink,
}

#[derive(Serialize, Deserialize, PartialEq, Debug, Clone)]
pub struct SyncManifest {
    pub method: SyncMethod,
    pub synced_mods: Vec<SyncedMod>,
    pub synced_at: chrono::DateTime<chrono::Utc>,
}

#[derive(Serialize, Deserialize, PartialEq, Debug, Clone)]
pub struct SyncedMod {
    pub mod_name: String,
    pub game_folder: String,
    pub method: SyncMethod,
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
pub struct SyncResult {
    success: bool,
    synced: usize,
    total: usize,
    skipped_unmanaged: usize,
}

#[derive(Serialize, Clone)]
struct SyncEndEvent<'a> {
    r#type: SyncType,
    success: bool,
    synced: usize,
    total: usize,
    error: Option<&'a ModSyncError>,
}

#[derive(thiserror::Error, Debug)]
pub enum ModSyncError {
    #[error("The sync manifest is corrupt: {reason}")]
    ManifestCorrupt { reason: String },

    #[error("Failed to save the sync manifest: {source}")]
    ManifestSaveFailed {
        #[source]
        source: std::io::Error,
    },

    #[error("Failed to remove {failed} of {total} installed folders")]
    UnsyncFailed { failed: usize, total: usize },

    #[error("Symlink requires admin privileges")]
    SymlinkAdminRequired,

    #[error("Mod contains a symbolic link or junction: '{path}'")]
    ModContainsSymlink { path: String },

    #[error("Staging and game mods directories overlap")]
    DirectoriesNested,

    #[error("Destination contains a symbolic link or junction: '{path}'")]
    DestinationContainsSymlink { path: String },

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

    #[error("No available disk space for sync")]
    NoAvailableDiskSpace,

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
            ModSyncError::UnsyncFailed { failed, total } => (
                "UnsyncFailed",
                Some(json!({ "failed": failed, "total": total })),
            ),
            ModSyncError::ManifestSaveFailed { source } => (
                "ManifestSaveFailed",
                Some(json!({ "kind": format!("{:?}", source.kind()) })),
            ),
            ModSyncError::ManifestCorrupt { reason } => {
                ("ManifestCorrupt", Some(json!({ "reason": reason })))
            }
            ModSyncError::DirectoriesNested => ("DirectoriesNested", None),
            ModSyncError::DestinationContainsSymlink { path } => {
                ("DestinationContainsSymlink", Some(json!({ "path": path })))
            }
            ModSyncError::SymlinkAdminRequired => ("SymlinkAdminRequired", None),
            ModSyncError::ModContainsSymlink { path } => {
                ("ModContainsSymlink", Some(json!({ "path": path })))
            }
            ModSyncError::CopyFailed { mod_name, source } => (
                "CopyFailed",
                Some(json!({ "mod_name": mod_name, "kind": format!("{:?}", source.kind()) })),
            ),
            ModSyncError::SymlinkFailed { mod_name, source } => (
                "SymlinkFailed",
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
            ModSyncError::NoAvailableDiskSpace => ("NoAvailableDiskSpace", None),
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

pub(crate) fn remove_mod_path(path: &Path) -> io::Result<()> {
    let metadata = match fs::symlink_metadata(path) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(()),
        Err(error) => return Err(error),
    };
    if metadata.file_attributes() & 0x10 != 0 {
        if metadata.file_attributes() & 0x400 != 0 {
            fs::remove_dir(path)
        } else {
            fs::remove_dir_all(path)
        }
    } else {
        fs::remove_file(path)
    }
}

fn get_sync_directory(
    game_directory: &Path,
    staging_directory: &Path,
) -> Result<PathBuf, ModSyncError> {
    let game_mods_path = game_directory.join("BepInEx/plugins/BrownDustX/mods/BD2MM");
    for parent in game_mods_path
        .ancestors()
        .take_while(|parent| parent.starts_with(game_directory))
    {
        match fs::symlink_metadata(parent) {
            Ok(metadata) if metadata.file_attributes() & 0x400 != 0 => {
                return Err(ModSyncError::DestinationContainsSymlink {
                    path: parent.to_string_lossy().to_string(),
                });
            }
            Ok(_) => {}
            Err(error) if error.kind() == io::ErrorKind::NotFound => {}
            Err(error) => return Err(error.into()),
        }
    }
    let parent = staging_directory
        .ancestors()
        .find(|parent| parent.exists())
        .ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::NotFound,
                "Staging directory parent was not found",
            )
        })?;
    let staging = PathBuf::from(
        parent
            .canonicalize()?
            .join(staging_directory.strip_prefix(parent).unwrap())
            .to_string_lossy()
            .to_lowercase(),
    );
    let destination = PathBuf::from(
        game_directory
            .canonicalize()?
            .join("BepInEx/plugins/BrownDustX/mods")
            .to_string_lossy()
            .to_lowercase(),
    );
    if staging.starts_with(&destination) || destination.starts_with(&staging) {
        return Err(ModSyncError::DirectoriesNested);
    }
    // [TODO] add a check if we can write?
    ensure_dir_exists(&game_mods_path)
        .map_err(|source| ModSyncError::DirectoryCreationFailed { source })?;
    fs::read_dir(&game_mods_path)?;
    Ok(game_mods_path)
}

fn check_mod_parents(destination: &Path, root: &Path) -> Result<(), ModSyncError> {
    for parent in destination
        .ancestors()
        .skip(1)
        .take_while(|parent| parent.starts_with(root))
    {
        match fs::symlink_metadata(parent) {
            Ok(metadata) if metadata.file_attributes() & 0x400 != 0 => {
                return Err(ModSyncError::DestinationContainsSymlink {
                    path: parent.to_string_lossy().to_string(),
                });
            }
            Ok(_) => {}
            Err(error) if error.kind() == io::ErrorKind::NotFound => {}
            Err(error) => return Err(error.into()),
        }
    }
    Ok(())
}

pub fn load_manifest(path: &PathBuf) -> Result<Option<SyncManifest>, ModSyncError> {
    let content = match fs::read_to_string(path) {
        Ok(content) => content,
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(error.into()),
    };
    let mut content: serde_json::Value =
        serde_json::from_str(&content).map_err(|error| ModSyncError::ManifestCorrupt {
            reason: error.to_string(),
        })?;
    let method = content
        .get("method")
        .cloned()
        .unwrap_or(serde_json::Value::Null);

    // Old manifests used the staging name as the destination path.
    if let Some(mods) = content
        .get_mut("synced_mods")
        .and_then(|mods| mods.as_array_mut())
    {
        for entry in mods {
            if let Some(name) = entry.as_str() {
                *entry = serde_json::json!({ "mod_name": name, "game_folder": name });
            }
            if let Some(entry) = entry.as_object_mut() {
                entry.entry("method").or_insert_with(|| method.clone());
            }
        }
    }
    let manifest: SyncManifest =
        serde_json::from_value(content).map_err(|error| ModSyncError::ManifestCorrupt {
            reason: error.to_string(),
        })?;
    let mut names = HashSet::new();
    let mut folders = HashSet::new();
    for entry in &manifest.synced_mods {
        for path in [&entry.mod_name, &entry.game_folder] {
            if path.is_empty()
                || Path::new(path)
                    .components()
                    .any(|part| !matches!(part, std::path::Component::Normal(_)))
            {
                return Err(ModSyncError::ManifestCorrupt {
                    reason: format!("Invalid mod path: {}", path),
                });
            }
        }
        if !names.insert(entry.mod_name.replace('\\', "/").to_lowercase())
            || !folders.insert(entry.game_folder.replace('\\', "/").to_lowercase())
        {
            return Err(ModSyncError::ManifestCorrupt {
                reason: "Duplicate mod name or game folder".into(),
            });
        }
    }
    Ok(Some(manifest))
}

pub fn save_manifest(path: &PathBuf, manifest: SyncManifest) -> Result<(), io::Error> {
    let temp_file = NamedTempFile::new_in(path.parent().unwrap())?;
    let content = serde_json::to_string_pretty(&manifest)?;
    temp_file.as_file().write_all(content.as_bytes())?;
    temp_file.as_file().sync_all()?;
    temp_file.persist(path)?;
    Ok(())
}
#[derive(Serialize, Debug, Clone, Deserialize)]
pub enum SyncAction {
    Add(String),
    Remove(String),
    Replace(String),
    Nothing(String),
    #[serde(skip_deserializing)]
    Failed(Arc<ModSyncError>),
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum ModState {
    Managed,      // installed in the game and listed in the manifest
    Unmanaged, // already in the game but not listed in the manifest; left alone unless the user allows changes
    NotInstalled, // in staging, but not currently installed in the game
}
#[derive(Serialize, Debug, Clone)]
pub struct ModSyncAction {
    pub mod_name: String,
    pub game_folder: String,
    pub action: SyncAction,
    pub state: ModState,
    #[serde(skip)]
    pub size: Option<u64>, // just to calculate the total size of mods to sync, not serialized
}

pub fn get_sync_actions(
    manifest: &SyncManifest,
    game_directory: &PathBuf,
    staging_directory: &PathBuf,
    method: &SyncMethod,
    mods: Vec<&BD2Mod>,
) -> Result<Vec<ModSyncAction>, ModSyncError> {
    let started = Instant::now();
    let mut actions: Vec<ModSyncAction> = Vec::new();

    let game_mods_path = get_sync_directory(game_directory, staging_directory)?.canonicalize()?;

    let game_folders: HashMap<String, String> = mods
        .iter()
        .map(|entry| {
            (
                entry.name.clone(),
                game_folder_name(&entry.name),
            )
        })
        .collect();

    // #1 find installed mods without following links
    let mut installed = HashSet::new();

    let mut entries = WalkDir::new(&game_mods_path)
        .follow_links(false)
        .min_depth(1)
        .into_iter();

    while let Some(entry) = entries.next() {
        let (path, error) = match entry {
            Ok(entry) => {
                let path = entry.path().to_path_buf();
                if entry.file_type().is_symlink() {
                    installed.insert(path);
                    continue;
                }
                let relative = path
                    .strip_prefix(&game_mods_path)
                    .unwrap()
                    .to_string_lossy()
                    .replace('\\', "/");
                let is_mod = manifest
                    .synced_mods
                    .iter()
                    .any(|entry| entry.game_folder.eq_ignore_ascii_case(&relative));
                if is_mod {
                    installed.insert(path);
                    if entry.file_type().is_dir() {
                        entries.skip_current_dir();
                    }
                    continue;
                }
                if !entry.file_type().is_dir() {
                    continue;
                }
                let result = (|| -> io::Result<bool> {
                    for child in fs::read_dir(&path)? {
                        let child = child?;
                        if child.file_type()?.is_file()
                            && child
                                .path()
                                .extension()
                                .and_then(|ext| ext.to_str())
                                .map(|ext| ext.eq_ignore_ascii_case("modfile"))
                                .unwrap_or(false)
                        {
                            return Ok(true);
                        }
                    }
                    Ok(false)
                })();
                match result {
                    Ok(true) => {
                        installed.insert(path);
                        entries.skip_current_dir();
                        continue;
                    }
                    Ok(false) => continue,
                    Err(error) => {
                        entries.skip_current_dir();
                        (path, error)
                    }
                }
            }
            Err(error) => {
                let path = error.path().unwrap_or(&game_mods_path).to_path_buf();
                if path == game_mods_path {
                    return Err(io::Error::from(error).into());
                }
                (path, io::Error::from(error))
            }
        };
        let folder = path
            .strip_prefix(&game_mods_path)
            .unwrap()
            .to_string_lossy()
            .replace('\\', "/");

        actions.push(ModSyncAction {
            mod_name: folder.clone(),
            game_folder: folder,
            action: SyncAction::Failed(Arc::new(error.into())),
            state: ModState::Unmanaged,
            size: None,
        });
    }

    // #2 old destinations and mods no longer in staging
    for path in installed {
        let game_folder = path
            .strip_prefix(&game_mods_path)
            .unwrap()
            .to_string_lossy()
            .replace('\\', "/");

        if game_folders
            .values()
            .any(|folder| folder.eq_ignore_ascii_case(&game_folder))
        {
            continue;
        }

        // [TODO] explain this
        let saved = manifest
            .synced_mods
            .iter()
            .find(|entry| entry.game_folder.eq_ignore_ascii_case(&game_folder));

        let mod_name = saved
            .map(|entry| entry.mod_name.clone())
            .unwrap_or_else(|| game_folder.clone());

        let is_managed = saved.is_some();

        let action = match check_mod_parents(&path, &game_mods_path) {
            Ok(()) => SyncAction::Remove(if is_managed {
                "missingFromStaging".into()
            } else {
                "unmanagedNotInStaging".into()
            }),
            Err(error) => SyncAction::Failed(Arc::new(error)),
        };

        actions.push(ModSyncAction {
            mod_name,
            game_folder,
            action,
            state: if is_managed {
                ModState::Managed
            } else {
                ModState::Unmanaged
            },
            size: None,
        });
    }

    // #3 actions for mods currently in staging.
    for mod_entry in &mods {
        let game_folder = game_folders[&mod_entry.name].clone();
        let destination = game_mods_path.join(&game_folder);
        let is_managed = manifest.synced_mods.iter().any(|entry| {
            entry.mod_name == mod_entry.name
                && entry
                    .game_folder
                    .replace('\\', "/")
                    .eq_ignore_ascii_case(&game_folder)
        });

        let previous_synced_mod = manifest
            .synced_mods
            .iter()
            .find(|entry| entry.mod_name == mod_entry.name);

        let method_changed = previous_synced_mod
            .map(|entry| entry.method != *method)
            .unwrap_or(false);

        let mut state = if is_managed {
            ModState::Managed
        } else {
            ModState::Unmanaged
        };
        let result = (|| -> Result<SyncAction, ModSyncError> {
            check_mod_parents(&destination, &game_mods_path)?;
            let exists_in_game = match fs::symlink_metadata(&destination) {
                Ok(_) => true,
                Err(error) if error.kind() == io::ErrorKind::NotFound => false,
                Err(error) => return Err(error.into()),
            };

            state = if !exists_in_game {
                ModState::NotInstalled
            } else if is_managed {
                ModState::Managed
            } else {
                ModState::Unmanaged
            };

            let action = match (
                mod_entry.enabled,
                is_managed,
                exists_in_game,
                mod_entry.errors.iter().any(|error| {
                    !matches!(error, BD2ModError::UnmanagedButInStaging)
                }),
                method_changed,
            ) {
                // Disabled + exists in game
                (false, _, true, _, _) => SyncAction::Remove("disabledButInstalled".into()),

                // disabled + managed but already missing
                (false, true, false, _, _) => SyncAction::Nothing("disabledAndNotInstalled".into()),

                // disabled + unmanaged
                (false, false, false, _, _) => {
                    SyncAction::Nothing("disabledAndNotInstalled".into())
                }

                // enabled + errors + exists in game
                (true, _, true, true, _) => SyncAction::Remove("stagingErrorsButInstalled".into()),

                // enabled + errors + missing destination
                (true, _, _, true, _) => SyncAction::Nothing("stagingErrorsAndNotInstalled".into()),

                // enabled + no errors + missing destination
                (true, _, false, false, _) => SyncAction::Add(if is_managed {
                    "managedDestinationMissing".into()
                } else {
                    "notInstalled".into()
                }),
                (true, _, true, false, _) => {
                    if is_managed && method_changed {
                        return Ok(SyncAction::Replace("methodChanged".into()));
                    }

                    let (unchanged, reason) = match method {
                        SyncMethod::Copy => {
                            (dirs_match(&mod_entry.path, &destination)?, "filesDiffer")
                        }
                        SyncMethod::Symlink => {
                            if destination.is_symlink() {
                                let target = destination.read_link()?;
                                let target = if target.is_absolute() {
                                    target
                                } else {
                                    destination.parent().unwrap().join(target)
                                };
                                match target.canonicalize() {
                                    Ok(target) => (
                                        target.to_string_lossy().to_lowercase()
                                            == mod_entry
                                                .path
                                                .canonicalize()?
                                                .to_string_lossy()
                                                .to_lowercase(),
                                        "symlinkTargetChanged",
                                    ),
                                    Err(error) if error.kind() == io::ErrorKind::NotFound => {
                                        (false, "symlinkTargetMissing")
                                    }
                                    Err(error) => return Err(error.into()),
                                }
                            } else {
                                (false, "destinationNotSymlink")
                            }
                        } // SyncMethod::Hardlink => (false, "hardlinkRebuildRequired"),
                    };

                    if !is_managed {
                        SyncAction::Replace("unmanagedReinstall".into())
                    } else if unchanged {
                        SyncAction::Nothing("noChanges".into())
                    } else {
                        SyncAction::Replace(reason.into())
                    }
                }
            };

            Ok(action)
        })();

        let mut action = match result {
            Ok(action) => action,
            Err(error) => SyncAction::Failed(Arc::new(error)),
        };

        // [TODO] we change the action to failed if we can't get the size, but maybe we should just log the error and continue with the action?
        // [TODO] check the performance of this
        let size = match &action {
            SyncAction::Add(_) | SyncAction::Replace(_) => {
                if *method == SyncMethod::Symlink {
                    Some(0)
                } else {
                    match get_directory_size(&mod_entry.path) {
                        Ok(size) => Some(size),
                        Err(error) => {
                            action = SyncAction::Failed(Arc::new(error.into()));
                            None
                        }
                    }
                }
            }
            _ => None,
        };

        actions.push(ModSyncAction {
            mod_name: mod_entry.name.clone(),
            game_folder,
            action,
            state,
            size,
        });
    }

    debug!(
        "Calculated {} sync actions in {:.3} ms",
        actions.len(),
        started.elapsed().as_secs_f64() * 1000.0
    );

    Ok(actions)
}

pub fn sync_mods<R: tauri::Runtime>(
    app_handle: &AppHandle<R>,
    game_directory: &PathBuf,
    staging_directory: &PathBuf,
    mods: Vec<&BD2Mod>,
    method: SyncMethod,
    remove_unmanaged_mods: bool,
) -> Result<SyncResult, ModSyncError> {
    let sync_started = Instant::now();
    info!(
        "Starting sync (method = {:?}, remove_unmanaged_mods = {})",
        method, remove_unmanaged_mods
    );
    app_handle
        .emit(
            "sync-start",
            SyncStartEvent {
                r#type: SyncType::Sync,
            },
        )
        .ok();

    let game_mods_path = get_sync_directory(game_directory, staging_directory).map_err(|err| {
        error!("Failed to get sync directory: {:?}", err);

        app_handle
            .emit(
                "sync-end",
                SyncEndEvent {
                    r#type: SyncType::Sync,
                    success: false,
                    error: Some(&err),
                    synced: 0,
                    total: 0,
                },
            )
            .ok();
        return err;
    })?;

    if method == SyncMethod::Symlink && !can_create_symlink() {
        error!("Symlink requires admin privileges or developer mode (windows) is not enabled.");

        app_handle
            .emit(
                "sync-end",
                SyncEndEvent {
                    r#type: SyncType::Sync,
                    success: false,
                    error: Some(&ModSyncError::SymlinkAdminRequired),
                    total: 0,
                    synced: 0,
                },
            )
            .ok();

        return Err(ModSyncError::SymlinkAdminRequired);
    }

    let manifest_path = game_directory.join(".bd2mm.json");
    let mut manifest = load_manifest(&manifest_path)
        .map_err(|err| {
            error!("Failed to load manifest: {:?}", err);
            app_handle
                .emit(
                    "sync-end",
                    SyncEndEvent {
                        r#type: SyncType::Sync,
                        success: false,
                        error: Some(&err),
                        total: 0,
                        synced: 0,
                    },
                )
                .ok();
            return err;
        })?
        .unwrap_or(SyncManifest {
            method,
            synced_mods: Vec::new(),
            synced_at: chrono::Utc::now(),
        });

    let mut actions = get_sync_actions(&manifest, game_directory, staging_directory, &method, mods)
        .map_err(|err| {
            error!("Failed to get sync actions: {:?}", err);

            app_handle
                .emit(
                    "sync-end",
                    SyncEndEvent {
                        r#type: SyncType::Sync,
                        success: false,
                        error: Some(&err),
                        total: 0,
                        synced: 0,
                    },
                )
                .ok();

            return err;
        })?;

    actions.sort_by_key(|entry| match &entry.action {
        SyncAction::Failed(_) => 0,
        SyncAction::Nothing(_) => 0,
        SyncAction::Remove(_) => 1,
        SyncAction::Replace(_) => 2,
        SyncAction::Add(_) => 3,
    });

    let actions_copy = actions.clone();

    let skipped_unmanaged = actions.iter().filter(|act| {
        !remove_unmanaged_mods
            && act.state == ModState::Unmanaged
            && matches!(&act.action, SyncAction::Add(_) | SyncAction::Replace(_) | SyncAction::Remove(_))
    }).count();

    // remove the unmanaged mods if the user has chosen to do so
    // remove all nothing except noChanges
    actions.retain(|act| {
        if matches!(act.action, SyncAction::Failed(_)) {
            // this keep failed even if it is unmanaged, we keep it to report
            return true;
        }
        !matches!( &act.action, SyncAction::Nothing(reason) if reason != "noChanges") // it removes all nothing but keep noChanges to report progress 
        && (act.state != ModState::Unmanaged || remove_unmanaged_mods) // if remove_unmanaged_mods is false, we don't want to show unmanaged mods
    });

    debug!(
        "Sync actions:\n{}",
        actions_copy
            .iter()
            .filter(|act| !matches!(
                (&act.action, &act.state),
                (SyncAction::Nothing(reason), ModState::NotInstalled)
                    if reason == "disabledAndNotInstalled"
            ))
            .map(|act| format!("{:?}", act))
            .collect::<Vec<_>>()
            .join("\n")
    );

    info!(
        "Sync action (remove_unmanaged_mods = {}): {} add, {} remove, {} replace, {} nothing, {} failed | {} managed, {} unmanaged",
        remove_unmanaged_mods,
        actions_copy.iter().filter(|act| matches!(act.action, SyncAction::Add(_))).count(),
        actions_copy.iter().filter(|act| matches!(act.action, SyncAction::Remove(_))).count(),
        actions_copy.iter().filter(|act| matches!(act.action, SyncAction::Replace(_))).count(),
        actions_copy.iter().filter(|act| matches!(act.action, SyncAction::Nothing(_))).count(),
        actions_copy.iter().filter(|act| matches!(act.action, SyncAction::Failed(_))).count(),
        actions_copy.iter().filter(|act| matches!(act.state, ModState::Managed)).count(),
        actions_copy.iter().filter(|act| matches!(act.state, ModState::Unmanaged)).count()
    );

    drop(actions_copy);

    //if there is actions (not Nothing(noChanges)) and there is 
    // if there is no actions != Nothing(noChanges) we can just return early
    // return an error? so we can show a message?
    if actions
        .iter()
        .all(|act| matches!(act.action, SyncAction::Nothing(_)))
    {
        info!("No sync actions needed, exiting early.");
        app_handle
            .emit(
                "sync-end",
                SyncEndEvent {
                    r#type: SyncType::Sync,
                    success: true,
                    error: None,
                    total: 0,
                    synced: 0,
                },
            )
            .ok();
        return Ok(SyncResult {
            success: true,
            synced: 0,
            total: 0,
            skipped_unmanaged,
        });
    }

    if method == SyncMethod::Copy {
        let game_avaiable_space = get_available_size(&game_mods_path).ok(); // if we can't get the available space, we assume it's enough and let the sync fail if it runs out of space
                                                                            // [FIXME] simple check, problems: if the user only changed a few files, we will still count the whole mod size, and if the user has a mod that is already installed, we will count it again, even if it is not going to be copied again
                                                                            // but i think this is good enough for now because some mods is only a few MB, we can improve this later

        let total_space_needed: u64 = actions.iter().filter_map(|act| act.size).sum();
        if let Some(available_space) = game_avaiable_space {
            if available_space < total_space_needed {
                error!(
                    "Not enough available disk space for sync. Needed: {} bytes, Available: {} bytes",
                    total_space_needed, available_space
                );

                app_handle
                    .emit(
                        "sync-end",
                        SyncEndEvent {
                            r#type: SyncType::Sync,
                            success: false,
                            error: Some(&ModSyncError::NoAvailableDiskSpace),
                            total: actions.len(),
                            synced: 0,
                        },
                    )
                    .ok();

                return Err(ModSyncError::NoAvailableDiskSpace);
            }
        }
    }

    // add + remvoe + replace + failed
    let total_mods_count = actions.len();
    let mut synced_count = 0;
    let execution_started = Instant::now();
    let mut failed_removals: HashMap<String, Arc<ModSyncError>> = HashMap::new();

    for (index, action) in actions.iter().enumerate() {
        let (result_status, result_error) = {
            match &action.action {
                SyncAction::Add(_) | SyncAction::Replace(_)
                    if failed_removals.contains_key(&action.mod_name) => {
                    // keep the old destination until it can be removed
                    (SyncStatus::Failed, Some(Arc::clone(&failed_removals[&action.mod_name])))
                }
                SyncAction::Add(_) => {
                    let result = (|| -> Result<(), ModSyncError> {
                        let source = staging_directory.join(&action.mod_name);
                        let destination = game_mods_path.join(&action.game_folder);

                        // check if the mod on staging contains symlinks
                        for entry in WalkDir::new(&source).follow_links(false) {
                            let entry = entry.map_err(io::Error::from)?;

                            if fs::symlink_metadata(entry.path())?.file_attributes() & 0x400 != 0 {
                                return Err(ModSyncError::ModContainsSymlink {
                                    path: entry.path().to_string_lossy().to_string(),
                                });
                            }
                        }

                        match method {
                            SyncMethod::Copy => {
                                match sync_dirs(&source, &destination) {
                                    Ok(_) => Ok(()),
                                    Err(error) => {
                                        error!("Failed to copy mod {}: {}", action.mod_name, error);

                                        // remove the partial copy
                                        remove_mod_path(&destination).map_err(|source| {
                                            ModSyncError::RemovalFailed {
                                                path: destination.to_string_lossy().to_string(),
                                                source,
                                            }
                                        })?;

                                        Err(match error {
                                            ModSyncError::Io(source) => ModSyncError::CopyFailed {
                                                mod_name: action.mod_name.clone(),
                                                source,
                                            },
                                            error => error,
                                        })
                                    }
                                }
                            }
                            SyncMethod::Symlink => {
                                let source = source.canonicalize()?;

                                std::os::windows::fs::symlink_dir(&source, &destination).map_err(
                                    |source| ModSyncError::SymlinkFailed {
                                        mod_name: action.mod_name.clone(),
                                        source,
                                    },
                                )?;

                                Ok(())
                            }
                        }
                    })();

                    match result {
                        Ok(()) => (SyncStatus::Synced, None),
                        Err(error) => (SyncStatus::Failed, Some(Arc::new(error))),
                    }
                }
                SyncAction::Remove(_) => {
                    // remove
                    let game_mod_path = game_mods_path.join(&action.game_folder);
                    match remove_mod_path(&game_mod_path) {
                        Ok(()) => (SyncStatus::Removed, None),
                        Err(source) => {
                            let error = Arc::new(ModSyncError::RemovalFailed {
                                path: game_mod_path.to_string_lossy().to_string(),
                                source,
                            });
                            failed_removals.insert(action.mod_name.clone(), Arc::clone(&error));
                            (SyncStatus::Failed, Some(error))
                        }
                    }
                }
                SyncAction::Replace(_) => {
                    // remove and add

                    let replace_result = (|| -> Result<(), ModSyncError> {
                        let source = staging_directory.join(&action.mod_name);
                        let destination = game_mods_path.join(&action.game_folder);

                        // check if the mod on staging contains symlinks
                        for entry in WalkDir::new(&source).follow_links(false) {
                            let entry = entry.map_err(io::Error::from)?;

                            if fs::symlink_metadata(entry.path())?.file_attributes() & 0x400 != 0 {
                                return Err(ModSyncError::ModContainsSymlink {
                                    path: entry.path().to_string_lossy().to_string(),
                                });
                            }
                        }

                        remove_mod_path(&destination).map_err(|source| {
                            ModSyncError::RemovalFailed {
                                path: destination.to_string_lossy().to_string(),
                                source,
                            }
                        })?;

                        match method {
                            SyncMethod::Copy => sync_dirs(&source, &destination)
                                .map(|_| ())
                                .map_err(|error| match error {
                                    ModSyncError::Io(source) => ModSyncError::CopyFailed {
                                        mod_name: action.mod_name.clone(),
                                        source,
                                    },
                                    error => error,
                                }),
                            SyncMethod::Symlink => {
                                let source = source.canonicalize()?;

                                std::os::windows::fs::symlink_dir(&source, &destination).map_err(
                                    |source| ModSyncError::SymlinkFailed {
                                        mod_name: action.mod_name.clone(),
                                        source,
                                    },
                                )?;

                                Ok(())
                            }
                        }
                    })();

                    match replace_result {
                        Ok(()) => (SyncStatus::Synced, None),
                        Err(error) => (SyncStatus::Failed, Some(Arc::new(error))),
                    }
                }
                SyncAction::Nothing(_) => {
                    // only Nothing("noChanges")
                    // just emit the progress
                    (SyncStatus::UpToDate, None)
                }
                SyncAction::Failed(error) => {
                    // emit the progress with the error
                    (SyncStatus::Failed, Some(Arc::clone(error)))
                }
            }
        };

        match &result_status {
            SyncStatus::Synced => {
                // add or update the manifest entry
                if let Some(entry) = manifest
                    .synced_mods
                    .iter_mut()
                    .find(|entry| entry.mod_name == action.mod_name)
                {
                    entry.game_folder = action.game_folder.clone();
                    entry.method = method;
                } else {
                    manifest.synced_mods.push(SyncedMod {
                        mod_name: action.mod_name.clone(),
                        game_folder: action.game_folder.clone(),
                        method,
                    });
                }
            }
            SyncStatus::Removed => {
                // remove the manifest entry
                manifest
                    .synced_mods
                    .retain(|entry| entry.mod_name != action.mod_name);
            }
            SyncStatus::UpToDate => {
                // do nothing
            }
            SyncStatus::Failed => {
                error!(
                    "Sync failed for mod {}: {:?}",
                    action.mod_name,
                    result_error.as_ref().map(|error| error.to_string())
                );
            }
        }

        if matches!(result_status, SyncStatus::Synced | SyncStatus::Removed) {
            manifest.synced_at = chrono::Utc::now();

            if let Err(source) = save_manifest(&manifest_path, manifest.clone()) {
                let error = ModSyncError::ManifestSaveFailed { source };

                error!("Failed to save sync manifest: {}", error);
                debug!(
                    "Sync stopped at {}/{} ({}). Execution: {:.3} ms, total: {:.3} ms",
                    index + 1,
                    total_mods_count,
                    action.mod_name,
                    execution_started.elapsed().as_secs_f64() * 1000.0,
                    sync_started.elapsed().as_secs_f64() * 1000.0
                );

                app_handle
                    .emit(
                        "sync-end",
                        SyncEndEvent {
                            r#type: SyncType::Sync,
                            success: false,
                            error: Some(&error),
                            synced: synced_count,
                            total: total_mods_count,
                        },
                    )
                    .ok();

                return Err(error);
            }
        }

        if !matches!(result_status, SyncStatus::Failed) {
            synced_count += 1;
        }

        app_handle
            .emit(
                "sync-progress",
                SyncProgressEvent {
                    r#type: SyncType::Sync,
                    mod_name: action.mod_name.clone(),
                    current: index + 1,
                    total: total_mods_count,
                    status: result_status,
                    error: result_error,
                },
            )
            .ok();
    }

    debug!(
        "Executed {} actions in {:.3} ms. Successful: {}, failed: {}",
        total_mods_count,
        execution_started.elapsed().as_secs_f64() * 1000.0,
        synced_count,
        total_mods_count - synced_count
    );

    // debug sync results
    info!(
        "Sync completed. Synced: {}, Total: {}",
        synced_count, total_mods_count
    );
    debug!("{:#?}", manifest);

    app_handle
        .emit(
            "sync-end",
            SyncEndEvent {
                r#type: SyncType::Sync,
                success: true,
                error: None,
                synced: synced_count,
                total: total_mods_count,
            },
        )
        .ok();

    debug!(
        "Total sync time: {:.3} ms",
        sync_started.elapsed().as_secs_f64() * 1000.0
    );

    Ok(SyncResult {
        success: true,
        synced: synced_count,
        total: total_mods_count,
        skipped_unmanaged,
    })
}

pub fn unsync_mods<R: tauri::Runtime>(
    app_handle: &tauri::AppHandle<R>,
    game_directory: &PathBuf,
    staging_directory: &PathBuf,
    removed_unmanaged_mods: bool,
) -> Result<SyncResult, ModSyncError> {
    debug!("Starting unsync (remove_unmanaged_mods = {})", removed_unmanaged_mods);

    let manifest_path = game_directory.join(".bd2mm.json");

    app_handle
        .emit(
            "sync-start",
            SyncStartEvent {
                r#type: SyncType::Unsync,
            },
        )
        .ok();

    let mut total_mods = 0;
    let mut unsynced = 0;
    let mut skipped_unmanaged = 0;

    let result = (|| -> Result<(), ModSyncError> {
        let mut manifest = load_manifest(&manifest_path)?;
        let game_mods_path = get_sync_directory(game_directory, staging_directory)?;

        if !removed_unmanaged_mods {
            let mut entries = WalkDir::new(&game_mods_path).follow_links(false).min_depth(1).into_iter();
            while let Some(entry) = entries.next() {
                let entry = entry.map_err(io::Error::from)?;
                let relative = entry.path().strip_prefix(&game_mods_path).unwrap();
                let saved = manifest.as_ref().map(|manifest| &manifest.synced_mods);

                if saved.is_some_and(|mods| mods.iter().any(|entry| Path::new(&entry.game_folder) == relative)) {
                    if entry.file_type().is_dir() {
                        entries.skip_current_dir();
                    }
                    continue;
                }
                // old manifests can have nested folders
                if saved.is_some_and(|mods| mods.iter().any(|entry| Path::new(&entry.game_folder).starts_with(relative))) {
                    continue;
                }
                skipped_unmanaged += 1;
                if entry.file_type().is_dir() {
                    entries.skip_current_dir();
                }
            }
        }
        if manifest.is_none() && !removed_unmanaged_mods {
            debug!("No manifest found and remove_unmanaged_mods is false, nothing to unsync.");
            return Ok(());
        }

        let entries = if removed_unmanaged_mods {
            game_mods_path
                .read_dir()?
                .map(|entry| entry.map(|entry| entry.path()))
                .collect::<Result<Vec<_>, io::Error>>()?
        } else {
            // use saved paths, including old nested folders
            manifest.as_ref().unwrap().synced_mods.iter()
                .map(|entry| game_mods_path.join(&entry.game_folder))
                .filter(|path| !matches!(fs::symlink_metadata(path), Err(error) if error.kind() == io::ErrorKind::NotFound))
                .collect()
        };

        total_mods = entries.len();

        let mut failed = 0;

        for (index, path) in entries.into_iter().enumerate() {
            debug!("Removing mod at path: {:?}", path);

            let (status, error) = match check_mod_parents(&path, &game_mods_path).and_then(|()| {
                remove_mod_path(&path).map_err(|source| ModSyncError::RemovalFailed {
                    path: path.to_string_lossy().to_string(),
                    source,
                })
            }) {
                Ok(_) => {
                    unsynced += 1;
                    
                    if let Some(manifest) = &mut manifest {
                        let relative = path.strip_prefix(&game_mods_path).unwrap();

                        manifest
                            .synced_mods
                            .retain(|entry| !Path::new(&entry.game_folder).starts_with(relative));
                    }

                    (SyncStatus::Removed, None)
                }
                Err(source) => {
                    failed += 1;

                    (
                        SyncStatus::Failed,
                        Some(source),
                    )
                }
            };

            app_handle
                .emit(
                    "sync-progress",
                    SyncProgressEvent {
                        r#type: SyncType::Unsync,
                        mod_name: path
                            .file_name()
                            .and_then(|name| name.to_str())
                            .unwrap_or_default()
                            .to_string(),
                        current: index + 1,
                        total: total_mods,
                        status,
                        error: error.map(Arc::new),
                    },
                )
                .ok();
        }

        if let Some(mut manifest) = manifest {
            // remove entries whose folders are already missing
            manifest.synced_mods.retain(|entry| {
                let path = game_mods_path.join(&entry.game_folder);

                match fs::symlink_metadata(&path) {
                    Ok(_) => true,
                    Err(error) if error.kind() == io::ErrorKind::NotFound => false,
                    Err(error) => {
                        warn!("Failed to check mod {}: {}", entry.mod_name, error);
                        true
                    }
                }
            });

            if manifest.synced_mods.is_empty() && failed == 0 {
                match fs::remove_file(&manifest_path) {
                    Ok(_) => {}
                    Err(error) if error.kind() == io::ErrorKind::NotFound => {}
                    Err(error) => return Err(error.into()),
                }
            } else {
                save_manifest(&manifest_path, manifest)
                    .map_err(|source| ModSyncError::ManifestSaveFailed { source })?;
            }
        }

        if failed > 0 {
            return Err(ModSyncError::UnsyncFailed {
                failed,
                total: total_mods,
            });
        }

        Ok(())
    })();

    app_handle
        .emit(
            "sync-end",
            SyncEndEvent {
                r#type: SyncType::Unsync,
                success: matches!(&result, Ok(()) | Err(ModSyncError::UnsyncFailed { .. })),
                synced: unsynced,
                total: total_mods,
                error: result.as_ref().err(),
            },
        )
        .ok();

    match result {
        Ok(()) | Err(ModSyncError::UnsyncFailed { .. }) => Ok(SyncResult {
            success: true,
            synced: unsynced,
            total: total_mods,
            skipped_unmanaged,
        }),
        Err(error) => Err(error),
    }
}

pub fn is_sync_needed(
    game_directory: &PathBuf,
    staging_directory: &PathBuf,
    method: SyncMethod,
    staging_mods: Vec<&BD2Mod>,
) -> bool {
    let manifest_path = game_directory.join(".bd2mm.json");
    let game_mods_path = game_directory.join("BepInEx/plugins/BrownDustX/mods/BD2MM");

    if !game_mods_path.exists() {
        debug!("Game mods path does not exist, is sync needed = true");
        return true;
    }

    let manifest = match load_manifest(&manifest_path) {
        Ok(Some(m)) => m,
        Ok(None) | Err(_) => {
            debug!("Manifest cannot be loaded, is sync needed = true");
            return true;
        }
    };

    let actions = match get_sync_actions(
        &manifest,
        game_directory,
        staging_directory,
        &method,
        staging_mods,
    ) {
        Ok(actions) => actions,
        Err(err) => {
            debug!(
                "Failed to get sync actions: {:?}, is sync needed = true",
                err
            );
            return true;
        }
    };

    let is_sync_needed = actions.iter().any(|act| {
        act.state != ModState::Unmanaged
            && matches!(&act.action, SyncAction::Add(_) | SyncAction::Remove(_) | SyncAction::Replace(_))
    });

    debug!("[is_sync_needed] {} sync actions ({} add, {} remove, {} replace, {} nothing, {} failed | {} managed, {} unmanaged), is sync needed = {}", actions.len(), 
        actions.iter().filter(|act| matches!(act.action, SyncAction::Add(_))).count(),
        actions.iter().filter(|act| matches!(act.action, SyncAction::Remove(_))).count(),
        actions.iter().filter(|act| matches!(act.action, SyncAction::Replace(_))).count(),
        actions.iter().filter(|act| matches!(act.action, SyncAction::Nothing(_))).count(),
        actions.iter().filter(|act| matches!(act.action, SyncAction::Failed(_))).count(),
        actions.iter().filter(|act| matches!(act.state, ModState::Managed)).count(),
        actions.iter().filter(|act| matches!(act.state, ModState::Unmanaged)).count(),
        is_sync_needed
    );

    // only actions that change files need syncing
    is_sync_needed
}

