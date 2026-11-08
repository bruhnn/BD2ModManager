use serde::{Deserialize, Serialize};
use tauri::Manager;
use std::collections::HashMap;

use crate::errors::AppError;

#[derive(thiserror::Error, Debug)]
pub enum ThemesError {
    #[error("Theme with name '{0}' already exists.'")]
    AlreadyExists(String),
    #[error("Theme with name '{0}' not found.'")]
    NotFound(String),
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),
    #[error("Invalid theme JSON: {0}")]
    Json(#[from] serde_json::Error),
    #[error("'{theme_name}' is not a valid theme name ({reason})")]
    InvalidName { theme_name: String, reason: String },
}

const INVALID_NAME_CHARS: &[char] = &['<', '>', ':', '"', '/', '\\', '|', '?', '*'];
const MAX_NAME_LENGTH: usize = 200;

const BUILT_IN_THEMES: &[&str] = &["dark-1", "dark-2", "dark-3", "dark-4", "light-1", "light-2"];

pub(crate) fn validate_theme_name(name: &str) -> Result<(), ThemesError> {
    let reason = if name.trim().is_empty() {
        Some("EMPTY_NAME".to_string())
    } else if let Some(bad_char) = name.chars().find(|c| INVALID_NAME_CHARS.contains(c) || c.is_control()) {
        Some(format!("INVALID_CHAR_{}", bad_char.escape_default()))
    } else if BUILT_IN_THEMES.contains(&name.to_lowercase().as_str()) {
        Some("BUILT_IN_NAME".to_string())
    } else if name.ends_with('.') || name.ends_with(' ') {
        Some("TRAILING_DOT_OR_SPACE".to_string())
    } else if name.chars().count() > MAX_NAME_LENGTH {
        Some("TOO_LONG".to_string())
    } else {
        None
    };

    match reason {
        Some(reason) => Err(ThemesError::InvalidName { theme_name: name.to_string(), reason }),
        None => Ok(()),
    }
}

impl serde::Serialize for ThemesError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        use serde::ser::SerializeStruct;
        use serde_json::json;

        let (type_, details): (&str, Option<serde_json::Value>) = match self {
            ThemesError::AlreadyExists(theme_name) => (
                "AlreadyExists",
                Some(json!({ "theme_name": theme_name })),
            ),
            ThemesError::NotFound(theme_name) => (
                "NotFound",
                Some(json!({ "theme_name": theme_name })),
            ),
            ThemesError::Io(error) => (
                "Io",
                Some(json!({ "kind": format!("{:?}", error.kind()) })),
            ),
            ThemesError::Json(error) => (
                "Json",
                Some(json!({ "line": error.line(), "column": error.column() })),
            ),
            ThemesError::InvalidName { theme_name, reason } => (
                "InvalidName",
                Some(json!({ "theme_name": theme_name, "reason": reason })),
            ),
        };

        let mut s = serializer.serialize_struct("ThemesError", 3)?;
        s.serialize_field("type", type_)?;
        s.serialize_field("details", &details)?;
        s.serialize_field("message", &self.to_string())?;
        s.end()
    }
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct Theme {
    pub name: String,
    pub author: Option<String>,
    pub colors: HashMap<String, String>
}

pub fn get_themes_directory(app_handle: &tauri::AppHandle) -> std::path::PathBuf {
    let app_dir = app_handle.path().app_data_dir().expect("Failed to get app data directory");
    let themes_dir = app_dir.join("themes");
    if !themes_dir.exists() {
        std::fs::create_dir_all(&themes_dir).expect("Failed to create themes directory");
    }
    themes_dir
}

#[tauri::command]
pub fn get_user_themes(app_handle: tauri::AppHandle) -> Result<Vec<Theme>, AppError> {
    let themes_dir = get_themes_directory(&app_handle);

    let mut themes = Vec::new();
    for entry in std::fs::read_dir(themes_dir).map_err(ThemesError::Io)? {
        let path = entry.map_err(ThemesError::Io)?.path();
        if path.extension().and_then(|s| s.to_str()) != Some("json") {
            continue;
        }

        // skip brokn files
        let theme = std::fs::read_to_string(&path)
            .map_err(ThemesError::from)
            .and_then(|content| serde_json::from_str::<Theme>(&content).map_err(ThemesError::from));

        match theme {
            Ok(mut theme) => {
                if let Some(stem) = path.file_stem().and_then(|s| s.to_str()) {
                    theme.name = stem.to_string();
                }
                themes.push(theme);
            }
            Err(error) => log::warn!("Skipping theme file {:?}: {}", path, error),
        }
    }

    Ok(themes)
}

#[tauri::command]
pub fn create_user_theme(app_handle: tauri::AppHandle, theme: Theme) -> Result<(), AppError> {
    validate_theme_name(&theme.name)?;

    let themes_dir = get_themes_directory(&app_handle);
    let theme_file_path = themes_dir.join(format!("{}.json", theme.name));
    let temp_file_path = themes_dir.join(format!("{}.json.tmp", theme.name));

    if theme_file_path.exists() {
        return Err(ThemesError::AlreadyExists(theme.name).into());
    }

    let theme_json = serde_json::to_string_pretty(&theme).map_err(ThemesError::Json)?;
    std::fs::write(&temp_file_path, theme_json).map_err(ThemesError::Io)?;
    std::fs::rename(&temp_file_path, &theme_file_path).map_err(ThemesError::Io)?;

    Ok(())
}

#[tauri::command]
pub fn delete_user_theme(app_handle: tauri::AppHandle, theme_name: String) -> Result<(), AppError> {
    validate_theme_name(&theme_name)?;

    let theme_file_path = get_themes_directory(&app_handle).join(format!("{}.json", theme_name));

    if !theme_file_path.exists() {
        return Err(ThemesError::NotFound(theme_name).into());
    }

    std::fs::remove_file(&theme_file_path).map_err(ThemesError::Io)?;

    Ok(())
}

#[tauri::command]
pub fn update_user_theme(app_handle: tauri::AppHandle, old_name: String, theme: Theme) -> Result<(), AppError> {
    // added old_name for checking because they could contain ../../
    validate_theme_name(&old_name)?;
    validate_theme_name(&theme.name)?;

    let themes_dir = get_themes_directory(&app_handle);
    let old_file_path = themes_dir.join(format!("{}.json", old_name));
    let theme_file_path = themes_dir.join(format!("{}.json", theme.name));
    let temp_file_path = themes_dir.join(format!("{}.json.tmp", theme.name));

    if !old_file_path.exists() {
        return Err(ThemesError::NotFound(old_name).into());
    }

    // windows is case insensitive
    let is_rename = old_name.to_lowercase() != theme.name.to_lowercase();
    if is_rename && theme_file_path.exists() {
        return Err(ThemesError::AlreadyExists(theme.name).into());
    }

    let theme_json = serde_json::to_string_pretty(&theme).map_err(ThemesError::Json)?;
    std::fs::write(&temp_file_path, theme_json).map_err(ThemesError::Io)?;
    if old_name != theme.name {
        std::fs::remove_file(&old_file_path).map_err(ThemesError::Io)?;
    }
    std::fs::rename(&temp_file_path, &theme_file_path).map_err(ThemesError::Io)?;

    Ok(())
}
