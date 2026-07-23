use crate::{updater, utils::path::get_mod_preview_path};
use log::{debug, info};
use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use tauri::{AppHandle, Emitter, State};
use tauri_plugin_updater::{Update};
use tokio::io::AsyncWriteExt;

#[cfg(feature = "portable")]
mod portable {
    use log::info;
    use semver::Version;
    use serde::{Deserialize, Serialize};
    use tauri::AppHandle;

    use crate::commands::updater::get_app_version;

    const RELEASES_URL: &str = "https://shy-waterfall-2797.bruhnn.workers.dev/";

    #[derive(Debug, Deserialize)]
    struct GitHubRelease {
        tag_name: String,
        html_url: String,
        changelog: Option<Vec<String>>,
    }

    #[derive(Debug, Deserialize, Clone, Serialize)]
    struct UpdateInfo {
        version: String,
        download_url: String,
    }

    pub(super) async fn fetch_app_latest_version(
        app: &AppHandle,
    ) -> Result<(Version, String, Vec<String>), String> {
        let current_version = get_app_version(&app);
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(30))
            .build()
            .map_err(|e| format!("Failed to build HTTP client: {e}"))?;

        let release: GitHubRelease = client
            .get(RELEASES_URL)
            .header("Accept", "application/json")
            .header("X-Manager-Version", current_version)
            .header("X-Manager-Platform", std::env::consts::OS)
            .header("X-Manager-Portable", "true")
            .send()
            .await
            .map_err(|e| format!("Request failed: {e}"))?
            .json()
            .await
            .map_err(|e| format!("Invalid JSON: {e}"))?;

        let latest_version = release.tag_name.trim_start_matches('v');
        let html_url = release.html_url.clone();
        info!("Latest version: {latest_version}, URL: {html_url}");
        let version =
            Version::parse(latest_version).map_err(|e| format!("Invalid remote version: {e}"))?;
        let changelog = release.changelog.unwrap_or_default();
        Ok((version, html_url, changelog))
    }
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct UpdateAvailablePayload {
    latest_version: String,
    download_url: String,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
struct ProgressPayload {
    version: String,
    progress: u8,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateMetadata {
    version: String,
    current_version: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    download_url: Option<String>,
    changelog: Option<Vec<String>>,
}

#[derive(Debug, thiserror::Error)]
pub enum UpdateError {
    #[error(transparent)]
    Updater(#[from] tauri_plugin_updater::Error),
    #[error("there is no pending update")]
    NoPendingUpdate,
    #[cfg(feature = "portable")]
    #[error("update check failed: {0}")]
    CheckFailed(String),
}

impl Serialize for UpdateError {
    fn serialize<S>(&self, serializer: S) -> std::result::Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        serializer.serialize_str(self.to_string().as_str())
    }
}

pub struct PendingUpdate(pub Mutex<Option<(Update, Vec<u8>)>>);
pub type ResultUpdate<T> = std::result::Result<T, UpdateError>;

pub fn get_app_version(app: &AppHandle) -> String {
    app.package_info().version.to_string()
}

#[tauri::command]
pub fn get_mod_preview_version(app_handle: AppHandle) -> Option<String> {
    updater::mod_preview::get_mod_preview_version(app_handle)
}

#[tauri::command]
pub async fn check_for_mod_preview_update(
    app_handle: AppHandle,
) -> Result<UpdateAvailablePayload, String> {
    let (latest_version, _download_url) = updater::mod_preview::check_for_update(app_handle).await?;

    debug!(
        "Checked for mod preview update: latest version {}, download URL: {}",
        latest_version.as_deref().unwrap_or_default(),
        _download_url.as_deref().unwrap_or_default()
    );

    if let Some(download_url) = _download_url {
        info!(
            "Mod preview update available: version {}, URL: {}",
            latest_version.as_deref().unwrap_or_default(),
            download_url
        );
        Ok(UpdateAvailablePayload {
            latest_version: latest_version.unwrap_or_default(),
            download_url,
        })
    } else {
        Err("No update available".to_string())
    }
}

#[tauri::command]
pub async fn update_mod_preview(app_handle: AppHandle) {
    app_handle.emit("update:modPreview:checking", ()).ok();

    let result = updater::mod_preview::check_for_update(app_handle.clone()).await;

    match result {
        Ok((Some(latest_version), Some(download_url))) => {
            app_handle
                .emit(
                    "update:modPreview:available",
                    (latest_version.clone(), download_url.clone()),
                )
                .ok();

            let dest_path = match get_mod_preview_path(&app_handle) {
                Some(p) => p,
                None => {
                    app_handle
                        .emit(
                            "update:modPreview:error",
                            "Failed to resolve mod preview path",
                        )
                        .ok();
                    return;
                }
            };

            if let Some(parent) = dest_path.parent() {
                if let Err(e) = tokio::fs::create_dir_all(parent).await {
                    app_handle
                        .emit(
                            "update:modPreview:error",
                            format!("Failed to create directory: {e}"),
                        )
                        .ok();
                    return;
                }
            }

            let client = reqwest::Client::new();
            let response = match client
                .get(&download_url)
                .header("User-Agent", "BD2ModManager")
                .send()
                .await
            {
                Ok(r) => r,
                Err(e) => {
                    app_handle
                        .emit(
                            "update:modPreview:error",
                            format!("Download request failed: {e}"),
                        )
                        .ok();
                    return;
                }
            };

            if !response.status().is_success() {
                app_handle
                    .emit(
                        "update:modPreview:error",
                        format!("Download failed: HTTP {}", response.status()),
                    )
                    .ok();
                return;
            }

            let total_size = response.content_length().unwrap_or(0);
            let mut downloaded: u64 = 0;

            let mut file = match tokio::fs::File::create(&dest_path).await {
                Ok(f) => f,
                Err(e) => {
                    app_handle
                        .emit(
                            "update:modPreview:error",
                            format!("Failed to create file: {e}"),
                        )
                        .ok();
                    return;
                }
            };

            let mut stream = response.bytes_stream();
            use futures_util::StreamExt;

            while let Some(chunk) = stream.next().await {
                let chunk = match chunk {
                    Ok(c) => c,
                    Err(e) => {
                        app_handle
                            .emit("update:modPreview:error", format!("Download error: {e}"))
                            .ok();
                        return;
                    }
                };

                if let Err(e) = file.write_all(&chunk).await {
                    app_handle
                        .emit("update:modPreview:error", format!("Write error: {e}"))
                        .ok();
                    return;
                }

                downloaded += chunk.len() as u64;

                let progress = if total_size > 0 {
                    (downloaded as f64 / total_size as f64 * 100.0) as u8
                } else {
                    0
                };

                app_handle
                    .emit(
                        "update:modPreview:downloading",
                        ProgressPayload {
                            version: latest_version.clone(),
                            progress,
                        },
                    )
                    .ok();
            }

            app_handle
                .emit("update:modPreview:downloaded", latest_version.clone())
                .ok();
        }

        Ok((None, None)) => {
            app_handle.emit("update:modPreview:uptodate", ()).ok();
        }

        Ok(_) => {
            app_handle
                .emit("update:modPreview:error", "Invalid update state")
                .ok();
        }

        Err(err) => {
            app_handle.emit("update:modPreview:error", err).ok();
        }
    }
}

#[tauri::command]
pub async fn update_game_data(app_handle: AppHandle) -> Result<(), String> {
    updater::game_data::update_characters(app_handle).await
}

#[cfg(feature = "portable")]
#[tauri::command]
pub async fn check_for_app_update(app_handle: AppHandle) -> ResultUpdate<Option<UpdateMetadata>> {
    match portable::fetch_app_latest_version(&app_handle).await {
        Ok((latest_version, download_url, changelog)) => {
            let local_version = get_app_version(&app_handle);
            let local_ver = semver::Version::parse(&local_version)
                .map_err(|e| UpdateError::CheckFailed(format!("Invalid local version: {e}")))?;

            if latest_version <= local_ver {
                return Ok(None);
            }

            Ok(Some(UpdateMetadata {
                version: latest_version.to_string(),
                current_version: local_version,
                download_url: Some(download_url),
                changelog: Some(changelog),
            }))
        }
        Err(e) => Err(UpdateError::CheckFailed(e)),
    }
}

#[cfg(not(feature = "portable"))]
#[tauri::command]
pub async fn check_for_app_update(
    app_handle: AppHandle,
    pending_update: State<'_, PendingUpdate>,
) -> ResultUpdate<Option<UpdateMetadata>> {
    use reqwest::header::{HeaderMap, HeaderValue};
    use tauri_plugin_updater::UpdaterExt;

    let mut headers = HeaderMap::new();
    headers.insert("X-Manager-Version", HeaderValue::from_str(&get_app_version(&app_handle)).unwrap());
    headers.insert("X-Manager-Platform", HeaderValue::from_str(std::env::consts::OS).unwrap());
    headers.insert("X-Manager-Portable", HeaderValue::from_static("false"));

    let update = app_handle
        .updater_builder()
        .timeout(std::time::Duration::from_secs(30))
        .headers(headers)
        .build()?
        .check()
        .await?;

    match update {
        None => Ok(None),
        Some(update) => {
            let metadata = UpdateMetadata {
                version: update.version.clone(),
                current_version: update.current_version.clone(),
                download_url: None,
                changelog: None,
            };

            let bytes = update.download(|_, _| {}, || {}).await?;
            *pending_update.0.lock().unwrap() = Some((update, bytes));

            Ok(Some(metadata))
        }
    }
}

#[cfg(not(feature = "portable"))]
#[tauri::command]
pub async fn install_app_update(
    app_handle: AppHandle,
    pending_update: State<'_, PendingUpdate>,
) -> ResultUpdate<()> {
    let Some((update, bytes)) = pending_update.0.lock().unwrap().take() else {
        return Err(UpdateError::NoPendingUpdate);
    };

    update.install(bytes)?;
    app_handle.restart();
}
