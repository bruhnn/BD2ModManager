use std::{env, path::{PathBuf}};

use tauri::{path::BaseDirectory, AppHandle, Manager};

use crate::config::BD2Config;

fn get_executable_dir() -> PathBuf {
    env::current_exe()
        .expect("Failed to get the current exe path")
        .parent()
        .unwrap()
        .to_path_buf()
}

pub fn get_default_profiles_dir(app: &AppHandle, on_executable_dir: bool) -> PathBuf {
    // receives (on_executable_dir: bool), if true then return executable_dir/profiles, if not appdata/profiles

    if on_executable_dir {
        let exec_dir = get_executable_dir();
        exec_dir
    } else {
        match app
            .app_handle()
            .path()
            .resolve("profiles", BaseDirectory::AppData)
        {
            Ok(path) => path,
            Err(_error) => {
                let exec_dir = get_executable_dir();
                exec_dir
            }
        }
    }
}

// same as "identifier" in tauri.conf.json
#[cfg(not(windows))]
const APP_IDENTIFIER: &str = "com.bruhnn.BD2ModManager";

#[cfg(not(windows))]
fn home_dir() -> PathBuf {
    env::var_os("HOME").map(PathBuf::from).unwrap_or_else(get_executable_dir)
}

// Windows keeps config.json next to the exe. On Linux the exe folder is read-only
// (AppImage mount, /usr/bin), so it goes in ~/.config/<identifier> like Tauri's app_config_dir
pub fn get_config_file_path() -> PathBuf {
    #[cfg(windows)]
    {
        get_executable_dir().join("config.json")
    }
    #[cfg(not(windows))]
    {
        let config_dir = env::var_os("XDG_CONFIG_HOME")
            .filter(|dir| !dir.is_empty())
            .map(PathBuf::from)
            .unwrap_or_else(|| home_dir().join(".config"));
        config_dir.join(APP_IDENTIFIER).join("config.json")
    }
}

// Windows: mods/ next to the exe. Linux: a visible folder in the home directory,
// like other Linux mod managers (~/Games/<manager>)
pub fn get_default_staging_dir() -> PathBuf {
    #[cfg(windows)]
    {
        get_executable_dir().join("mods")
    }
    #[cfg(not(windows))]
    {
        home_dir().join("Games").join("BD2ModManager").join("mods")
    }
}

// BepInEx/plugins/BrownDustX of the game, only when "use game folder as staging" is on
pub fn get_game_folder_base(config: &BD2Config) -> Option<PathBuf> {
    if !config.use_game_folder_as_staging {
        return None;
    }
    get_game_dir(config).map(|game_dir| game_dir.join("BepInEx/plugins/BrownDustX"))
}

pub fn get_staging_dir(config: &BD2Config) -> PathBuf {
    // with the game folder as staging, enabled mods live in BrownDustX/mods
    if let Some(base) = get_game_folder_base(config) {
        return base.join("mods");
    }
    match &config.staging_directory {
        Some(path) => return PathBuf::from(path),
        None => return get_default_staging_dir(),
    }
}

pub fn get_game_dir(config: &BD2Config) -> Option<PathBuf> {
    match &config.game_directory {
        Some(path) => return Some(PathBuf::from(path)),
        None => None,
    }
}

#[cfg(windows)]
pub const MOD_PREVIEW_FILE: &str = "BD2ModPreview.exe";
#[cfg(not(windows))]
pub const MOD_PREVIEW_FILE: &str = "BD2ModPreview.AppImage";

pub fn get_tools_dir(app: &AppHandle) -> Option<PathBuf> {
    app.path().resolve("tools", BaseDirectory::AppData).ok()
}

pub fn get_mod_preview_path(app: &AppHandle) -> Option<PathBuf> {
    get_tools_dir(app).map(|path| path.join(MOD_PREVIEW_FILE))
}

pub fn get_characters_path(app_handle: &AppHandle) -> Option<PathBuf> {
    app_handle
    .path()
    .app_data_dir()
    .ok()
    .map(|dir| dir.join("characters.json"))
}
