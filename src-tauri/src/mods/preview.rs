use std::fs::read_dir;
use std::path::PathBuf;

use log::error;
use tauri::AppHandle;
use tauri_plugin_opener::OpenerExt;

#[derive(Debug, thiserror::Error)]
pub enum PreviewError {
    #[error("mod '{mod_name}' was not found")]
    ModNotFound { mod_name: String },
    #[error("mod '{mod_name}' contains errors")]
    ModHasErrors { mod_name: String },
    #[error("preview failed: {reason}")]
    PreviewFailed { reason: String },
    #[error("mod preview tool not found")]
    ModPreviewNotFound,
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),
}

impl serde::Serialize for PreviewError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        use serde::ser::SerializeStruct;
        use serde_json::json;

        let (type_, details): (&str, Option<serde_json::Value>) = match self {
            PreviewError::ModNotFound { mod_name } => (
                "ModNotFound",
                Some(json!({ "mod_name": mod_name })),
            ),
            PreviewError::ModHasErrors { mod_name } => (
                "ModHasErrors",
                Some(json!({ "mod_name": mod_name })),
            ),
            PreviewError::PreviewFailed { reason } => (
                "PreviewFailed",
                Some(json!({ "reason": reason })),
            ),
            PreviewError::ModPreviewNotFound => (
                "ModPreviewNotFound",
                Some(json!({}))
            ),
            PreviewError::Io(error) => (
                "Io",
                Some(json!({ "kind": format!("{:?}", error.kind()) })),
            ),
        };

        let mut s = serializer.serialize_struct("PreviewError", 3)?;
        s.serialize_field("type", type_)?;
        s.serialize_field("details", &details)?;
        s.serialize_field("message", &self.to_string())?;
        s.end()
    }
}

// Check if the folder is a texture mod
pub fn is_texture_mod(path: &PathBuf) -> bool {
    if !path.join("textures").is_dir() {
        return false;
    }

    let (has_skel, has_atlas) = read_dir(path)
        .map(|entries| {
            entries
                .filter_map(Result::ok)
                .fold((false, false), |(skel, atlas), entry| {
                    match entry.path().extension().and_then(|e| e.to_str()) {
                        Some("skel") => (true, atlas),
                        Some("atlas") => (skel, true),
                        _ => (skel, atlas),
                    }
                })
        })
        .unwrap_or((false, false));

    !has_skel && !has_atlas
}

pub fn preview_image(app_handle: AppHandle, path: &PathBuf) -> Result<(), PreviewError> {
    let dir = path.join("textures");
    if !dir.exists() {
        return Ok(());
    }

    let mut img_path: Option<PathBuf> = None;
    for entry in read_dir(&dir)? {
        let entry = entry?;
        let path = entry.path();

        if path.is_file() && path.extension().map(|e| e == "png").unwrap_or(false) {
            img_path = Some(path);
            break;
        }
    }

    if let Some(img) = img_path {
        let img_str = img.to_string_lossy().to_string();
        app_handle
            .opener()
            .open_path(&img_str, None::<&str>)
            .map_err(|e| {
                error!("Failed to open preview image {:?}: {:?}", img_str, e);
                PreviewError::PreviewFailed {
                    reason: e.to_string(),
                }
            })?;
    }

    Ok(())
}
