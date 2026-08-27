use crate::utils::path::get_mod_preview_path;
use pelite::{FileMap, PeFile};
use semver::Version;
use serde::{Deserialize, Serialize};

#[derive(Debug, thiserror::Error)]
pub enum ModPreviewUpdateError {
    #[error("failed to check for Mod Preview updates: {reason}")]
    CheckFailed { reason: String },
    #[error("BD2ModPreview.exe was not found in the latest release")]
    ReleaseFileNotFound,
    #[error("the Mod Preview installation path could not be found")]
    InstallationPathNotFound,
    #[error("failed to download Mod Preview: {reason}")]
    DownloadFailed { reason: String },
    #[error("failed to save Mod Preview to '{path}': {source}")]
    SaveFailed {
        path: String,
        #[source]
        source: std::io::Error,
    },
}

impl Serialize for ModPreviewUpdateError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        use serde::ser::SerializeStruct;
        use serde_json::json;

        let (type_, details) = match self {
            ModPreviewUpdateError::CheckFailed { reason } => {
                ("CheckFailed", Some(json!({ "reason": reason })))
            }
            ModPreviewUpdateError::ReleaseFileNotFound => ("ReleaseFileNotFound", None),
            ModPreviewUpdateError::InstallationPathNotFound => ("InstallationPathNotFound", None),
            ModPreviewUpdateError::DownloadFailed { reason } => {
                ("DownloadFailed", Some(json!({ "reason": reason })))
            }
            ModPreviewUpdateError::SaveFailed { path, source } => (
                "SaveFailed",
                Some(json!({
                    "path": path,
                    "kind": format!("{:?}", source.kind()),
                })),
            ),
        };

        let mut state = serializer.serialize_struct("ModPreviewUpdateError", 3)?;
        state.serialize_field("type", type_)?;
        state.serialize_field("details", &details)?;
        state.serialize_field("message", &self.to_string())?;
        state.end()
    }
}

pub struct ModPreviewUpdate {
    pub version: String,
    pub download_url: String,
}

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

    log::warn!(
        "Version not found in mod preview executable at {:?}",
        exe_path
    );
    None
}

async fn get_latest_mod_preview_version() -> Result<(Version, String), ModPreviewUpdateError> {
    let client = reqwest::Client::new();

    let release: GitHubRelease = client
        .get(RELEASES_URL)
        .header("User-Agent", "BD2ModManager")
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await
        .map_err(|e| ModPreviewUpdateError::CheckFailed {
            reason: format!("request failed: {e}"),
        })?
        .json()
        .await
        .map_err(|e| ModPreviewUpdateError::CheckFailed {
            reason: format!("invalid response: {e}"),
        })?;

    let latest_version = release.tag_name.trim_start_matches('v');

    let asset = release
        .assets
        .iter()
        .find(|a| a.name == "BD2ModPreview.exe")
        .ok_or(ModPreviewUpdateError::ReleaseFileNotFound)?;

    let version =
        Version::parse(latest_version).map_err(|e| ModPreviewUpdateError::CheckFailed {
            reason: format!("invalid remote version: {e}"),
        })?;

    Ok((version, asset.browser_download_url.clone()))
}

pub async fn check_for_update(
    app_handle: &tauri::AppHandle,
) -> Result<Option<ModPreviewUpdate>, ModPreviewUpdateError> {
    let local_version = get_mod_preview_version(app_handle.clone());
    let (latest_version, download_url) = get_latest_mod_preview_version().await?;

    log::info!(
        "Mod preview update check; local: {}, latest: {}",
        local_version.as_deref().unwrap_or("not installed"),
        latest_version
    );

    if let Some(local) = local_version {
        let local_ver = Version::parse(&local).map_err(|e| ModPreviewUpdateError::CheckFailed {
            reason: format!("invalid local version: {e}"),
        })?;

        if latest_version <= local_ver {
            log::info!("Mod preview is up to date");
            return Ok(None);
        }
    }

    log::info!("Mod preview update available: {}", latest_version);

    Ok(Some(ModPreviewUpdate {
        version: latest_version.to_string(),
        download_url,
    }))
}
