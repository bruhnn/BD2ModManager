use std::{collections::HashMap, path::PathBuf};

pub mod config;
pub mod game;
pub mod mods;
pub mod profiles;
pub mod utils;

use log::{debug, error, info, warn};
use serde::Serialize;
use tauri::{AppHandle, Emitter};

use crate::mods::delete::ModDeleteError;
use crate::mods::install::ModInstallError;
use crate::mods::metadata::{MetadataError, ModMetadataStore};
use crate::mods::preview::PreviewError;
use crate::mods::sync::{ModSyncError, SyncMethod};
use crate::mods::BD2Mod;
use crate::profiles::types::{Profile, ProfileError};
use crate::profiles::ProfileManager;

#[derive(thiserror::Error, Debug)]
pub enum ModError {
    #[error("game directory is not set")]
    GameDirectoryNotSet,
    #[error("invalid sync method: {0}")]
    SyncMethodInvalid(String),

    #[error(transparent)]
    Io(#[from] std::io::Error),
    #[error(transparent)]
    Install(#[from] ModInstallError),
    #[error(transparent)]
    Delete(#[from] ModDeleteError),
    #[error(transparent)]
    Sync(#[from] ModSyncError),
    #[error(transparent)]
    Rename(#[from] ModRenameError),
    #[error(transparent)]
    Profile(#[from] ProfileError),
    #[error(transparent)]
    Metadata(#[from] MetadataError),
    #[error(transparent)]
    Preview(#[from] PreviewError),
    #[error("unknown error: {0}")]
    Unknown(String)
}

#[derive(thiserror::Error, Debug, Serialize)]
#[serde(tag = "type", content = "message")]
pub enum ModRenameError {
    #[error("mod not found: {0}")]
    NotFound(String),
    #[error("mod path does not exist on disk: {0}")]
    PathMissing(String),
    #[error("mod with new name already exists: {0}")]
    AlreadyExists(String),
    #[error("failed to rename mod: {0}")]
    IoError(String),
}

impl serde::Serialize for ModError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where S: serde::Serializer {
        use serde::ser::SerializeStruct;
        let mut s = serializer.serialize_struct("Error", 2)?;
         let type_ = match self {
            ModError::Io(_) => "io",
            ModError::Install(_) => "install",
            ModError::Delete(_) => "delete",
            ModError::Sync(_) => "sync",
            ModError::Rename(_) => "rename",
            ModError::Profile(_) => "profile",
            ModError::Metadata(_) => "metadata",
            ModError::Preview(_) => "preview",
            ModError::Unknown(_) => "unknown",
            ModError::GameDirectoryNotSet => "game_directory_not_set",
            ModError::SyncMethodInvalid(_) => "sync_method_invalid",
        };
        s.serialize_field("type", type_)?;
        s.serialize_field("message", &self.to_string())?;
        s.end()
    }
}

pub struct BD2ModManager {
    pub profile_manager: ProfileManager,
    pub cached_mods: HashMap<String, BD2Mod>,
    pub metadata_store: ModMetadataStore,
}
//
impl BD2ModManager {
    pub fn new(profile_manager: ProfileManager, metadata_store: ModMetadataStore) -> Self {
        Self {
            profile_manager,
            cached_mods: HashMap::new(),
            metadata_store,
        }
    }

    pub fn discover_mods(
        &mut self,
        staging_dir: &PathBuf,
        recursive: bool,
    ) -> Vec<BD2Mod> {
        info!(
            "Searching for mods on staging directory ({:?})",
            staging_dir
        );

        let mods_found: Vec<BD2Mod> = mods::discover::discover_staging_mods(staging_dir, recursive);

        self.cached_mods.clear();

        for _mod in mods_found {
            self.cached_mods.insert(_mod.name.clone(), _mod);
        }

        // detect if mods edits the same files (mod type + mod id)
        mods::conflict::detect_conflicts(&mut self.cached_mods);

        // apply stored metadata (author, etc.)
        self.metadata_store.apply_to_mods(&mut self.cached_mods);

        // set mods enabled states with the active proifle
        self.sync_mods_with_profiles();

        self.get_mods()
    }

    fn sync_mods_with_profiles(&mut self) {
        if let Some(active_profile) = self.profile_manager.get_active_profile() {
            info!("Active profile ({:?}), updating mod states", active_profile);
            //
            for bd2mod in self.cached_mods.values_mut() {
                bd2mod.enabled = active_profile.get_mod_state(&bd2mod.name);
            }
        } else {
            warn!("No active profile found. Disabing all mods by default.");
            for bd2mod in self.cached_mods.values_mut() {
                bd2mod.enabled = false;
            }
        }
    }

    fn change_mods_state(&mut self, mod_names: Vec<String>, enabled: bool) {
        for mod_name in mod_names.iter() {
            if let Some(bd2mod) = self.cached_mods.get_mut(mod_name) {
                bd2mod.enabled = enabled;
                debug!(
                    "{} mod: {}",
                    if enabled { "Enabled" } else { "Disabled" },
                    bd2mod.name
                );
            } else {
                warn!("Mod not found: {}", mod_name);
            }
        }

        if let Some(active_profile) = self.profile_manager.get_active_profile() {
            for mod_name in mod_names.iter() {
                active_profile.set_mod_state(mod_name, enabled);
            }
        }

        if let Err(e) = self.profile_manager.save_active_profile() {
            warn!(
                "Failed to save profiles after changing mod state: {:?}",
                e
            );
        }
    }

    // mods Methods
    pub fn get_mods(&self) -> Vec<BD2Mod> {
        let mut mods: Vec<BD2Mod> = self.cached_mods.values().cloned().collect();
        mods.sort_by(|a, b| a.name.cmp(&b.name));
        mods
    }

    pub fn get_mod_by_name(&self, mod_name: &str) -> Option<BD2Mod> {
        self.cached_mods.get(mod_name).cloned()
    }

    pub fn enable_mods(&mut self, mod_names: Vec<String>) -> Vec<BD2Mod> {
        self.change_mods_state(mod_names, true);
        self.get_mods()
    }

    pub fn disable_mods(&mut self, mod_names: Vec<String>) -> Vec<BD2Mod> {
        self.change_mods_state(mod_names, false);
        self.get_mods()
    }

    // profile
    pub fn load_profiles(&mut self) -> Result<(), ProfileError> {
        self.profile_manager.load_profiles()
    }

    pub fn get_profiles(&self) -> Vec<Profile> {
        self.profile_manager.get_profiles()
    }

    pub fn get_active_profile(&mut self) -> Option<&mut Profile> {
        self.profile_manager.get_active_profile()
    }

    pub fn create_profile(
        &mut self,
        name: String,
        description: Option<String>,
        template_id: Option<String>,
    ) -> Result<(), ProfileError> {
        self.profile_manager
            .create_profile(name, description, None, None, template_id)
    }

    pub fn switch_profile(
        &mut self,
        app_handle: &AppHandle,
        profile_id: String,
    ) -> Result<(), ProfileError> {
        info!("Switching profile to {:?}", profile_id);

        self.profile_manager.set_active_profile(profile_id)?;

        self.sync_mods_with_profiles();

        if let Err(e) = self.update_mods_on_frontend(app_handle) {
            error!("Failed to update frontend after switching profile: {:?}", e);
        }

        Ok(())
    }

    pub fn edit_profile(
        &mut self,
        profile_id: String,
        name: String,
        description: Option<String>,
    ) -> Result<(), ProfileError> {
        self.profile_manager
            .edit_profile(profile_id, name, description)
    }

    pub fn delete_profile(
        &mut self,
        app_handle: &AppHandle,
        profile_id: String,
    ) -> Result<(), ProfileError> {
        self.profile_manager.delete_profile(profile_id)?;
        self.sync_mods_with_profiles();

        if let Err(e) = self.update_mods_on_frontend(app_handle) {
            warn!("Failed to update frontend after deleting profile: {:?}", e);
        }

        Ok(())
    }

    // manager
    pub fn install_mod(
        &mut self,
        path: PathBuf,
        staging_dir: &PathBuf,
    ) -> Result<BD2Mod, ModInstallError> {
        let mod_path = mods::install::install_mod(&path, staging_dir)?;

        let (is_mod, error) = mods::discover::analyze_mod_path(&mod_path);
        if is_mod {
            let mut new_mod = mods::discover::create_mod(staging_dir, &mod_path, error);
            let mod_name = new_mod.name.clone();
            self.cached_mods.insert(mod_name.clone(), new_mod.clone());
            mods::conflict::detect_conflicts(&mut self.cached_mods);
            self.metadata_store.apply_to_mod(&mut new_mod);
            self.sync_mods_with_profiles();
            Ok(new_mod)
        } else {
            Err(ModInstallError::InvalidMod)
        }
    }

    pub fn sync_mods(
        &mut self,
        app_handle: &AppHandle,
        game_directory: &PathBuf,
        method: SyncMethod,
    ) -> Result<(), ModSyncError> {
        let mods: Vec<&BD2Mod> = self.cached_mods.values().collect();

        mods::sync::sync_mods(app_handle, game_directory, mods, method)
    }

    pub fn unsync_mods(
        &mut self,
        app_handle: &AppHandle,
        game_directory: &PathBuf,
    ) -> Result<(), ModSyncError> {
        // let mods: Vec<&BD2Mod> = self.cached_mods.values().collect();
        // [TODO] unsync all mods, or only the ones that are currently synced (in manifest)? 
        mods::sync::unsync_mods(app_handle, game_directory)
    }

    pub fn is_sync_needed(&self, game_directory: &PathBuf) -> bool {
        let mods: Vec<&BD2Mod> = self.cached_mods.values().collect();

        mods::sync::is_sync_needed(game_directory, &mods)
    }

    pub fn delete_mod(&mut self, mod_name: String) -> Result<(), ModDeleteError> {
        let mod_ = self.get_mod_by_name(&mod_name).ok_or_else(|| ModDeleteError::NotFound(mod_name))?;

        mods::delete::delete_mod(&mod_).map_err(|e| {
            error!("Failed to delete mod: {:?}, error: {:?}", mod_, e);
            ModDeleteError::FailedToDelete(mod_.name.clone())
        })?;

        self.cached_mods.remove(&mod_.name);

        self.profile_manager.remove_mod_from_profiles(&mod_.name);

        if let Err(e) = self.metadata_store.remove_mod(&mod_.name) {
            warn!("Failed to remove metadata for deleted mod {}: {:?}", mod_.name, e);
        }
        Ok(())
    }

    pub fn rename_mod(
        &mut self,
        old_name: String,
        new_name: String,
    ) -> Result<BD2Mod, ModRenameError> {
        if let Some(mod_info) = self.cached_mods.get(&old_name) {
            let mod_path = mod_info.path.clone();
            let new_path = mod_path
                .parent()
                .unwrap_or_else(|| std::path::Path::new(""))
                .join(&new_name);
            
            if new_path.exists() {
                error!("A mod with the new name already exists: {:?}", new_path);
                return Err(ModRenameError::AlreadyExists(new_name));
            }

            if mod_path.exists() {
                if let Err(e) = std::fs::rename(&mod_path, &new_path) {
                    error!(
                        "Failed to rename mod from {:?} to {:?}: {:?}",
                        mod_path, new_path, e
                    );
                    return Err(ModRenameError::IoError(e.to_string()));
                }
            } else {
                error!("Mod path does not exist: {:?}", mod_path);
                return Err(ModRenameError::PathMissing(old_name));
            }

            let mut updated_mod = mod_info.clone();
            updated_mod.name = new_name.clone();
            updated_mod.path = new_path.clone();
            updated_mod.display_name = new_path
                .file_name()
                .map(|name| name.to_string_lossy().into_owned())
                .unwrap_or_else(|| "unknown".to_string());

            self.cached_mods.remove(&old_name);
            self.cached_mods.insert(new_name.clone(), updated_mod.clone());

            if let Err(e) = self.metadata_store.rename_mod(&old_name, &new_name) {
                warn!("Failed to rename metadata for mod {}: {:?}", old_name, e);
            }

            Ok(updated_mod)
        } else {
            error!("Mod not found for renaming: {}", old_name);
            Err(ModRenameError::NotFound(old_name))
        }
    }

    // metadata
    pub fn set_mod_author(
        &mut self,
        mod_names: Vec<String>,
        author: Option<String>,
    ) -> Result<Vec<BD2Mod>, MetadataError> {
        // if it fails to set the author in the metadata store, we return an error and do not update the cached mods
        self.metadata_store.set_authors(&mod_names, author.clone())?;

        let mut mods_updated: Vec<BD2Mod> = Vec::new();
        for mod_name in &mod_names {
            if let Some(mod_info) = self.cached_mods.get_mut(mod_name) {
                mod_info.author = author.clone();
                mods_updated.push(mod_info.clone());
            }
        }

        Ok(mods_updated)
    }

    pub fn refresh_mods_authors(&mut self, app_handle: &AppHandle) -> Result<(), String> {
        for mod_info in self.cached_mods.values_mut() {
            let author = self.metadata_store.get_author(&mod_info.name);
            mod_info.author = author;
        }
        let all_mods: Vec<&BD2Mod> = self.cached_mods.values().collect();
        app_handle.emit("mods-changed", all_mods).unwrap();
        Ok(())
    }

    pub fn update_mods_on_frontend(&self, app_handle: &AppHandle) -> Result<(), String> {
        let all_mods: Vec<&BD2Mod> = self.cached_mods.values().collect();
        app_handle
            .emit("mods-changed", all_mods)
            .map_err(|e| format!("Failed to emit mods-changed event: {:?}", e))
        // instead of sending all the mods, we send a event "asking" to the frontend to refrest the mod list
    }
}
