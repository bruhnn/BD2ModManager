use std::{fs, path::PathBuf};

use regex::Regex;
use serde::Serialize;
use tauri::AppHandle;

use crate::{
    game::installer::{migrate_old_manifest, read_manifest},
    utils::misc::{compare_versions, get_dll_version},
};

#[derive(Serialize)]
pub enum Status {
    NotInstalled,
    Installed,
    InstalledButOutdated,
    BepInExMissing,
}

#[derive(Serialize)]
#[serde(tag = "type", content = "reason")]
pub enum CanRemove {
    Yes,
    No(String),
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct VersionResult {
    pub status: Status,
    pub version: Option<String>,
    pub can_remove: Option<CanRemove>,
    pub can_configure: Option<bool>,
}

pub fn get_game_version(game_path: &PathBuf) -> Option<String> {
    let path = game_path
        .join("BrownDust II_Data")
        .join("globalgamemanagers");

    if !path.exists() {
        return None;
    }

    let data = fs::read(&path).ok()?;
    let content = String::from_utf8_lossy(&data);

    let re = Regex::new(r"\b\d{1,2}\.\d{1,2}\.\d{1,2}\b").ok()?;

    for cap in re.find_iter(&content) {
        let version = cap.as_str();

        if !version.starts_with("20") {
            return Some(version.to_string());
        }
    }

    None
}

pub fn get_bepinex_version(app_handle: &AppHandle, game_path: &PathBuf) -> Option<VersionResult> {
    let bepinex_dll_path = game_path.join("BepInEx").join("core").join("BepInEx.dll");
    let bepinex_version = get_dll_version(&bepinex_dll_path);

    let _ = migrate_old_manifest(
        app_handle,
        game_path.join("BepInEx/.bd2mm_bepinex_manifest.json"),
        "BepInEx",
    );

    let manifest = read_manifest(app_handle, "BepInEx").unwrap_or_default();
    let manifest_version = manifest.get("version").and_then(|v| v.as_str());

    let can_remove: CanRemove = {
        if matches!(
            (&bepinex_version, manifest_version),
            (Some(installed), Some(recorded)) if installed == recorded
        ) {
            let bdx_dll = game_path.join("BepInEx/plugins/BrownDustX/lynesth.bd2.browndustx.dll");
            let cm_dll = game_path.join("BepInEx/plugins/ConfigurationManager/ConfigurationManager.dll");

            if bdx_dll.exists() || cm_dll.exists() {
                CanRemove::No("PluginsInstalled".to_string())
            } else {
                CanRemove::Yes
            }
        } else {
            CanRemove::No("VersionMismatch".to_string())
        }
    };

    let can_configure = game_path.join("BepInEx/config/BepInEx.cfg").exists();

    match bepinex_version {
        Some(v) => Some(VersionResult {
            status: Status::Installed,
            version: Some(v),
            can_configure: Some(can_configure),
            can_remove: Some(can_remove),
        }),
        None => Some(VersionResult {
            status: Status::NotInstalled,
            version: None,
            can_configure: None,
            can_remove: None,
        }),
    }
}
pub fn get_browndustx_version(
    app_handle: &AppHandle,
    game_path: &PathBuf,
) -> Option<VersionResult> {
    let bepinex_path = game_path.join("BepInEx");
    let bepinex_dll_path = bepinex_path.join("core/BepInEx.dll");
    let bepinex_winhttp_dll_path = game_path.join("winhttp.dll");

    if !bepinex_path.exists() || !bepinex_dll_path.exists() || !bepinex_winhttp_dll_path.exists() {
        return Some(VersionResult {
            status: Status::BepInExMissing,
            version: None,
            can_configure: None,
            can_remove: None,
        });
    }

    let bdx_dll_path = game_path.join("BepInEx/plugins/BrownDustX/lynesth.bd2.browndustx.dll");
    let bdx_version = get_dll_version(&bdx_dll_path);

    let _ = migrate_old_manifest(
        app_handle,
        game_path.join("BepInEx/plugins/BrownDustX/.bd2mm_bdx_manifest.json"),
        "BrownDustX",
    );

    let manifest = read_manifest(app_handle, "BrownDustX").unwrap_or_default();
    let manifest_version = manifest.get("version").and_then(|v| v.as_str());

    let can_remove: CanRemove = if !bdx_dll_path.exists() {
        CanRemove::No("NotInstalled".to_string())
    } else if matches!(
        (&bdx_version, manifest_version),
        (Some(installed), Some(recorded)) if installed == recorded
    ) {
        CanRemove::Yes
    } else {
        CanRemove::No("VersionMismatch".to_string())
    };

    let can_configure =
        bdx_dll_path.exists() && game_path.join("BepInEx/config/BrownDustX.cfg").exists();

    match bdx_version {
        Some(version) => {
            if let Some(gv) = get_game_version(game_path) {
                if compare_versions(&gv, &version) == std::cmp::Ordering::Greater {
                    return Some(VersionResult {
                        status: Status::InstalledButOutdated,
                        version: Some(version),
                        can_remove: Some(can_remove),
                        can_configure: Some(can_configure),
                    });
                }
            }
            Some(VersionResult {
                status: Status::Installed,
                version: Some(version),
                can_remove: Some(can_remove),
                can_configure: Some(can_configure),
            })
        }
        None => Some(VersionResult {
            status: Status::NotInstalled,
            version: None,
            can_remove: None,
            can_configure: None,
        }),
    }
}

pub fn get_configmanager_version(
    app_handle: &AppHandle,
    game_path: &PathBuf,
) -> Option<VersionResult> {
    let bepinex_path = game_path.join("BepInEx");
    let bepinex_dll_path = bepinex_path.join("core/BepInEx.dll");
    let bepinex_winhttp_dll_path = game_path.join("winhttp.dll");

    if !bepinex_path.exists() || !bepinex_dll_path.exists() || !bepinex_winhttp_dll_path.exists() {
        return Some(VersionResult {
            status: Status::BepInExMissing,
            version: None,
            can_configure: None,
            can_remove: None,
        });
    }

    let cm_dll_path =
        game_path.join("BepInEx/plugins/ConfigurationManager/ConfigurationManager.dll");
    let cm_version = get_dll_version(&cm_dll_path);

    let _ = migrate_old_manifest(
        app_handle,
        game_path.join("BepInEx/plugins/ConfigurationManager/.bd2mm_configmanager_manifest.json"),
        "ConfigurationManager",
    );

    let manifest = read_manifest(app_handle, "ConfigurationManager").unwrap_or_default();
    let manifest_version = manifest.get("version").and_then(|v| v.as_str());

    let can_remove: CanRemove = if !cm_dll_path.exists() {
        CanRemove::No("NotInstalled".to_string())
    } else if matches!(
        (&cm_version, manifest_version),
        (Some(installed), Some(recorded)) if installed == recorded
    ) {
        CanRemove::Yes
    } else {
        CanRemove::No("VersionMismatch".to_string())
    };

    let can_configure = cm_dll_path.exists()
        && game_path
            .join("BepInEx/config/ConfigurationManager.cfg")
            .exists();

    match cm_version {
        Some(v) => Some(VersionResult {
            status: Status::Installed,
            version: Some(v),
            can_configure: Some(can_configure),
            can_remove: Some(can_remove),
        }),
        None => Some(VersionResult {
            status: Status::NotInstalled,
            version: None,
            can_configure: None,
            can_remove: None,
        }),
    }
}