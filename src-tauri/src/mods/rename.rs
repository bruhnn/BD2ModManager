use log::{error, debug};

use crate::mods::BD2Mod;

// https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file
const INVALID_NAME_CHARS: &[char] = &['<', '>', ':', '"', '/', '\\', '|', '?', '*'];

#[derive(thiserror::Error, Debug)]
pub enum ModRenameError {
    #[error("mod '{mod_name}' was not found")]
    ModNotFound { mod_name: String },
    #[error("mod path '{path}' does not exist on disk")]
    PathNotFound { path: String },
    #[error("a mod named '{mod_name}' already exists")]
    ModAlreadyExists { mod_name: String },
    #[error("'{name}' is not a valid name ({reason})")]
    InvalidName { name: String, reason: String },
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),
}

impl serde::Serialize for ModRenameError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        use serde::ser::SerializeStruct;
        use serde_json::json;

        let (type_, details): (&str, Option<serde_json::Value>) = match self {
            ModRenameError::ModNotFound { mod_name } => (
                "ModNotFound",
                Some(json!({ "mod_name": mod_name })),
            ),
            ModRenameError::PathNotFound { path } => (
                "PathNotFound",
                Some(json!({ "path": path })),
            ),
            ModRenameError::ModAlreadyExists { mod_name } => (
                "ModAlreadyExists",
                Some(json!({ "mod_name": mod_name })),
            ),
            ModRenameError::InvalidName { name, reason } => (
                "InvalidName",
                Some(json!({ "name": name, "reason": reason })),
            ),
            ModRenameError::Io(error) => (
                "Io",
                Some(json!({ "kind": format!("{:?}", error.kind()) })),
            ),
        };

        let mut s = serializer.serialize_struct("ModRenameError", 3)?;
        s.serialize_field("type", type_)?;
        s.serialize_field("details", &details)?;
        s.serialize_field("message", &self.to_string())?;
        s.end()
    }
}

pub fn rename_mod(mod_: BD2Mod, new_name: String) -> Result<BD2Mod, ModRenameError> {
    let mod_path = mod_.path.clone();

    if new_name.trim().is_empty() {
        error!("Invalid mod name (empty): '{}'", new_name);
        return Err(ModRenameError::InvalidName {
            name: new_name,
            reason: "EMPTY_NAME".into(),
        });
    }

    if new_name.trim() == ".." {
        error!("Invalid mod name (..): '{}'", new_name);
        return Err(ModRenameError::InvalidName {
            name: new_name,
            reason: "DOT_DOT_NAME".into(),
        });
    }

    if let Some(bad_char) = new_name.trim().chars().find(|char| INVALID_NAME_CHARS.contains(char)) {
        error!("Invalid mod name (bad_char = {}): '{}'", bad_char, new_name);
        return Err(ModRenameError::InvalidName {
            name: new_name,
            reason: format!("INVALID_CHAR_{}", bad_char),
        });
    }

    let new_path = mod_path
        .parent()
        .unwrap_or_else(|| std::path::Path::new(""))
        .join(&new_name);

    debug!("Renaming mod {} ({:?}) to {:?}", mod_.name, mod_path, new_path);

    if new_path.exists() {
        error!("A mod with the new name already exists: {:?}", new_path);
        return Err(ModRenameError::ModAlreadyExists { mod_name: new_name });
    }

    if mod_path.exists() {
        if let Err(error) = std::fs::rename(&mod_path, &new_path) {
            error!(
                "Failed to rename mod from {:?} to {:?}: {:?}",
                mod_path, new_path, error
            );
            return Err(ModRenameError::Io(error));
        }
    } else {
        error!("Mod path does not exist: {:?}", mod_path);
        return Err(ModRenameError::PathNotFound {
            path: mod_path.to_string_lossy().to_string(),
        });
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
