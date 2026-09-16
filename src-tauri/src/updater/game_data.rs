use log::{debug, info, warn};
use semver::Version;
use serde::Serialize;
use tauri::{ipc::Channel, Manager};

use crate::updater::commands::{GameDataDownloadProgress, GameDataEvent};

#[derive(Debug, thiserror::Error)]
pub enum GameDataUpdateError {
    #[error("failed to check for game data updates: {0}")]
    CheckFailed(String),
    #[error("failed to download game data: {0}")]
    DownloadFailed(String),
    #[error("failed to save game data: {0}")]
    SaveFailed(String),
    #[error("invalid game data: {0}")]
    InvalidData(String),
}

impl Serialize for GameDataUpdateError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        serializer.serialize_str(&self.to_string())
    }
}

const CHARACTERS_URL: &str = "https://raw.githubusercontent.com/bruhnn/BD2ModManager/refs/heads/main/src-tauri/data/characters.json";
const STANDING_ASSETS_BASE_URL: &str = "https://raw.githubusercontent.com/bruhnn/BD2ModManager/refs/heads/main/public/characters/standing/";
const HEADS_ASSETS_BASE_URL: &str = "https://raw.githubusercontent.com/bruhnn/BD2ModManager/refs/heads/main/public/characters/heads/";

async fn fetch_latest_characters_data() -> Result<(String, serde_json::Value), GameDataUpdateError>
{
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .map_err(|e| GameDataUpdateError::CheckFailed(e.to_string()))?;

    let json = client
        .get(CHARACTERS_URL)
        .send()
        .await
        .map_err(|e| GameDataUpdateError::CheckFailed(e.to_string()))?
        .json::<serde_json::Value>()
        .await
        .map_err(|e| GameDataUpdateError::InvalidData(e.to_string()))?;

    let version = json
        .get("version")
        .and_then(|v| v.as_str())
        .unwrap_or("0.0.0")
        .to_string();

    Ok((version, json))
}

fn get_local_characters_version(app_handle: &tauri::AppHandle) -> Option<String> {
    let path = app_handle
        .path()
        .app_data_dir()
        .ok()?
        .join("characters.json");
    let data = std::fs::read_to_string(path).ok()?;
    let json: serde_json::Value = serde_json::from_str(&data).ok()?;
    json.get("version")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
}

async fn download_missing_assets(
    app_handle: &tauri::AppHandle,
    characters: &serde_json::Value,
    on_event: &Channel<GameDataEvent>
) -> Result<(), GameDataUpdateError> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(15))
        .build()
        .map_err(|e| GameDataUpdateError::DownloadFailed(e.to_string()))?;

    let standing_characters_dir = app_handle
        .path()
        .app_data_dir()
        .map_err(|e| GameDataUpdateError::SaveFailed(e.to_string()))?
        .join("assets")
        .join("standing");

    let heads_characters_dir = app_handle
        .path()
        .app_data_dir()
        .map_err(|e| GameDataUpdateError::SaveFailed(e.to_string()))?
        .join("assets")
        .join("heads");

    tokio::fs::create_dir_all(&standing_characters_dir)
        .await
        .map_err(|e| GameDataUpdateError::SaveFailed(e.to_string()))?;

    tokio::fs::create_dir_all(&heads_characters_dir)
        .await
        .map_err(|e| GameDataUpdateError::SaveFailed(e.to_string()))?;

    let bundled_assets: std::collections::HashSet<String> = app_handle
        .asset_resolver()
        .iter()
        .map(|(path, _)| path.to_string())
        .collect();

    let characters_w_missing_assets: Vec<(String, bool, bool)> = {
        // #[cfg(debug_assertions)]
        // {
        //     vec![]
        // }

        characters["characters"]
            .as_array()
            .ok_or_else(|| {
                GameDataUpdateError::InvalidData("characters must be an array".to_string())
            })?
            .iter()
            .filter_map(|character| {
                let id = character["id"].as_str()?;

                let is_standing_bundled =
                    bundled_assets.contains(&format!("/characters/standing/{}.png", id));
                let is_head_bundled =
                    bundled_assets.contains(&format!("/characters/heads/{}.png", id));

                // check if is bundled and not already download
                let is_standing_downloaded =
                    standing_characters_dir.join(format!("{}.png", id)).exists();
                let is_head_downloaded =
                    heads_characters_dir.join(format!("{}.png", id)).exists();

                debug!(
                    "[{}] bundled=(standing:{}, head:{}) downloaded=(standing:{}, head:{})",
                    id,
                    is_standing_bundled,
                    is_head_bundled,
                    is_standing_downloaded,
                    is_head_downloaded
                );

                let must_download_standing = !is_standing_bundled && !is_standing_downloaded;
                let must_download_head = !is_head_bundled && !is_head_downloaded;

                if must_download_standing || must_download_head {
                    Some((id.to_string(), must_download_standing, must_download_head))
                } else {
                    None
                }
            })
            .collect()
    };

    let total = characters_w_missing_assets
        .iter()
        .map(|(_, must_download_standing, must_download_head)| {
            (*must_download_standing as usize) + (*must_download_head as usize)
        })
        .sum::<usize>();

    if total == 0 {
        info!("No character assets found to download");
        return Ok(());
    }

    info!("Found {total} missing character assets, downloading...");

    let _ = on_event.send(GameDataEvent::Updating {
        resource: "char_assets".to_string(),
        percentage: 0,
        label: "downloading_assets".to_string(),
        download: Some(GameDataDownloadProgress {
            percentage: Some(0),
            current: Some(0),
            total: Some(total as u32),
        }),
    });

    let mut current = 0;

    for (character_id, must_download_standing, must_download_head) in
        characters_w_missing_assets.iter()
    {
        info!("Downloading missing assets for {character_id}; standing: {must_download_standing}, head: {must_download_head}");

        if *must_download_standing {
            let standing_url = format!("{}{}.png", STANDING_ASSETS_BASE_URL, character_id);
            let response = client.get(&standing_url).send().await.map_err(|e| {
                GameDataUpdateError::DownloadFailed(format!(
                    "standing asset for {character_id}: {e}"
                ))
            })?;

            if response.status().is_success() {
                let bytes = response.bytes().await.map_err(|e| {
                    GameDataUpdateError::DownloadFailed(format!(
                        "standing asset for {character_id}: {e}"
                    ))
                })?;

                tokio::fs::write(
                    standing_characters_dir.join(format!("{}.png", character_id)),
                    &bytes,
                )
                .await
                .map_err(|e| {
                    GameDataUpdateError::SaveFailed(format!(
                        "standing asset for {character_id}: {e}"
                    ))
                })?;
            } else {
                warn!("Standing asset not found for {character_id} at URL: {standing_url}");
            }

            current += 1;

            let percentage = (current as f32 / total as f32 * 100.0) as u8;

            let _ = on_event.send(GameDataEvent::Updating {
                resource: "char_assets".to_string(),
                percentage,
                label: character_id.clone(),
                download: Some(GameDataDownloadProgress {
                    percentage: Some(percentage),
                    current: Some(current as u32),
                    total: Some(total as u32),
                }),
            });
        }

        if *must_download_head {
            let head_url = format!("{}{}.png", HEADS_ASSETS_BASE_URL, character_id);
            let response = client.get(&head_url).send().await.map_err(|e| {
                GameDataUpdateError::DownloadFailed(format!("head asset for {character_id}: {e}"))
            })?;

            if response.status().is_success() {
                let bytes = response.bytes().await.map_err(|e| {
                    GameDataUpdateError::DownloadFailed(format!(
                        "head asset for {character_id}: {e}"
                    ))
                })?;

                tokio::fs::write(
                    heads_characters_dir.join(format!("{}.png", character_id)),
                    &bytes,
                )
                .await
                .map_err(|e| {
                    GameDataUpdateError::SaveFailed(format!("head asset for {character_id}: {e}"))
                })?;
            } else {
                warn!("Head asset not found for {character_id} at URL: {head_url}");
            }

            current += 1;

            let percentage = (current as f32 / total as f32 * 100.0) as u8;

            let _ = on_event.send(GameDataEvent::Updating {
                resource: "char_assets".to_string(),
                percentage,
                label: character_id.clone(),
                download: Some(GameDataDownloadProgress {
                    percentage: Some(percentage),
                    current: Some(current as u32),
                    total: Some(total as u32),
                }),
            });
        }
    }

    Ok(())
}

pub async fn update_characters(
    app_handle: tauri::AppHandle,
    on_event: Channel<GameDataEvent>,
) -> Result<(), GameDataUpdateError> {
    let _ = on_event.send(GameDataEvent::Started);

    let _ = on_event.send(GameDataEvent::Updating {
        resource: "characters".to_string(),
        percentage: 0,
        label: "request_github".to_string(),
        download: Some(GameDataDownloadProgress {
            percentage: None,
            current: None,
            total: None,
        }),
    });

    let (latest_version_str, latest_characters) = fetch_latest_characters_data().await?;

    let _ = on_event.send(GameDataEvent::Updating {
        resource: "characters".to_string(),
        percentage: 5,
        label: "got_characters".to_string(),
        download: None,
    });

    let latest_version = Version::parse(&latest_version_str)
        .map_err(|e| GameDataUpdateError::InvalidData(format!("invalid latest version: {e}")))?;

    info!("Latest characters version: {latest_version}");

    let _ = on_event.send(GameDataEvent::Updating {
        resource: "characters".to_string(),
        percentage: 10,
        label: "checking_version".to_string(),
        download: None,
    });

    if let Some(local_str) = get_local_characters_version(&app_handle) {
        let local_version = Version::parse(&local_str)
            .map_err(|e| GameDataUpdateError::InvalidData(format!("invalid local version: {e}")))?;

        debug!("Local characters version: {local_version}");

        if local_version >= latest_version {
            info!("Characters data is up to date (version {local_version})");
            info!("Checking for missing character assets...");

            let _ = on_event.send(GameDataEvent::Updated {
                resource: "characters".to_string(),
                label: "already_uptodate".to_string()
            });

            let local_characters: serde_json::Value = std::fs::read_to_string(
                app_handle
                    .path()
                    .app_data_dir()
                    .map_err(|e| GameDataUpdateError::SaveFailed(e.to_string()))?
                    .join("characters.json"),
            )
            .ok()
            .and_then(|s| serde_json::from_str(&s).ok())
            .unwrap_or(latest_characters.clone());

            let _ = on_event.send(GameDataEvent::Updating {
                resource: "char_assets".to_string(),
                percentage: 0,
                label: "checking_assets".to_string(),
                download: None,
            });

            download_missing_assets(&app_handle, &local_characters, &on_event).await?;

            info!("All character assets are present");

            let _ = on_event.send(GameDataEvent::Updated {
                resource: "char_assets".to_string(),
                label: "assets_updated".to_string()
            });

            let _ = on_event.send(GameDataEvent::Finished);

            return Ok(());
        }

        info!("Updating characters: {local_version} -> {latest_version}");
    } else {
        warn!("No local characters data found, will use latest version {latest_version}");
    }

    let _ = on_event.send(GameDataEvent::Updating {
        resource: "characters".to_string(),
        percentage: 15,
        label: "saving_characters".to_string(),
        download: None,
    });

    let app_dir = app_handle
        .path()
        .app_data_dir()
        .map_err(|e| GameDataUpdateError::SaveFailed(e.to_string()))?;

    let characters_path = app_dir.join("characters.json");

    let characters_json = serde_json::to_string_pretty(&latest_characters)
        .map_err(|e| GameDataUpdateError::InvalidData(e.to_string()))?;

    std::fs::write(&characters_path, characters_json)
        .map_err(|e| GameDataUpdateError::SaveFailed(format!("characters.json: {e}")))?;

    let _ = on_event.send(GameDataEvent::Updating {
        resource: "characters".to_string(),
        percentage: 100,
        label: "characters_updated".to_string(),
        download: None,
    });

    info!("Characters data updated to version {latest_version}, downloading missing assets...");

    let _ = on_event.send(GameDataEvent::Updating {
        resource: "char_assets".to_string(),
        percentage: 0,
        label: "checking_assets".to_string(),
        download: None,
    });

    download_missing_assets(&app_handle, &latest_characters, &on_event).await?;

    info!("All character assets are present");

    let _ = on_event.send(GameDataEvent::Updated {
        resource: "char_assets".to_string(),
        label: "assets_updated".to_string(),
    });

    let _ = on_event.send(GameDataEvent::Updated {
        resource: "characters".to_string(),
        label: "characters_updated".to_string(),
    });

    let _ = on_event.send(GameDataEvent::Finished);

    Ok(())
}