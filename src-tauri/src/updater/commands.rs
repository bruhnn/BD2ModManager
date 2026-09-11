use crate::{
    updater::{self, game_data::GameDataUpdateError, mod_preview::ModPreviewUpdateError},
    utils::path::get_mod_preview_path,
};
use log::{debug, info};
use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use tauri::ipc::Channel;
use tauri::AppHandle;
#[cfg(not(feature = "portable"))]
use tauri::State;
use tauri_plugin_updater::Update;
use tokio::io::AsyncWriteExt;

#[cfg(feature = "portable")]
mod portable {
    use log::info;
    use semver::Version;
    use serde::{Deserialize, Serialize};
    use tauri::AppHandle;

    use crate::updater::commands::get_app_version;

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

#[derive(Clone, Serialize)]
#[serde(tag = "event", content = "data", rename_all_fields = "camelCase")]
pub enum DownloadEvent {
    #[serde(rename_all = "camelCase")]
    Started {
        total_size: Option<u64>,
    },
    #[serde(rename_all = "camelCase")]
    Progress {
        chunk_length: usize,
    },
    Finished,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AppUpdateMetadata {
    version_available: String,
    current_version: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    download_url: Option<String>,
    changelog: Option<Vec<String>>,
    is_update_recommended: bool,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct ModPreviewUpdateMetadata {
    version_available: String,
    current_version: String,
    download_url: String,
}

#[derive(Debug, thiserror::Error)]
pub enum AppUpdateError {
    #[error(transparent)]
    Updater(#[from] tauri_plugin_updater::Error),
    #[error("there is no pending update")]
    NoPendingUpdate,
    #[error("update was not downloaded")]
    UpdateNotDownloaded,
    #[cfg(feature = "portable")]
    #[error("update check failed: {0}")]
    CheckFailed(String),
}

impl Serialize for AppUpdateError {
    fn serialize<S>(&self, serializer: S) -> std::result::Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        serializer.serialize_str(self.to_string().as_str())
    }
}

// Update, Bytes
pub struct PendingUpdate(pub Mutex<Option<(Update, Option<Vec<u8>>)>>);
pub type AppUpdateResult<T> = std::result::Result<T, AppUpdateError>;

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
) -> Result<Option<ModPreviewUpdateMetadata>, ModPreviewUpdateError> {

    let update = updater::mod_preview::check_for_update(&app_handle).await?;

    let current_version =
        updater::mod_preview::get_mod_preview_version(app_handle).unwrap_or_default();

    if let Some(update) = update {
        debug!(
            "Checked for mod preview update: latest version {}, download URL: {}",
            update.version, update.download_url
        );
        info!(
            "Mod preview update available: version {}, URL: {}",
            update.version, update.download_url
        );

        return Ok(Some(ModPreviewUpdateMetadata {
            version_available: update.version,
            current_version,
            download_url: update.download_url,
        }));
    }

    Ok(None)
}

#[tauri::command]
pub async fn download_mod_preview(
    app_handle: AppHandle,
    on_event: Channel<DownloadEvent>,
) -> Result<bool, ModPreviewUpdateError> {


    let result = updater::mod_preview::check_for_update(&app_handle).await;

    match result {
        Ok(Some(update)) => {
            let dest_path = get_mod_preview_path(&app_handle)
                .ok_or(ModPreviewUpdateError::InstallationPathNotFound)?;

            if let Some(parent) = dest_path.parent() {
                tokio::fs::create_dir_all(parent).await.map_err(|source| {
                    ModPreviewUpdateError::SaveFailed {
                        path: parent.to_string_lossy().into_owned(),
                        source,
                    }
                })?;
            }

            let client = reqwest::Client::new();
            let response = client
                .get(&update.download_url)
                .header("User-Agent", "BD2ModManager")
                .send()
                .await
                .map_err(|e| ModPreviewUpdateError::DownloadFailed {
                    reason: e.to_string(),
                })?;

            if !response.status().is_success() {
                return Err(ModPreviewUpdateError::DownloadFailed {
                    reason: format!("server returned HTTP {}", response.status()),
                });
            }

            let total_size = response.content_length();

            let _ = on_event.send(DownloadEvent::Started { total_size });

            let mut file = tokio::fs::File::create(&dest_path)
                .await
                .map_err(|source| ModPreviewUpdateError::SaveFailed {
                    path: dest_path.to_string_lossy().into_owned(),
                    source,
                })?;

            let mut stream = response.bytes_stream();
            use futures_util::StreamExt;

            while let Some(chunk) = stream.next().await {
                let chunk = chunk.map_err(|e| ModPreviewUpdateError::DownloadFailed {
                    reason: e.to_string(),
                })?;

                file.write_all(&chunk).await.map_err(|source| {
                    ModPreviewUpdateError::SaveFailed {
                        path: dest_path.to_string_lossy().into_owned(),
                        source,
                    }
                })?;

                let _ = on_event.send(DownloadEvent::Progress {
                    chunk_length: chunk.len(),
                });
            }

            file.flush()
                .await
                .map_err(|source| ModPreviewUpdateError::SaveFailed {
                    path: dest_path.to_string_lossy().into_owned(),
                    source,
                })?;

            let _ = on_event.send(DownloadEvent::Finished);
            Ok(true)
        }

        Ok(None) => Ok(false),

        Err(err) => Err(err),
    }
}


#[derive(Debug, Clone, Copy, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum GameDataResource {
    Characters,
    CharacterAssets,
}

#[derive(Debug, Serialize, Clone)]
pub struct GameDataDownloadProgress {
    pub percentage: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub current: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub total: Option<u32>,
}

#[derive(Debug, Serialize)]
#[serde(tag = "event", content = "data")]
pub enum GameDataEvent {
    Started,
    Updating {
        resource: String,
        percentage: u8,
        label: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        download: Option<GameDataDownloadProgress>,
    },
    Updated {
        resource: String,
        label: String,
    },
    Finished,
}

#[tauri::command]
pub async fn update_game_data(app_handle: AppHandle, on_event: Channel<GameDataEvent>) -> Result<(), GameDataUpdateError> {
    updater::game_data::update_characters(app_handle, on_event).await
}

#[cfg(feature = "portable")]
#[tauri::command]
pub async fn check_for_app_update(
    app_handle: AppHandle,
    dev_return_version: Option<String>,
) -> AppUpdateResult<Option<AppUpdateMetadata>> {
    let _ = dev_return_version;

    match portable::fetch_app_latest_version(&app_handle).await {
        Ok((latest_version, download_url, changelog)) => {
            let local_version = get_app_version(&app_handle);
            let local_ver = semver::Version::parse(&local_version)
                .map_err(|e| AppUpdateError::CheckFailed(format!("Invalid local version: {e}")))?;

            if latest_version <= local_ver {
                return Ok(None);
            }

            Ok(Some(AppUpdateMetadata {
                version_available: latest_version.to_string(),
                current_version: local_version,
                download_url: Some(download_url),
                changelog: Some(changelog),
                is_update_recommended: false,
            }))
        }
        Err(e) => Err(AppUpdateError::CheckFailed(e)),
    }
}

#[cfg(not(feature = "portable"))]
#[tauri::command]
pub async fn check_for_app_update(
    app_handle: AppHandle,
    pending_update: State<'_, PendingUpdate>,
    dev_return_version: Option<String>,
) -> AppUpdateResult<Option<AppUpdateMetadata>> {
    let _ = dev_return_version;

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
            let metadata = AppUpdateMetadata {
                version_available: update.version.clone(),
                current_version: update.current_version.clone(),
                download_url: None,
                changelog: None,
                is_update_recommended: false,
            };

            // let bytes = update.download(|_, _| {}, || {}).await?;
            // *pending_update.0.lock().unwrap() = Some((update, bytes));
            *pending_update.0.lock().unwrap() = Some((update, None));

            Ok(Some(metadata))
        }
    }
}

#[cfg(not(feature = "portable"))]
#[tauri::command]
pub async fn download_app_update(
    pending_update: State<'_, PendingUpdate>,
    on_event: Channel<DownloadEvent>,
) -> AppUpdateResult<()> {
    #[cfg(debug_assertions)]
    {
        let _ = pending_update;

        const TOTAL_BYTES: usize = 200 * 1024 * 1024;
        const CHUNK_BYTES: usize = 512 * 1024;

        let _ = on_event.send(DownloadEvent::Started {
            total_size: Some(TOTAL_BYTES as u64),
        });

        let mut downloaded = 0;

        while downloaded < TOTAL_BYTES {
            let chunk_length = CHUNK_BYTES.min(TOTAL_BYTES - downloaded);

            tokio::time::sleep(std::time::Duration::from_millis(75)).await;
            let _ = on_event.send(DownloadEvent::Progress { chunk_length });

            downloaded += chunk_length;
        }

        let _ = on_event.send(DownloadEvent::Finished);
        Ok(())
    }

    #[cfg(not(debug_assertions))]
    {
        let Some((update, bytes)) = pending_update.0.lock().unwrap().take() else {
            return Err(AppUpdateError::NoPendingUpdate);
        };

        if bytes.is_some() {
            *pending_update.0.lock().unwrap() = Some((update, bytes));
            return Ok(());
        }

        let mut started = false;

        let result = update
            .download(
                |chunk_length, total_size| {
                    if !started {
                        let _ = on_event.send(DownloadEvent::Started { total_size });
                        started = true;
                    }

                    let _ = on_event.send(DownloadEvent::Progress { chunk_length });
                },
                || {
                    let _ = on_event.send(DownloadEvent::Finished);
                },
            )
            .await;

        match result {
            Ok(bytes) => {
                *pending_update.0.lock().unwrap() = Some((update, Some(bytes)));
                Ok(())
            }
            Err(error) => {
                *pending_update.0.lock().unwrap() = Some((update, None));
                Err(error.into())
            }
        }
    }
}

#[cfg(not(feature = "portable"))]
#[tauri::command]
pub async fn install_app_update(
    app_handle: AppHandle,
    pending_update: State<'_, PendingUpdate>,
) -> AppUpdateResult<()> {
    let Some((update, bytes)) = pending_update.0.lock().unwrap().take() else {
        return Err(AppUpdateError::NoPendingUpdate);
    };

    let Some(bytes) = bytes else {
        *pending_update.0.lock().unwrap() = Some((update, None));
        return Err(AppUpdateError::UpdateNotDownloaded);
    };

    // [TODO] add a way to check if the game is doing syncing to block the restart

    if let Err(error) = update.install(&bytes) {
        *pending_update.0.lock().unwrap() = Some((update, Some(bytes)));
        return Err(error.into());
    }

    app_handle.restart();
}
