use log::{debug, info, warn};
use semver::Version;
use serde::{Deserialize, Serialize};
use tauri::{Emitter, Manager};

const CHARACTERS_URL: &str = "https://raw.githubusercontent.com/bruhnn/BD2ModManager/refs/heads/main/src-tauri/data/characters.json";
const STANDING_ASSETS_BASE_URL: &str = "https://raw.githubusercontent.com/bruhnn/BD2ModManager/refs/heads/main/public/characters/standing/";
const HEADS_ASSETS_BASE_URL: &str = "https://raw.githubusercontent.com/bruhnn/BD2ModManager/refs/heads/main/public/characters/heads/";

#[derive(Debug, Deserialize, Serialize, Clone)]
struct ProgressPayload {
    progress: u8,
    label: String,
}

async fn fetch_latest_characters_data() -> Result<(String, serde_json::Value), String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .map_err(|e| format!("Failed to build HTTP client: {e}"))?;

    let json = client
        .get(CHARACTERS_URL)
        .send()
        .await
        .map_err(|e| format!("Failed to fetch characters.json: {e}"))?
        .json::<serde_json::Value>()
        .await
        .map_err(|e| format!("Failed to parse characters.json: {e}"))?;

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
) -> Result<(), String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(15))
        .build()
        .map_err(|e| format!("Failed to build HTTP client: {e}"))?;

    let standing_characters_dir = app_handle
        .path()
        .app_data_dir()
        .map_err(|_| "Failed to get app data dir")?
        .join("assets")
        .join("standing");

    let heads_characters_dir = app_handle
        .path()
        .app_data_dir()
        .map_err(|_| "Failed to get app data dir")?
        .join("assets")
        .join("heads");

    tokio::fs::create_dir_all(&standing_characters_dir)
        .await
        .map_err(|e| format!("Failed creating dir: {e}"))?;

    tokio::fs::create_dir_all(&heads_characters_dir)
        .await
        .map_err(|e| format!("Failed creating dir: {e}"))?;

    let bundled_assets: std::collections::HashSet<String> = app_handle
        .asset_resolver()
        .iter()
        .map(|(path, _)| path.to_string())
        .collect();

    let characters_w_missing_assets: Vec<(String, bool, bool)> = {
        #[cfg(debug_assertions)]
        {
            vec![]
        }

        #[cfg(not(debug_assertions))]
        {
            characters["characters"]
                .as_array()
                .ok_or("Invalid characters format")?
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
        }
    };

    let total = characters_w_missing_assets.len();

    if total == 0 {
        info!("No character assets found to download");
        return Ok(());
    }

    info!("Found {total} characters with missing assets, downloading...");

    for (index, (character_id, must_download_standing, must_download_head)) in
        characters_w_missing_assets.iter().enumerate()
    {
        info!("Downloading missing assets for {character_id}; standing: {must_download_standing}, head: {must_download_head}");

        app_handle
            .emit(
                "update:gameData:updating",
                ProgressPayload {
                    progress: ((index + 1) as f32 / total as f32 * 100.0) as u8,
                    label: character_id.clone(),
                },
            )
            .ok();

        if *must_download_standing {
            let standing_url = format!("{}{}.png", STANDING_ASSETS_BASE_URL, character_id);
            let response = client.get(&standing_url).send().await.map_err(|e| {
                format!("Failed to download standing asset for {character_id}: {e}")
            })?;

            if response.status().is_success() {
                let bytes = response.bytes().await.map_err(|e| {
                    format!("Failed to read bytes for standing asset of {character_id}: {e}")
                })?;

                tokio::fs::write(
                    standing_characters_dir.join(format!("{}.png", character_id)),
                    &bytes,
                )
                .await
                .map_err(|e| format!("Failed to save standing asset for {character_id}: {e}"))?;
            } else {
                warn!("Standing asset not found for {character_id} at URL: {standing_url}");
            }
        }

        if *must_download_head {
            let head_url = format!("{}{}.png", HEADS_ASSETS_BASE_URL, character_id);
            let response =
                client.get(&head_url).send().await.map_err(|e| {
                    format!("Failed to download head asset for {character_id}: {e}")
                })?;

            if response.status().is_success() {
                let bytes = response.bytes().await.map_err(|e| {
                    format!("Failed to read bytes for head asset of {character_id}: {e}")
                })?;

                tokio::fs::write(
                    heads_characters_dir.join(format!("{}.png", character_id)),
                    &bytes,
                )
                .await
                .map_err(|e| format!("Failed to save head asset for {character_id}: {e}"))?;
            } else {
                warn!("Head asset not found for {character_id} at URL: {head_url}");
            }
        }
    }

    Ok(())
}

pub async fn update_characters(app_handle: tauri::AppHandle) -> Result<(), String> {
    app_handle.emit("update:gameData:checking", ()).ok();

    let (latest_version_str, latest_characters) = fetch_latest_characters_data()
        .await
        .map_err(|e| format!("Failed to fetch latest characters data: {e}"))?;

    let latest_version =
        Version::parse(&latest_version_str).map_err(|e| format!("Invalid latest version: {e}"))?;

    info!("Latest characters version: {latest_version}");

    if let Some(local_str) = get_local_characters_version(&app_handle) {
        let local_version =
            Version::parse(&local_str).map_err(|e| format!("Invalid local version: {e}"))?;

        debug!("Local characters version: {local_version}");

        if local_version >= latest_version {
            info!("Characters data is up to date (version {local_version})");
            info!("Checking for missing character assets...");

            let local_characters: serde_json::Value = std::fs::read_to_string(
                app_handle
                    .path()
                    .app_data_dir()
                    .map_err(|_| "Failed to get app data dir")?
                    .join("characters.json"),
            )
            .ok()
            .and_then(|s| serde_json::from_str(&s).ok())
            .unwrap_or(latest_characters.clone());

            if let Err(e) = download_missing_assets(&app_handle, &local_characters).await {
                warn!("Failed to download missing assets: {e}");
                app_handle
                    .emit("update:gameData:error", serde_json::json!({ "message": e }))
                    .ok();
            } else {
                info!("All character assets are present");
                app_handle.emit("update:gameData:updated", ()).ok();
            }

            return Ok(());
        }

        info!("Updating characters: {local_version} -> {latest_version}");
    } else {
        warn!("No local characters data found, will use latest version {latest_version}");
    }

    let app_dir = app_handle
        .path()
        .app_data_dir()
        .map_err(|_| "Failed to get app data directory")?;
    let characters_path = app_dir.join("characters.json");

    std::fs::write(
        &characters_path,
        serde_json::to_string_pretty(&latest_characters).unwrap(),
    )
    .map_err(|e| format!("Failed to save characters.json: {e}"))?;

    info!("Characters data updated to version {latest_version}, downloading missing assets...");

    if let Err(e) = download_missing_assets(&app_handle, &latest_characters).await {
        warn!("Failed to download missing assets: {e}");
        app_handle
            .emit("update:gameData:error", serde_json::json!({ "message": e }))
            .ok();
    } else {
        info!("All character assets are present");
        app_handle.emit("update:gameData:updated", ()).ok();
    }

    Ok(())
}
