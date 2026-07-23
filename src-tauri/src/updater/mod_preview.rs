use crate::utils::path::get_mod_preview_path;
use pelite::{FileMap, PeFile};
use semver::Version;
use serde::Deserialize;

#[derive(Debug, Deserialize)]
struct GitHubRelease {
    tag_name: String,
    assets: Vec<GitHubAsset>,
}

#[derive(Debug, Deserialize)]
struct GitHubAsset {
    name: String,
    browser_download_url: String,
}

const RELEASES_URL: &str = "https://api.github.com/repos/bruhnn/BD2ModPreview/releases/latest";

pub fn get_mod_preview_version(app_handle: tauri::AppHandle) -> Option<String> {
    let exe_path = get_mod_preview_path(&app_handle)?;

    if !exe_path.exists() {
        log::warn!("Mod preview executable not found at {:?}", exe_path);
        return None;
    }

    let file_map = FileMap::open(&exe_path).ok()?;
    let pe = PeFile::from_bytes(&file_map).ok()?;
    let resources = pe.resources().ok()?;
    let version_info = resources.version_info().ok()?;

    let file_info = version_info.file_info();
    for (_lang, strings) in file_info.strings {
        for (key, value) in strings {
            if key == "FileVersion" || key == "ProductVersion" {
                return Some(value.to_string());
            }
        }
    }

    log::warn!("Version not found in mod preview executable at {:?}", exe_path);
    None
}

async fn get_latest_mod_preview_version() -> Result<(Version, String), String> {
    let client = reqwest::Client::new();

    let release: GitHubRelease = client
        .get(RELEASES_URL)
        .header("User-Agent", "BD2ModManager")
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await
        .map_err(|e| format!("Request failed: {e}"))?
        .json()
        .await
        .map_err(|e| format!("Invalid JSON: {e}"))?;

    let latest_version = release.tag_name.trim_start_matches('v');

    let asset = release
        .assets
        .iter()
        .find(|a| a.name == "BD2ModPreview.exe")
        .ok_or("BD2ModPreview.exe not found in release")?;

    let version =
        Version::parse(latest_version).map_err(|e| format!("Invalid remote version: {e}"))?;

    Ok((version, asset.browser_download_url.clone()))
}

pub async fn check_for_update(
    app_handle: tauri::AppHandle,
) -> Result<(Option<String>, Option<String>), String> {
    let local_version = get_mod_preview_version(app_handle.clone());
    let (latest_version, download_url) = get_latest_mod_preview_version().await?;

    log::info!(
        "Mod preview update check; local: {}, latest: {}",
        local_version.as_deref().unwrap_or("not installed"),
        latest_version
    );

    if let Some(local) = local_version {
        let local_ver =
            Version::parse(&local).map_err(|e| format!("Invalid local version: {e}"))?;

        if latest_version <= local_ver {
            log::info!("Mod preview is up to date");
            return Ok((None, None));
        }
    }

    log::info!("Mod preview update available: {}", latest_version);
    
    Ok((Some(latest_version.to_string()), Some(download_url)))
}