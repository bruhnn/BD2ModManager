use std::path::PathBuf;

use crate::{mods::BD2Mod};
use log::{debug, error};

#[derive(thiserror::Error, Debug)]
pub enum ModDeleteError {
    #[error("Mod not found")]
    ModNotFound { mod_name: String },
    #[error("The path was not found")]
    PathNotFound { path: String },
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error), // PermissionDenied, OS errors, etc
}

impl serde::Serialize for ModDeleteError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        use serde::ser::SerializeStruct;
        use serde_json::json;

        let (type_, details): (&str, Option<serde_json::Value>) = match self {
            ModDeleteError::ModNotFound { mod_name } => (
                "ModNotFound",
                Some(json!({ "mod_name": mod_name })),
            ),
            ModDeleteError::PathNotFound { path } => (
                "PathNotFound",
                Some(json!({ "path": path })),
            ),
            ModDeleteError::Io(error) => (
                "Io",
                Some(json!({ "kind": format!("{:?}", error.kind()) })),
            ),
        };

        let mut s = serializer.serialize_struct("ModDeleteError", 3)?;
        s.serialize_field("type", type_)?;
        s.serialize_field("details", &details)?;
        s.serialize_field("message", &self.to_string())?;
        s.end()
    }
}

pub fn delete_mod(mod_: &BD2Mod) -> Result<(), ModDeleteError> {
    let mod_path = mod_.path.clone();
    // to get staging_dir only works on subfolders because BD2Mod.name has the its subfolders in it.
    // Ex. test/mod_name
    let relative_path = PathBuf::from(&mod_.name);
    let staging_dir = mod_path
    .ancestors()
    .nth(relative_path.components().count())
    .map(|p| p.to_path_buf()).filter(|p| p.exists())
    .ok_or_else(|| {
        error!("Could not determine staging directory for mod: {:?}", mod_);
        ModDeleteError::ModNotFound { mod_name: mod_.name.clone() }
    })?;
    debug!("Deleting mod: {:?}", mod_); 

    if !mod_path.exists() {
        error!("Mod path does not exist: {:?}", mod_path);
        // FailedToDelete or NotFound? because the mod is not found in the filesystem, but it is found in the mod manager
        return Err(ModDeleteError::PathNotFound { path: mod_.name.clone() })?;
    }

    if mod_path.is_dir() {
        std::fs::remove_dir_all(&mod_path).map_err(|e| {
            error!("Failed to delete mod directory: {:?}, error: {:?}", mod_path, e);
            ModDeleteError::Io(e.into())
        })?;
    } else {
        std::fs::remove_file(&mod_path).map_err(|e| {
            error!("Failed to delete mod file: {:?}, error: {:?}", mod_path, e);
            ModDeleteError::Io(e.into())
        })?;
    }

    // remove subfolders in staging_dir if they are empty
    let mut current_path = mod_path.parent();
    while let Some(path) = current_path {
        if path == staging_dir {
            break;
        }
        if path.read_dir().map(|mut i| i.next().is_none()).unwrap_or(false) {
            std::fs::remove_dir(path).map_err(|e| {
                error!("Failed to delete empty directory: {:?}, error: {:?}", path, e);
                ModDeleteError::Io(e.into())
            })?;
        } else {
            break;
        }
        current_path = path.parent();
    }

    Ok(())
}
