use std::{collections::HashMap, path::PathBuf};

pub mod config;
pub mod game;
pub mod mods;
pub mod profiles;
pub mod utils;

use log::{info, warn};
use tauri::{AppHandle, Emitter};

use crate::mods::metadata::ModMetadataStore;
use crate::mods::sync::{SyncError, SyncMethod};
use crate::mods::BD2Mod;
use crate::profiles::types::{Profile, ProfileError};
use crate::profiles::ProfileManager;

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
        app_handle: &AppHandle,
        staging_dir: &PathBuf,
        recursive: bool,
    ) {
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

        // sent event to frontend
        let all_mods: Vec<&BD2Mod> = self.cached_mods.values().collect();
        // all_mods.sort_by(|a, b| a.name.cmp(&b.name));
        app_handle.emit("mods-changed", all_mods).unwrap();
    }

    fn sync_mods_with_profiles(&mut self) {
        if let Some(active_profile) = self.profile_manager.get_active_profile() {
            info!("Active profile ({:?})", active_profile);
            //
            for bd2mod in self.cached_mods.values_mut() {
                bd2mod.enabled = active_profile.get_mod_state(&bd2mod.name);
            }
        } else {
            warn!("No active profile found.");
        }
    }

    // mods Methods
    pub fn enable_mods(&mut self, app_handle: &AppHandle, mod_names: Vec<String>) {
        for mod_name in mod_names.iter() {
            if let Some(bd2mod) = self.cached_mods.get_mut(mod_name) {
                bd2mod.enabled = true;
                info!("Enabled mod: {}", bd2mod.name);
            } else {
                warn!("Mod not found: {}", mod_name);
            }
        }

        if let Some(active_profile) = self.profile_manager.get_active_profile() {
            for mod_name in mod_names.iter() {
                active_profile.set_mod_state(mod_name, true);
            }
        }

        if let Err(e) = self.profile_manager.save_active_profile() {
            warn!("Failed to save profiles after enabling mods: {:?}", e);
        }

        let all_mods: Vec<&BD2Mod> = self.cached_mods.values().collect();
        app_handle.emit("mods-changed", all_mods).unwrap();
    }

    /// Enable mods in a specific profile (may differ from active).
    pub fn enable_mods_in_profile(
        &mut self,
        app_handle: &AppHandle,
        profile_id: &str,
        mod_names: Vec<String>,
    ) -> Result<(), ProfileError> {
        let mut mods_to_disable: Vec<String> = Vec::new();
        for mod_name in mod_names.iter() {
            if let Some(bd2mod) = self.cached_mods.get(mod_name) {
                for conflict_name in bd2mod.conflicts_with.iter() {
                    if !mod_names.contains(conflict_name) && !mods_to_disable.contains(conflict_name) {
                        mods_to_disable.push(conflict_name.clone());
                    }
                }
            }
        }
        let is_active = self.profile_manager.enable_mods_in_profile(profile_id, &mod_names)?;
        if is_active && !mods_to_disable.is_empty() {
            if let Some(active_profile) = self.profile_manager.get_active_profile() {
                for mod_name in mods_to_disable.iter() {
                    active_profile.set_mod_state(mod_name, false);
                }
            }
            if let Err(e) = self.profile_manager.save_active_profile() {
                warn!("Failed to save after disabling conflicts: {:?}", e);
            }
        }
        if is_active {
            for mod_name in mod_names.iter() {
                if let Some(bd2mod) = self.cached_mods.get_mut(mod_name) { bd2mod.enabled = true; }
            }
            for mod_name in mods_to_disable.iter() {
                if let Some(bd2mod) = self.cached_mods.get_mut(mod_name) { bd2mod.enabled = false; }
            }
            let all_mods: Vec<&BD2Mod> = self.cached_mods.values().collect();
            app_handle.emit("mods-changed", all_mods).unwrap();
        }
        Ok(())
    }

    /// Replace a profile's enabled-mods list.
    pub fn set_profile_enabled_mods(
        &mut self,
        app_handle: &AppHandle,
        profile_id: &str,
        mod_names: Vec<String>,
    ) -> Result<(), ProfileError> {
        let is_active = self.profile_manager.set_profile_enabled_mods(profile_id, mod_names)?;
        if is_active {
            self.sync_mods_with_profiles();
            let all_mods: Vec<&BD2Mod> = self.cached_mods.values().collect();
            app_handle.emit("mods-changed", all_mods).unwrap();
        }
        Ok(())
    }

    pub fn disable_mods(&mut self, app_handle: &AppHandle, mod_names: Vec<String>) {
        for mod_name in mod_names.iter() {
            if let Some(bd2mod) = self.cached_mods.get_mut(mod_name) {
                bd2mod.enabled = false;
                info!("Disabled mod: {}", bd2mod.name);
            } else {
                warn!("Mod not found: {}", mod_name);
            }
        }

        if let Some(active_profile) = self.profile_manager.get_active_profile() {
            for mod_name in mod_names.iter() {
                active_profile.set_mod_state(mod_name, false);
            }
        }

        if let Err(e) = self.profile_manager.save_active_profile() {
            warn!("Failed to save profiles after disabling mods: {:?}", e);
        }

        let all_mods: Vec<&BD2Mod> = self.cached_mods.values().collect();
        app_handle.emit("mods-changed", all_mods).unwrap();
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

        self.sync_mods_with_profile();

        if let Err(e) = self.update_mods_on_frontend(app_handle) {
            warn!("Failed to update frontend after switching profile: {:?}", e);
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
        self.sync_mods_with_profile();

        if let Err(e) = self.update_mods_on_frontend(app_handle) {
            warn!("Failed to update frontend after deleting profile: {:?}", e);
        }

        Ok(())
    }

    // manager
    pub fn install_mod(
        &mut self,
        app_handle: &AppHandle,
        path: PathBuf,
        staging_dir: &PathBuf,
    ) -> Result<String, mods::install::ModInstallError> {
        let mod_path = mods::install::install_mod(&path, staging_dir)?;

        let (is_mod, error) = mods::discover::analyze_mod_path(&mod_path);
        if is_mod {
            let new_mod = mods::discover::create_mod(staging_dir, &mod_path, error);
            let mod_name = new_mod.name.clone();
            self.cached_mods.insert(mod_name.clone(), new_mod);
            mods::conflict::detect_conflicts(&mut self.cached_mods);
            self.metadata_store.apply_to_mods(&mut self.cached_mods);
            self.sync_mods_with_profiles();
            let all_mods: Vec<&BD2Mod> = self.cached_mods.values().collect();
            app_handle.emit("mods-changed", all_mods).unwrap();
            Ok(mod_name)
        } else {
            Err(mods::install::ModInstallError::InvalidMod)
        }
    }

    pub fn sync_mods(
        &mut self,
        app_handle: &AppHandle,
        game_directory: &PathBuf,
        method: SyncMethod,
    ) -> Result<(), SyncError> {
        let mods: Vec<&BD2Mod> = self.cached_mods.values().collect();

        mods::sync::sync_mods(app_handle, game_directory, mods, method)
    }

    pub fn unsync_mods(
        &mut self,
        app_handle: &AppHandle,
        game_directory: &PathBuf,
    ) -> Result<(), SyncError> {
        let _mods: Vec<&BD2Mod> = self.cached_mods.values().collect();

        mods::sync::unsync_mods(app_handle, game_directory)
    }

    pub fn is_sync_needed(&self, _app_handle: &AppHandle, game_directory: &PathBuf) -> bool {
        let mods: Vec<&BD2Mod> = self.cached_mods.values().collect();

        mods::sync::is_sync_needed(game_directory, &mods)
    }

    fn delete_mod(&mut self, mod_name: String) -> Result<(), String> {
        // [TODO] move to mods::delete
        if let Some(mod_info) = self.cached_mods.get(&mod_name) {
            let mod_path = mod_info.path.clone();

            let rel = PathBuf::from(&mod_info.name);
            let staging_dir = mod_path
                .ancestors()
                .nth(rel.components().count())
                .map(|p| p.to_path_buf());

            if mod_path.exists() {
                if mod_path.is_dir() {
                    std::fs::remove_dir_all(&mod_path).map_err(|e| {
                        format!("Failed to delete mod directory {:?}: {:?}", mod_path, e)
                    })?;
                } else {
                    std::fs::remove_file(&mod_path).map_err(|e| {
                        format!("Failed to delete mod file {:?}: {:?}", mod_path, e)
                    })?;
                }

                if let Some(staging) = staging_dir {
                    let mut current = mod_path.parent().map(|p| p.to_path_buf());
                    while let Some(dir) = current {
                        if dir == staging {
                            break;
                        }

                        // Only remove if the directory is empty
                        match std::fs::read_dir(&dir) {
                            Ok(mut entries) => {
                                if entries.next().is_none() {
                                    let _ = std::fs::remove_dir(&dir);
                                } else {
                                    break; // directory still has other mods
                                }
                            }
                            Err(_) => break,
                        }
                        current = dir.parent().map(|p| p.to_path_buf());
                    }
                }
            }
            self.cached_mods.remove(&mod_name);
            Ok(())
        } else {
            Err(format!("Mod '{}' not found", mod_name))
        }
    }

    pub fn delete_mods(&mut self, app_handle: &AppHandle, mod_names: Vec<String>) -> bool {
        for mod_name in mod_names {
            let _ = self.delete_mod(mod_name);
        }
        let all_mods: Vec<&BD2Mod> = self.cached_mods.values().collect();
        app_handle.emit("mods-changed", all_mods).unwrap();
        true
    }

    pub fn rename_mod(
        &mut self,
        app_handle: &AppHandle,
        old_name: String,
        new_name: String,
    ) -> bool {
        if let Some(mod_info) = self.cached_mods.get(&old_name) {
            let mod_path = mod_info.path.clone();
            let new_path = mod_path
                .parent()
                .unwrap_or_else(|| std::path::Path::new(""))
                .join(&new_name);

            if mod_path.exists() {
                if let Err(e) = std::fs::rename(&mod_path, &new_path) {
                    eprintln!(
                        "Failed to rename mod from {:?} to {:?}: {:?}",
                        mod_path, new_path, e
                    );
                    return false;
                }
            } else {
                eprintln!("Mod path does not exist: {:?}", mod_path);
                return false;
            }

            let mut updated_mod = mod_info.clone();
            updated_mod.name = new_name.clone();
            updated_mod.path = new_path;
            self.cached_mods.remove(&old_name);
            self.cached_mods.insert(new_name.clone(), updated_mod);

            self.metadata_store.rename(&old_name, &new_name);

            let all_mods: Vec<&BD2Mod> = self.cached_mods.values().collect();
            app_handle.emit("mods-changed", all_mods).unwrap();
            true
        } else {
            eprintln!("Mod not found for renaming: {}", old_name);
            false
        }
    }

    pub fn set_mod_author(
        &mut self,
        app_handle: &AppHandle,
        mod_names: Vec<String>,
        author: Option<String>,
    ) {
        self.metadata_store.set_authors(&mod_names, author.clone());

        for mod_name in &mod_names {
            if let Some(mod_info) = self.cached_mods.get_mut(mod_name) {
                mod_info.author = author.clone();
            }
        }

        let all_mods: Vec<&BD2Mod> = self.cached_mods.values().collect();
        app_handle.emit("mods-changed", all_mods).unwrap();
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
    }

    fn sync_mods_with_profile(&mut self) {
        if let Some(active_profile) = self.profile_manager.get_active_profile() {
            info!("Active profile ({:?})", active_profile);

            for bd2mod in self.cached_mods.values_mut() {
                bd2mod.enabled = active_profile.get_mod_state(&bd2mod.name);
            }
        } else {
            warn!("No active profile found.");
            // reset all mods to disabled if no active profile is found, just in case
            for bd2mod in self.cached_mods.values_mut() {
                bd2mod.enabled = false;
            }
        }
    }
}
