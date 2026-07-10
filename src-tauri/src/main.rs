// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{
    env,
    path::PathBuf,
    sync::{Arc, Mutex},
};

use bd2modmanager_lib::{
    config::{config::PartialAppConfig, BD2Config},
    mods::metadata::ModMetadataStore,
    profiles::ProfileManager,
    utils::{
        data,
        files::ensure_dir_exists,
        path::{get_default_profiles_dir, get_default_staging_dir},
    },
    BD2ModManager,
};
use log::debug;
use tauri::{AppHandle, Manager, http};

mod commands;
use commands::*;

use crate::commands::updater::PendingUpdate;

mod migrate;
mod update;

use percent_encoding::percent_decode_str;
use reqwest;

struct BundledAssets(std::collections::HashSet<String>);

pub struct AppState {
    pub mod_manager: Arc<Mutex<BD2ModManager>>,
    pub config: Arc<Mutex<BD2Config>>,
}

fn rotate_logs(logs_dir: &PathBuf) {
    if !logs_dir.exists() {
        return;
    }

    // this function will only keep2 logs; will move logs.log to logs-<timestamp>.log, and delete the previous logs-<timestamp>.log if it exists

    let log_file = logs_dir.join("logs.log");
    if !log_file.exists() {
        return;
    }

    let timestamp = std::fs::metadata(&log_file)
        .and_then(|m| m.modified())
        .map(|t| {
            let dt: chrono::DateTime<chrono::Local> = t.into();
            dt.format("%Y-%m-%d_%H-%M-%S").to_string()
        })
        .unwrap_or_else(|_| chrono::Local::now().format("%Y-%m-%d_%H-%M-%S").to_string());

    let rotated_log_file = logs_dir.join(format!("logs-{}.log", timestamp));
    if let Err(e) = std::fs::rename(&log_file, &rotated_log_file) {
        eprintln!("Failed to rename log file: {e}");
        return;
    }

    let entries = match std::fs::read_dir(logs_dir) {
        Ok(e) => e,
        Err(e) => { eprintln!("Failed to read logs dir: {e}"); return; }
    };

    let old_logs: Vec<_> = entries
        .filter_map(|entry| {
            let entry = entry.ok()?;
            let file_name = entry.file_name().into_string().ok()?;
            if file_name.starts_with("logs-")
                && file_name.ends_with(".log")
                && entry.path() != rotated_log_file
            {
                Some(entry.path())
            } else {
                None
            }
        })
        .collect();

    for old_log in old_logs {
        if let Err(e) = std::fs::remove_file(&old_log) {
            eprintln!("Failed to remove old log file: {e}");
        }
    }
}

fn get_game_asset(app_handle: &AppHandle, character_ids: &[&str], category: &str) -> Option<Vec<u8>> {
    #[cfg(not(debug_assertions))]
    {
        let bundled_assets = app_handle.state::<BundledAssets>();
    
        for id in character_ids {
            let path = format!("/characters/{}/{}.png", category, id);
            // debug!("Trying bundled asset: {}", path);
            if bundled_assets.0.contains(&path) {
                // debug!("Found bundled asset: {}", path);
                if let Some(asset) = app_handle.asset_resolver().get(path.clone()) {
                    return Some(asset.bytes.to_vec());
                }
            }
        }
    
        debug!("Assets for character id {:?} not found bundled", character_ids);
    }

    if let Ok(app_data) = app_handle.path().app_data_dir() {
        for id in character_ids {
            let appdata_asset_path = app_data.join("assets").join(category).join(format!("{}.png", id));
            // debug!("Trying appdata path: {:?}", appdata_asset_path);
            if let Ok(bytes) = std::fs::read(&appdata_asset_path) {
                debug!("Found asset on appdata: {:?}", appdata_asset_path);
                return Some(bytes);
            }
        }
    }

    #[cfg(debug_assertions)]
    for id in character_ids {
        let url = format!("http://localhost:1420/characters/{}/{}.png", category, id);
        if let Ok(resp) = reqwest::blocking::get(&url) {
            if resp.status().is_success() {
                if let Ok(bytes) = resp.bytes() {
                    // debug!("Found asset on dev server: {}", url);
                    return Some(bytes.to_vec());
                }
            }
        }
    }

    debug!("Assets not found for characters {:?}", character_ids);

    None
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn main() {
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
            mods::discover_mods,
            mods::get_mods,
            mods::enable_mods,
            mods::disable_mods,
            mods::delete_mods,
            mods::rename_mod,
            mods::set_mod_author,
            mods::install_mod_from_zip,
            mods::install_mod_from_folder,
            mods::sync_mods,
            mods::unsync_mods,
            mods::is_sync_needed,
            mods::preview_mod,
            // profiles
            profiles::get_profiles,
            profiles::switch_profile,
            profiles::edit_profile,
            profiles::create_profile,
            profiles::delete_profile,
            // config
            config::get_settings,
            config::set_settings,
            // game
            game::locate_game,
            game::validate_game_path,
            game::launch_game,
            game::get_game_version,
            game::get_browndustx_version,
            game::get_bepinex_version,
            game::get_configmanager_version,
            game::install_bepinex,
            game::install_browndustx,
            game::install_configmanager,
            game::uninstall_bepinex,
            game::uninstall_browndustx,
            game::uninstall_configmanager,
            game::determine_archive_type,
            game::get_characters,
            game::get_dating,
            // updater
            updater::get_mod_preview_version,
            updater::check_for_app_update,
            #[cfg(not(feature = "portable"))]
            updater::install_app_update,
            updater::check_for_mod_preview_update,
            updater::update_mod_preview,
            updater::update_game_data,
            // migration
            commands::migrate::get_legacy_profiles,
            commands::migrate::import_legacy_profiles,
            commands::migrate::import_legacy_mod_authors,
            // utils
            utils::is_folder,
            utils::path_exists,
            utils::is_portable,
            utils::get_user_locale,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
