use std::sync::{Arc, Mutex};
use std::path::PathBuf;
use percent_encoding::percent_decode_str;
use tauri::{Manager, http};

mod state;

pub mod manager;
pub mod config;
pub mod game;
pub mod mods;
pub mod profiles;
pub mod utils;
pub mod updater;
pub mod migrate;
pub mod errors;

pub use state::AppState;

use crate::manager::BD2ModManager;
use crate::config::{BD2Config, PartialAppConfig};
use crate::mods::metadata::{ModMetadataStore};
use crate::profiles::ProfileManager;
use crate::state::BundledAssets;
use crate::updater::commands::PendingUpdate;
use crate::utils::data;
use crate::utils::files::ensure_dir_exists;
use crate::utils::logs::rotate_logs;
use crate::utils::misc::get_game_asset;
use crate::utils::path::{get_default_profiles_dir, get_default_staging_dir};


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
            updater::commands::download_app_update,
            #[cfg(not(feature = "portable"))]
            updater::commands::install_app_update,
            updater::commands::check_for_mod_preview_update,
            updater::commands::download_mod_preview,
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
