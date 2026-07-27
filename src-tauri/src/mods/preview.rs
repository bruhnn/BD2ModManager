use std::fs::read_dir;
use std::path::PathBuf;

use serde::Serialize;
use tauri::AppHandle;
use tauri_plugin_opener::OpenerExt;

#[derive(Serialize, Clone, Debug, thiserror::Error)]
pub enum PreviewError {
    #[error("mod '{0}' was not found")]
    ModNotFound(String),
    #[error("mod contains errors: {0}")]
    ModHasErrors(String),
    #[error("preview failed: {0}")]
    Failed(String),
    #[error("io error: {0}")]
    Io(String),
}

impl From<std::io::Error> for PreviewError {
    fn from(e: std::io::Error) -> Self {
        PreviewError::Io(e.to_string())
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
            .open_path(img_str, None::<&str>)
            .map_err(|e| PreviewError::Failed(e.to_string()))?;
    }

    Ok(())
}
