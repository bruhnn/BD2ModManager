use std::sync::{Arc, Mutex};
use std::{collections::HashMap, path::PathBuf};

pub mod config;
pub mod game;
pub mod mods;
pub mod profiles;
pub mod utils;
pub mod updater;
pub mod migrate;

use log::{debug, error, info, warn};
use percent_encoding::percent_decode_str;
use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager, http};

mod state;
pub use state::AppState;

use crate::config::{BD2Config, PartialAppConfig};
use crate::mods::delete::ModDeleteError;
use crate::mods::install::ModInstallError;
use crate::mods::metadata::{MetadataError, ModMetadataStore};
use crate::mods::preview::PreviewError;
use crate::mods::sync::{ModSyncError, SyncMethod};
use crate::mods::BD2Mod;
use crate::profiles::types::{Profile, ProfileError};
use crate::profiles::ProfileManager;
use crate::state::BundledAssets;
use crate::updater::commands::PendingUpdate;
use crate::utils::data;
use crate::utils::files::ensure_dir_exists;
use crate::utils::logs::rotate_logs;
use crate::utils::misc::get_game_asset;
use crate::utils::path::{get_default_profiles_dir, get_default_staging_dir};

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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let context: tauri::Context = tauri::generate_context!();
    let bundle_id = context.config().identifier.clone();
    if let Some(data_dir) = dirs::data_local_dir() {
        let logs_dir = data_dir.join(&bundle_id).join("logs");
        rotate_logs(&logs_dir);
    }

    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            let _ = app.get_webview_window("main")
            .expect("no main window")
            .set_focus();
        }))
        .register_uri_scheme_protocol("bd2assets", |ctx, request| {
            // standing/065001,065002
            // standing/065001
            // heads/065002
            let uri_path = percent_decode_str(request.uri().path())
                .decode_utf8_lossy()
                .trim_start_matches('/')
                .to_string();

            // println!("{:?}", uri_path);

            let parts: Vec<&str> = uri_path.splitn(2, '/').collect();

            let category = parts.get(0).copied().unwrap_or("standing");
            let ids_raw = parts.get(1).copied().unwrap_or("");
            let ids: Vec<&str> = ids_raw.split(',').collect();

            if let Some(bytes) = get_game_asset(ctx.app_handle(), &ids, category) {
                http::Response::builder()
                    .header("Content-Type", "image/png")
                    .header("Access-Control-Allow-Origin", "http://tauri.localhost")
                    .header("Cache-Control", "public, max-age=604800") // 7 days cache
                    .body(bytes)
                    .unwrap()
            } else {
                // 404
                http::Response::builder()
                .status(404)
                 .body(format!("missing character asset: {:?}", ids).into_bytes())
                .unwrap()
            }
        })
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_os::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_store::Builder::new().build())
        .plugin(tauri_plugin_window_state::Builder::new().build())
        .plugin(
            tauri_plugin_log::Builder::new()
                .clear_targets()
                .targets([
                    tauri_plugin_log::Target::new(tauri_plugin_log::TargetKind::Stdout),
                    tauri_plugin_log::Target::new(tauri_plugin_log::TargetKind::LogDir {
                        file_name: Some("logs".to_string()),
                    }),
                ])
                .filter(|metadata| {
                    !(cfg!(debug_assertions)
                        && metadata.target() == "reqwest::connect"
                        && metadata.level() <= log::Level::Debug)
                })
                .max_file_size(10_000_000) // 10mb
                .level(log::LevelFilter::Debug)
                .build(),
        )
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            log::info!("Starting app...");

            let app_handle = app.app_handle();

            let mut config = BD2Config::new(app_handle.clone());
            config.load_config();

            let profiles_dir: PathBuf = get_default_profiles_dir(app_handle, false);
            // let temp_dir = get_temp_dir();

            let staging_dir = match &config.staging_directory {
                Some(path) => PathBuf::from(path),
                None => {
                    let staging_dir = get_default_staging_dir();

                    config
                        .update_config(PartialAppConfig {
                            staging_directory: Some(staging_dir.to_string_lossy().to_string()),
                            ..Default::default()
                        })
                        .expect("Failed to update config with default staging directory");

                    staging_dir
                }
            };

            // ensure_dir_exists(&temp_dir).expect("Failed to create temp directory");
            ensure_dir_exists(&profiles_dir).expect("Failed to get profiles dir");
            ensure_dir_exists(&staging_dir).expect("Failed to create mods directory");

            let profile_manager: ProfileManager = ProfileManager::new(profiles_dir);

            let metadata_path = app_handle
                .path()
                .app_data_dir()
                .expect("Failed to resolve AppData dir")
                .join("mod_metadata.json");
            let metadata_store = ModMetadataStore::new(metadata_path);

            let mut mod_manager: BD2ModManager =
                BD2ModManager::new(profile_manager, metadata_store);

            mod_manager
                .load_profiles()
                .expect("failed to load profiles");

            let app_state: AppState = AppState {
                mod_manager: Arc::new(Mutex::new(mod_manager)),
                config: Arc::new(Mutex::new(config)),
            };

            let bundled_assets: std::collections::HashSet<String> = app
                .asset_resolver()
                .iter()
                .map(|(path, _)| path.to_string())
                .collect();

            app.manage(app_state);
            app.manage(PendingUpdate(std::sync::Mutex::new(None)));
            app.manage(BundledAssets(bundled_assets));

            // move data to appdata
            data::move_data_to_appdata(&app_handle).expect("Failed to move data to appdata");

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            // mods
            mods::commands::discover_mods,
            mods::commands::get_mods,
            mods::commands::enable_mods,
            mods::commands::disable_mods,
            mods::commands::delete_mods,
            mods::commands::rename_mod,
            mods::commands::set_mod_author,
            mods::commands::install_mod_from_zip,
            mods::commands::install_mod_from_folder,
            mods::commands::sync_mods,
            mods::commands::unsync_mods,
            mods::commands::is_sync_needed,
            mods::commands::preview_mod,
            // profiles
            profiles::commands::get_profiles,
            profiles::commands::switch_profile,
            profiles::commands::edit_profile,
            profiles::commands::create_profile,
            profiles::commands::delete_profile,
            // config
            config::commands::get_settings,
            config::commands::set_settings,
            // game
            game::commands::locate_game,
            game::commands::validate_game_path,
            game::commands::launch_game,
            game::commands::get_game_version,
            game::commands::get_browndustx_version,
            game::commands::get_bepinex_version,
            game::commands::get_configmanager_version,
            game::commands::install_bepinex,
            game::commands::install_browndustx,
            game::commands::install_configmanager,
            game::commands::uninstall_bepinex,
            game::commands::uninstall_browndustx,
            game::commands::uninstall_configmanager,
            game::commands::determine_archive_type,
            game::commands::get_characters,
            // updater
            updater::commands::get_mod_preview_version,
            updater::commands::check_for_app_update,
            #[cfg(not(feature = "portable"))]
            updater::commands::install_app_update,
            updater::commands::check_for_mod_preview_update,
            updater::commands::update_mod_preview,
            updater::commands::update_game_data,
            // migration
            migrate::commands::get_legacy_profiles,
            migrate::commands::import_legacy_profiles,
            migrate::commands::import_legacy_mod_authors,
            // utils
            utils::commands::is_folder,
            utils::commands::path_exists,
            utils::commands::is_portable,
            utils::commands::get_user_locale,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}