use std::{collections::HashMap, path::PathBuf};
use log::{info, error, warn, debug};
use tauri::{AppHandle, Emitter};

use crate::{mods::{self, BD2Mod, delete::ModDeleteError, install::ModInstallError, metadata::{MetadataError, ModMetadataStore}, rename::ModRenameError, sync::{ModSyncError, SyncMethod, SyncResult}, types::BD2ModError}, profiles::{ProfileManager, types::{Profile, ProfileError}}};

pub struct BD2ModManager {
    pub profile_manager: ProfileManager,
    pub cached_mods: HashMap<String, BD2Mod>,
    pub metadata_store: ModMetadataStore,
    discovery_failed: bool,
}

impl BD2ModManager {
    pub fn new(profile_manager: ProfileManager, metadata_store: ModMetadataStore) -> Self {
        Self {
            profile_manager,
            cached_mods: HashMap::new(),
            metadata_store,
            discovery_failed: true,
        }
    }

    pub fn discover_mods(
        &mut self,
        staging_dir: &PathBuf,
        game_dir: &Option<PathBuf>,
        recursive: bool,
    ) -> std::io::Result<Vec<BD2Mod>> {
        info!(
            "Searching for mods on staging directory ({:?})",
            staging_dir
        );

        // keep the cached list if staging cannot be read
        self.discovery_failed = true;
        let mut mods_found = mods::discover::discover_staging_mods(staging_dir, recursive)?;
        let unmanaged_mods = if let Some(game_dir) = game_dir {
            mods::discover::discover_unmanaged_mods(game_dir, &mut mods_found)
        } else {
            vec![]
        };


        self.cached_mods.clear();

        for _mod in mods_found {
            self.cached_mods.insert(_mod.name.clone(), _mod);
        }

        for _mod in unmanaged_mods {
            self.cached_mods.insert(_mod.name.clone(), _mod);
        }

        // detect if mods edits the same files (mod type + mod id)
        mods::conflict::detect_conflicts(&mut self.cached_mods);

        // apply stored metadata (author, etc.)
        self.metadata_store.apply_to_mods(&mut self.cached_mods);

        // set mods enabled states with the active proifle
        self.sync_mods_with_profiles();

        self.discovery_failed = false;
        Ok(self.get_mods())
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

    fn change_mods_state(&mut self, mod_names: Vec<String>, enabled: bool) -> Vec<BD2Mod> {
        let mut mods_changed: Vec<BD2Mod> = vec![];

        for mod_name in mod_names.iter() {
            if let Some(bd2mod) = self.cached_mods.get_mut(mod_name) {
                bd2mod.enabled = enabled;
                
                debug!(
                    "{} mod: {}",
                    if enabled { "Enabled" } else { "Disabled" },
                    bd2mod.name
                );

                mods_changed.push(bd2mod.clone());
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

        mods_changed
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
        self.change_mods_state(mod_names, true)
    }

    pub fn disable_mods(&mut self, mod_names: Vec<String>) -> Vec<BD2Mod> {
        self.change_mods_state(mod_names, false)
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

        let (is_mod, error) = mods::discover::analyze_mod_path(&mod_path)?;
        if is_mod {
            let mut new_mod = mods::discover::create_mod(staging_dir, &mod_path, error);
            let mod_name = new_mod.name.clone();
            self.cached_mods.insert(mod_name.clone(), new_mod.clone());
            mods::conflict::detect_conflicts(&mut self.cached_mods);
            self.metadata_store.apply_to_mod(&mut new_mod);
            self.sync_mods_with_profiles();
            Ok(new_mod)
        } else {
            Err(ModInstallError::NotAMod {
                path: mod_path.to_string_lossy().to_string(),
            })
        }
    }

    pub fn sync_mods(
        &mut self,
        app_handle: &AppHandle,
        game_directory: &PathBuf,
        staging_directory: &PathBuf,
        method: SyncMethod,
        remove_unmanaged_mods: bool,
    ) -> Result<SyncResult, ModSyncError> {
        if self.discovery_failed {
            return Err(std::io::Error::other("Staging discovery failed. Refresh mods before syncing.").into());
        }

        let mods: Vec<&BD2Mod> = self
        .cached_mods
        .values()
        // remove unmanaged mods from the list
        .filter(|mod_entry| !mod_entry.errors.contains(&BD2ModError::Unmanaged))
        .collect();

        mods::sync::sync_mods(app_handle, game_directory, staging_directory, mods, method, remove_unmanaged_mods)
    }

    pub fn unsync_mods(
        &mut self,
        app_handle: &AppHandle,
        game_directory: &PathBuf,
        staging_directory: &PathBuf,
        remove_unmanaged_mods: bool
    ) -> Result<SyncResult, ModSyncError> {
        // let mods: Vec<&BD2Mod> = self.cached_mods.values().collect();
        // [TODO] unsync all mods, or only the ones that are currently synced (in manifest)? 
        mods::sync::unsync_mods(app_handle, game_directory, staging_directory, remove_unmanaged_mods)
    }

    pub fn is_sync_needed(&self, game_directory: &PathBuf, staging_directory: &PathBuf, method: SyncMethod) -> bool {
        let mods: Vec<&BD2Mod> = self.cached_mods.values().collect();

        mods::sync::is_sync_needed(game_directory, staging_directory, method, mods)
    }

    pub fn delete_mod(&mut self, mod_name: String) -> Result<(), ModDeleteError> {
        let mod_ = self.get_mod_by_name(&mod_name).ok_or_else(|| ModDeleteError::ModNotFound {
            mod_name
        })?;

        mods::delete::delete_mod(&mod_)?;

        self.cached_mods.remove(&mod_.name);

        self.profile_manager.remove_mod_from_profiles(&mod_.name);

        if let Err(e) = self.metadata_store.remove_mod(&mod_.name) {
            warn!("Failed to remove metadata for deleted mod {}: {:?}", mod_.name, e);
        }
        Ok(())
    }

    pub fn rename_mod(
        &mut self,
        mod_name: String,
        new_name: String,
    ) -> Result<BD2Mod, ModRenameError> {
        let mod_: BD2Mod = self.get_mod_by_name(&mod_name).ok_or_else(|| ModRenameError::ModNotFound {
            mod_name: mod_name.clone()
        })?;

        let updated_mod = mods::rename::rename_mod(mod_, new_name.clone())?;

        self.cached_mods.remove(&mod_name);

        self.cached_mods.insert(updated_mod.name.clone(), updated_mod.clone());

        self.profile_manager.rename_mod_in_profiles(&mod_name, &updated_mod.name);

        if let Err(error) = self.metadata_store.rename_mod(&mod_name, &updated_mod.name) {
            warn!("Failed to rename metadata for mod {}: {:?}", updated_mod.name, error);
        }

        Ok(updated_mod)
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
