use std::fs;
use tauri::Manager;

const CHARACTERS: &str = include_str!("../../data/characters.json");
const DATING: &str = include_str!("../../data/dating.json");

pub fn move_data_to_appdata(app_handle: &tauri::AppHandle) -> Result<(), String> {
    let app_data = app_handle
        .path()
        .app_data_dir()
        .map_err(|e| e.to_string())?;

    fs::create_dir_all(&app_data).map_err(|e| e.to_string())?;

    seed_versioned_file(&app_data.join("characters.json"), CHARACTERS, "characters.json")?;
    seed_versioned_file(&app_data.join("dating.json"), DATING, "dating.json")?;

    // Keep dating.json in sync with the dating map in characters.json: any
    // dating_id present in characters.json but missing from dating.json gets a
    // stub entry appended. Existing entries (and their manually-entered
    // affection lists) are never modified.
    sync_dating_from_characters(&app_data)?;

    Ok(())
}

/// Seeds `bundled` into `path`, or overwrites it when the bundled version is
/// newer. Both the bundled string and the existing file must carry a top-level
/// semver `"version"` string.
fn seed_versioned_file(path: &std::path::Path, bundled: &str, label: &str) -> Result<(), String> {
    if !path.exists() {
        println!("Seeding {label} to appdata");
        fs::write(path, bundled).map_err(|e| e.to_string())?;
        return Ok(());
    }

    let bundled_version = semver::Version::parse(
        serde_json::from_str::<serde_json::Value>(bundled)
            .map_err(|e| e.to_string())?["version"]
            .as_str()
            .ok_or_else(|| format!("Missing 'version' in bundled {label}"))?,
    )
    .map_err(|e| e.to_string())?;

    let existing_version = semver::Version::parse(
        serde_json::from_str::<serde_json::Value>(
            &fs::read_to_string(path).map_err(|e| e.to_string())?,
        )
        .map_err(|e| e.to_string())?["version"]
            .as_str()
            .ok_or_else(|| format!("Missing 'version' in existing {label}"))?,
    )
    .map_err(|e| e.to_string())?;

    println!("{label} bundled v{bundled_version} vs appdata v{existing_version}");

    if bundled_version > existing_version {
        println!("Updating {label} from bundled (newer version)");
        fs::write(path, bundled).map_err(|e| e.to_string())?;
    }

    Ok(())
}

/// Appends stub dating entries for any dating_id found in characters.json's
/// `dating` map that is not already present in dating.json. Manual edits to
/// existing entries (including affection lists) are preserved.
fn sync_dating_from_characters(app_data: &std::path::Path) -> Result<(), String> {
    let chars_path = app_data.join("characters.json");
    let dating_path = app_data.join("dating.json");

    let chars: serde_json::Value = serde_json::from_str(
        &fs::read_to_string(&chars_path).map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;

    let mut dating: serde_json::Value = serde_json::from_str(
        &fs::read_to_string(&dating_path).map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;

    // dating map: { "<dating_id>": "<costume_id>", ... }
    let dating_map = match chars.get("dating").and_then(|v| v.as_object()) {
        Some(m) => m,
        None => return Ok(()),
    };

    // Build a lookup of costume_id -> character entry so stubs can be labelled.
    let characters = chars
        .get("characters")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();

    let find_costume = |costume_id: &str| -> Option<(String, String)> {
        for c in &characters {
            // id may be a string or an array of strings.
            let matches = match c.get("id") {
                Some(serde_json::Value::String(s)) => s == costume_id,
                Some(serde_json::Value::Array(arr)) => {
                    arr.iter().any(|v| v.as_str() == Some(costume_id))
                }
                _ => false,
            };
            if matches {
                let character = c
                    .get("character")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                let costume = c
                    .get("costume")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                return Some((character, costume));
            }
        }
        None
    };

    let entries = match dating.get_mut("dating").and_then(|v| v.as_array_mut()) {
        Some(e) => e,
        None => return Ok(()),
    };

    let existing_ids: std::collections::HashSet<String> = entries
        .iter()
        .filter_map(|e| e.get("dating_id").and_then(|v| v.as_str()).map(String::from))
        .collect();

    let mut appended = 0;
    for (dating_id, costume_id_val) in dating_map {
        if existing_ids.contains(dating_id) {
            continue;
        }
        let costume_id = costume_id_val.as_str().unwrap_or("").to_string();
        let (character, costume) = find_costume(&costume_id).unwrap_or_default();

        entries.push(serde_json::json!({
            "dating_id": dating_id,
            "costume_id": costume_id,
            "character": character,
            "costume": costume,
            "affection": []
        }));
        appended += 1;
    }

    if appended > 0 {
        println!("dating.json: appended {appended} new stub entr(y/ies) from characters.json");
        fs::write(
            &dating_path,
            serde_json::to_string_pretty(&dating).map_err(|e| e.to_string())?,
        )
        .map_err(|e| e.to_string())?;
    }

    Ok(())
}
