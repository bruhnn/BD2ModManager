use std::path::PathBuf;
use log::debug;
use pelite::pe32::Pe;
use pelite::FileMap;
use tauri::{AppHandle, Manager};
#[cfg(target_os = "windows")]
use windows_sys::Win32::Foundation::CloseHandle;
#[cfg(target_os = "windows")]
use windows_sys::Win32::Security::{
    GetTokenInformation, TokenElevation, TOKEN_ELEVATION, TOKEN_QUERY,
};
#[cfg(target_os = "windows")]
use windows_sys::Win32::System::Threading::{GetCurrentProcess, OpenProcessToken};

#[cfg(not(target_os = "windows"))]
use libc;

pub fn is_admin() -> bool {
    #[cfg(target_os = "windows")]
    {
        unsafe {
            let process = GetCurrentProcess();
            let mut token = std::ptr::null_mut();

            if OpenProcessToken(process, TOKEN_QUERY, &mut token) != 0 {
                let mut elevation: TOKEN_ELEVATION = TOKEN_ELEVATION { TokenIsElevated: 0 };
                let mut return_length: u32 = 0;

                let result = GetTokenInformation(
                    token,
                    TokenElevation,
                    &mut elevation as *mut TOKEN_ELEVATION as *mut _,
                    std::mem::size_of::<TOKEN_ELEVATION>() as u32,
                    &mut return_length,
                ) != 0;

                CloseHandle(token);

                if result {
                    return elevation.TokenIsElevated != 0;
                }
            }
        }

        return false;
    }

    #[cfg(not(target_os = "windows"))]
    {
        return unsafe { libc::geteuid() == 0 };
    }
}

pub fn can_create_symlink() -> bool {
    if is_admin() {
        return true;
    }

    let tdir = std::env::temp_dir();
    let file_a = tdir.join(".bd2mm.test.1");
    let file_b = tdir.join(".bd2mm.test.2");

    let _ = std::fs::remove_file(&file_a);
    let _ = std::fs::remove_file(&file_b);

    let result = {
        #[cfg(target_os = "windows")]
        {
            std::os::windows::fs::symlink_file(&file_a, &file_b)
        }
        #[cfg(not(target_os = "windows"))]
        {
            std::os::unix::fs::symlink(&file_b, &file_a)
        }
    };

    let _ = std::fs::remove_file(&file_a);
    let _ = std::fs::remove_file(&file_b);

    result.is_ok()
}

pub fn get_dll_version(dll_path: &PathBuf) -> Option<String> {
    if !dll_path.exists() {
        return None;
    }

    let file_map = FileMap::open(dll_path).ok()?;
    let pe = pelite::pe32::PeFile::from_bytes(&file_map).ok()?;
    let resources = pe.resources().ok()?;
    let version_info = resources.version_info().ok()?;
    let file_info = version_info.file_info();

    for (_lang, strings) in file_info.strings {
        for (key, value) in strings {
            if key == "FileVersion" {
                return Some(value.to_string());
            }
        }
    }

    None
}

pub fn compare_versions(first: &str, second: &str) -> std::cmp::Ordering {
    let first_parts: Vec<u64> = first
        .split('.')
        .filter_map(|part| part.parse().ok())
        .collect();
    let second_parts: Vec<u64> = second
        .split('.')
        .filter_map(|part| part.parse().ok())
        .collect();

    for index in 0..first_parts.len().max(second_parts.len()) {
        let first_compnent = first_parts.get(index).copied().unwrap_or(0);
        let second_component = second_parts.get(index).copied().unwrap_or(0);

        match first_compnent.cmp(&second_component) {
            std::cmp::Ordering::Equal => continue,
            ordering => return ordering,
        }
    }

    std::cmp::Ordering::Equal
}

pub fn get_game_asset(app_handle: &AppHandle, character_ids: &[&str], category: &str) -> Option<Vec<u8>> {
    #[cfg(not(debug_assertions))]
    {
        use crate::state::BundledAssets;

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


