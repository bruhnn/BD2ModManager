use serde::Serialize;
use log::{error, debug};

use crate::mods::BD2Mod;

// https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file
const INVALID_NAME_CHARS: &[char] = &['<', '>', ':', '"', '/', '\\', '|', '?', '*'];


#[derive(thiserror::Error, Debug, Serialize)]
#[serde(tag = "type", content = "message")]
pub enum ModRenameError {
    #[error("mod '{0}' was not found")]
    ModNotFound(String),
    #[error("mod path '{0}' does not exist on disk")]
    PathMissing(String),
    #[error("a mod named '{0}' already exists")]
    AlreadyExists(String),
    #[error("'{0}' is not a valid name ({1})")]
    InvalidName(String, String), // name and the reason
    #[error("failed to rename mod: '{0}'")]
    IoError(String),
}

pub fn rename_mod(mod_: BD2Mod, new_name: String) -> Result<BD2Mod, ModRenameError> {
    let mod_path = mod_.path.clone();

    // some checks
    if new_name.trim().is_empty() {
        error!("Invalid mod name (empty): '{}'", new_name);
        return Err(ModRenameError::InvalidName(new_name, "name cannot be empty".into()));
    }

    if new_name.trim() == ".." {
        error!("Invalid mod name (..): '{}'", new_name);
        return Err(ModRenameError::InvalidName(new_name.to_string(), "cannot be '..'".to_string()));
    }

    if let Some(bad_char) = new_name.trim().chars().find(|char|  INVALID_NAME_CHARS.contains(char)) {
        error!("Invalid mod name (bad_char = {}): '{}'",  bad_char, new_name);
        return Err(ModRenameError::InvalidName(
            new_name.to_string(),
            format!("contains invalid character '{}'", bad_char),
        ));
    }

    let new_path = mod_path
        .parent()
        .unwrap_or_else(|| std::path::Path::new(""))
        .join(&new_name);

    debug!("Renaming mod {} ({:?}) to {:?}", mod_.name, mod_path, new_path);

    if new_path.exists() {
        error!("A mod with the new name already exists: {:?}", new_path);
        return Err(ModRenameError::AlreadyExists(new_name));
    }

    if mod_path.exists() {
        if let Err(e) = std::fs::rename(&mod_path, &new_path) {
            error!(
                "Failed to rename mod from {:?} to {:?}: {:?}",
                mod_path, new_path, e
            );
            return Err(ModRenameError::IoError(e.to_string()));
        }
    } else {
        error!("Mod path does not exist: {:?}", mod_path);
        return Err(ModRenameError::PathMissing(mod_path.to_string_lossy().to_string()));
    }

    let mut updated_mod = mod_;

    updated_mod.name = new_name.clone();
    updated_mod.path = new_path.clone();
    updated_mod.display_name = new_path
        .file_name()
        .map(|name| name.to_string_lossy().into_owned())
        .unwrap_or_else(|| "unknown".to_string());

    Ok(updated_mod)
}