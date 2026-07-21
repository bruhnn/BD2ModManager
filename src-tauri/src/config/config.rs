use log::info;
use serde::{Deserialize, Serialize};
use tauri::AppHandle;
use tauri_plugin_store::StoreExt;

use crate::utils::path::get_config_file_path;

#[derive(Serialize, Deserialize, Debug, Clone)]
#[serde(rename_all = "camelCase", default)]
pub struct AppConfig {
    pub game_directory: Option<String>,
    pub staging_directory: Option<String>,
    pub language: String,
    pub theme: String,
    pub sync_method: String,
    pub search_mods_recursively: bool,
    pub auto_sync_mods: bool,
    pub check_for_app_updates: bool,
    pub auto_download_game_data: bool,
    pub auto_update_mod_preview: bool,
    pub manifest_url: String,
    pub releases_url: String,
    pub skip_update_version: Option<String>,
    pub is_first_launch: bool,
    // Persisted mod filter state — restored every time the app starts
    pub mod_filter_only_enabled: bool,
    pub mod_filter_only_disabled: bool,
    pub mod_filter_only_conflicts: bool,
    pub mod_filter_only_errors: bool,
    pub mod_filter_hide_errors: bool,
    pub mod_filter_types: Vec<String>,
}

#[derive(Deserialize, Serialize, Debug, Clone)]
#[serde(rename_all = "camelCase", default)]
pub struct PartialAppConfig {
    pub game_directory: Option<String>,
    pub staging_directory: Option<String>,
    pub language: Option<String>,
    pub theme: Option<String>,
    pub sync_method: Option<String>,
    pub search_mods_recursively: Option<bool>,
    pub check_for_app_updates: Option<bool>,
    pub auto_download_game_data: Option<bool>,
    pub auto_update_mod_preview: Option<bool>,
    pub manifest_url: Option<String>,
    pub releases_url: Option<String>,
    pub skip_update_version: Option<String>,
    pub auto_sync_mods: Option<bool>,
    pub is_first_launch: Option<bool>,
    pub mod_filter_only_enabled: Option<bool>,
    pub mod_filter_only_disabled: Option<bool>,
    pub mod_filter_only_conflicts: Option<bool>,
    pub mod_filter_only_errors: Option<bool>,
    pub mod_filter_hide_errors: Option<bool>,
    pub mod_filter_types: Option<Vec<String>>,
}

impl AppConfig {
    pub fn merge_from(&mut self, partial: PartialAppConfig) {
        if let Some(game_directory) = partial.game_directory {
            self.game_directory = Some(game_directory);
        }
        if let Some(staging_directory) = partial.staging_directory {
            self.staging_directory = Some(staging_directory);
        }
        if let Some(language) = partial.language {
            self.language = language;
        }
        if let Some(theme) = partial.theme {
            self.theme = theme;
        }
        if let Some(sync_method) = partial.sync_method {
            self.sync_method = sync_method;
        }
        if let Some(search_mods_recursively) = partial.search_mods_recursively {
            self.search_mods_recursively = search_mods_recursively;
        }
        if let Some(check_for_app_updates) = partial.check_for_app_updates {
            self.check_for_app_updates = check_for_app_updates;
        }
        if let Some(auto_download_game_data) = partial.auto_download_game_data {
            self.auto_download_game_data = auto_download_game_data;
        }
        if let Some(auto_update_mod_preview) = partial.auto_update_mod_preview {
            self.auto_update_mod_preview = auto_update_mod_preview;
        }
        if let Some(manifest_url) = partial.manifest_url {
            self.manifest_url = manifest_url;
        }
        if let Some(releases_url) = partial.releases_url {
            self.releases_url = releases_url;
        }
        if let Some(skip_update_version) = partial.skip_update_version {
            self.skip_update_version = Some(skip_update_version);
        }
        if let Some(auto_sync_mods) = partial.auto_sync_mods {
            self.auto_sync_mods = auto_sync_mods;
        }
        if let Some(is_first_launch) = partial.is_first_launch {
            self.is_first_launch = is_first_launch;
        }
        if let Some(v) = partial.mod_filter_only_enabled {
            self.mod_filter_only_enabled = v;
        }
        if let Some(v) = partial.mod_filter_only_disabled {
            self.mod_filter_only_disabled = v;
        }
        if let Some(v) = partial.mod_filter_only_conflicts {
            self.mod_filter_only_conflicts = v;
        }
        if let Some(v) = partial.mod_filter_only_errors {
            self.mod_filter_only_errors = v;
        }
        if let Some(v) = partial.mod_filter_hide_errors {
            self.mod_filter_hide_errors = v;
        }
        if let Some(v) = partial.mod_filter_types {
            self.mod_filter_types = v;
        }
    }
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            game_directory: None,
            staging_directory: None,
            language: "en_US".into(),
            theme: "dark".into(),
            sync_method: "copy".into(),
            search_mods_recursively: false,
            check_for_app_updates: true,
            auto_download_game_data: true,
            auto_update_mod_preview: true,
            manifest_url: "https://raw.githubusercontent.com/bruhnn/BD2ModManager/refs/heads/main/src/manifest_v2.json".into(),
            releases_url: "https://api.github.com/repos/bruhnn/BD2ModManager/releases".into(),
            skip_update_version: None,
            auto_sync_mods: false,
            is_first_launch: true,
            mod_filter_only_enabled: false,
            mod_filter_only_disabled: false,
            mod_filter_only_conflicts: false,
            mod_filter_only_errors: false,
            mod_filter_hide_errors: false,
            mod_filter_types: vec![],
        }
    }
}

impl Default for PartialAppConfig {
    fn default() -> Self {
        Self {
            game_directory: None,
            staging_directory: None,
            language: None,
            theme: None,
            sync_method: None,
            search_mods_recursively: None,
            check_for_app_updates: None,
            auto_download_game_data: None,
            auto_update_mod_preview: None,
            manifest_url: None,
            releases_url: None,
            skip_update_version: None,
            auto_sync_mods: None,
            is_first_launch: None,
            mod_filter_only_enabled: None,
            mod_filter_only_disabled: None,
            mod_filter_only_conflicts: None,
            mod_filter_only_errors: None,
            mod_filter_hide_errors: None,
            mod_filter_types: None,
        }
    }
}

#[derive(Clone)]
pub struct BD2Config {
    app: AppHandle,
    config: AppConfig,
}

impl BD2Config {
    pub fn new(app: AppHandle) -> Self {
        Self {
            app,
            config: AppConfig::default(),
        }
    }

    pub fn load_config(&mut self) {
        let config_path = get_config_file_path();

        info!("loading config from {:?}", config_path);

        if let Ok(store) = self.app.store(config_path) {
            if let Some(config_value) = store.get("config") {
                if let Ok(config) = serde_json::from_value(config_value) {
                    self.config = config;
                    return;
                }
            }
        }

        self.config = AppConfig::default();
    }

    pub fn get_config(&self) -> &AppConfig {
        &self.config
    }

    pub fn save_config(&self) -> Result<(), Box<dyn std::error::Error>> {
        let config_path = get_config_file_path();
        println!("saving config {:?}", config_path);
        let store = self.app.store(config_path)?;

        store.set("config", serde_json::to_value(&self.config)?);
        store.save()?;

        Ok(())
    }

    pub fn update_config(
        &mut self,
        new_config: PartialAppConfig,
    ) -> Result<(), Box<dyn std::error::Error>> {
        self.config.merge_from(new_config);
        self.save_config()?;
        Ok(())
    }
}

use std::ops::{Deref, DerefMut};

impl Deref for BD2Config {
    type Target = AppConfig;
    fn deref(&self) -> &Self::Target {
        &self.config
    }
}

impl DerefMut for BD2Config {
    fn deref_mut(&mut self) -> &mut Self::Target {
        &mut self.config
    }
}
