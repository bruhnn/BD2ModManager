use log::info;
use serde::{Deserialize, Serialize};
use std::{fs::File, path::PathBuf};
use zip::ZipArchive;

use crate::utils::files::ensure_dir_exists;

// [TODO] merge NotAMod and MissingModFile
#[derive(thiserror::Error, Debug)]
pub enum ModInstallError {
    #[error("path '{path}' not found ")]
    PathNotFound {
        path: String,
        mod_name: Option<String>,
    },
    #[error("could not determine a mod name from path '{path}'")]
    InvalidName { path: String },
    #[error("a mod named '{mod_name}' already exists")]
    ModAlreadyExists { mod_name: String },
    #[error("the provided path '{path}' does not appear to be a valid mod")]
    NotAMod { path: String },
    #[error("unsupported archive format")]
    UnsupportedFormat,
    #[error("archive is corrupted or unreadable")]
    InvalidArchive,
    #[error("no .modfile found - this doesn't appear to be a valid mod")]
    MissingModFile,
    #[error("multiple mods found in the archive")]
    MultipleModsFound,
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error), // PermissionDenied, DiskFull, etc.
}

impl serde::Serialize for ModInstallError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        use serde::ser::SerializeStruct;
        use serde_json::json;

        let (type_, details): (String, Option<serde_json::Value>) = match self {
            // returns Io::PermissionDenied
            ModInstallError::Io(error) => ("Io".to_string(), Some(json!({ "kind": format!("{:?}", error.kind()) }))),
            ModInstallError::PathNotFound { path, mod_name } => ("PathNotFound".to_string(),Some(json!({ "path": path, "mod_name": mod_name }))),
            ModInstallError::InvalidName { path } => ("InvalidName".to_string(), Some(json!({ "path": path }))),
            ModInstallError::ModAlreadyExists { mod_name } => ("ModAlreadyExists".to_string(), Some(json!({ "mod_name": mod_name }))),
            ModInstallError::UnsupportedFormat => ("UnsupportedFormat".to_string(), None),
            ModInstallError::InvalidArchive => ("InvalidArchive".to_string(), None),
            ModInstallError::MissingModFile => ("MissingModFile".to_string(), None),
            ModInstallError::MultipleModsFound => ("MultipleModsFound".to_string(), None),
            ModInstallError::NotAMod { path } => ("NotAMod".to_string(), Some(json!({ "path": path })))
        };

        let mut s = serializer.serialize_struct("ModInstallError", 3)?;
        s.serialize_field("type", &type_)?;
        s.serialize_field("details", &details)?;
        s.serialize_field("message", &self.to_string())?;
        s.end()
    }
}

fn find_mod_root(archive: &mut ZipArchive<File>) -> Result<String, ModInstallError> {
    let mut mod_roots = Vec::new();

    for index in 0..archive.len() {
        let file = archive.by_index(index).map_err(|e| {
            error!("Failed to read zip entry: {:?}", e);
            ModInstallError::InvalidArchive
        })?;

        if file.name().ends_with(".modfile") {
            if let Some(path) = file.enclosed_name() {
                if let Some(parent) = path.parent() {
                    mod_roots.push(parent.to_string_lossy().to_string());
                } else {
                    mod_roots.push(String::new());
                }
            }
        }
    }

    if mod_roots.len() == 1 {
        Ok(mod_roots[0].clone())
    } else if mod_roots.len() > 1 {
        Err(ModInstallError::MultipleModsFound)
    } else {
        Err(ModInstallError::MissingModFile)
    }
}

/// Find the mod root inside an extracted temp directory by locating the .modfile
fn find_mod_root_in_dir(dir: &PathBuf) -> Result<PathBuf, ModInstallError> {
    let mut mod_roots = Vec::new();

    for entry in walkdir::WalkDir::new(dir) {
        let entry = entry.map_err(|e| {
            error!("Failed to walk extracted directory: {:?}", e);
            ModInstallError::InvalidArchive
        })?;
        if entry
            .path()
            .extension()
            .map_or(false, |ext| ext == "modfile")
        {
            if let Some(parent) = entry.path().parent() {
                mod_roots.push(parent.to_path_buf());
            }
        }
    }

    if mod_roots.len() == 1 {
        Ok(mod_roots[0].clone())
    } else if mod_roots.len() > 1 {
        Err(ModInstallError::MultipleModsFound)
    } else {
        Err(ModInstallError::MissingModFile)
    }
}

pub fn install_zip_mod(
    path: &PathBuf,
    staging_directory: &PathBuf,
) -> Result<PathBuf, ModInstallError> {
    info!("Installing mod from ZIP: {:?}", path);

    let mod_name = path
        .file_stem()
        .ok_or(ModInstallError::InvalidName {
            path: path.to_string_lossy().to_string(),
        })?
        .to_string_lossy()
        .to_string();

    let final_mod_folder = staging_directory.join(&mod_name);

    if final_mod_folder.exists() {
        return Err(ModInstallError::ModAlreadyExists {
            mod_name: mod_name.clone(),
        });
    }

    let file = File::open(path).map_err(|_| ModInstallError::PathNotFound {
        path: path.to_string_lossy().to_string(),
        mod_name: Some(mod_name.clone()),
    })?;

    let mut archive = ZipArchive::new(file).map_err(|e| {
        error!("Failed to open zip archive: {:?}", e);
        ModInstallError::InvalidArchive
    })?;
    let mod_root = find_mod_root(&mut archive)?;

    for i in 0..archive.len() {
        let mut file = archive.by_index(i).map_err(|e| {
            error!("Failed to read zip entry: {:?}", e);
            ModInstallError::InvalidArchive
        })?;

        if let Some(file_path) = file.enclosed_name() {
            let path_str = file_path.to_string_lossy();

            if !mod_root.is_empty() && !path_str.starts_with(&format!("{}/", mod_root)) {
                continue;
            }

            let output_path = if mod_root.is_empty() {
                final_mod_folder.join(file_path)
            } else if let Ok(relative) = file_path.strip_prefix(&mod_root) {
                final_mod_folder.join(relative.strip_prefix("/").unwrap_or(relative))
            } else {
                continue;
            };

            if file.is_dir() {
                ensure_dir_exists(&output_path)?;
            } else {
                if let Some(parent) = output_path.parent() {
                    ensure_dir_exists(&parent.to_path_buf())?;
                }
                let mut output_file = File::create(&output_path)?;
                std::io::copy(&mut file, &mut output_file)?;
            }
        }
    }

    Ok(final_mod_folder)
}

pub fn install_folder_mod(
    path: &PathBuf,
    staging_directory: &PathBuf,
) -> Result<PathBuf, ModInstallError> {
    // [FIXME] it currently doesn't check for .modfile in the folder, but it should
    // What to do:
    // A/B/mod.modfile -> move A/B to staging_dir
    // A/B/mod.modfile -> move A to staging_dir
    info!("Installing mod from folder: {:?}", path);

    if !path.exists() || !path.is_dir() {
        return Err(ModInstallError::PathNotFound {
            path: path.to_string_lossy().to_string(),
            mod_name: None,
        });
    }

    let mod_name = path
        .file_name()
        .ok_or(ModInstallError::InvalidName {
            path: path.to_string_lossy().to_string(),
        })?
        .to_string_lossy()
        .to_string();

    // check for multiple mods in the folder by looking for .modfile files
    find_mod_root_in_dir(path)?;

    let final_mod_folder = staging_directory.join(&mod_name);

    if final_mod_folder.exists() {
        return Err(ModInstallError::ModAlreadyExists {
            mod_name: mod_name.clone(),
        });
    }

    std::fs::create_dir_all(&final_mod_folder)?;

    for entry in walkdir::WalkDir::new(path) {
        let entry = entry.map_err(|e| {
            error!("Failed to walk source directory: {:?}", e);
            ModInstallError::Io(e.into())
        })?;
        let relative_path = entry.path().strip_prefix(path).unwrap();
        let output_path = final_mod_folder.join(relative_path);

        if entry.file_type().is_dir() {
            ensure_dir_exists(&output_path)?;
        } else {
            if let Some(parent) = output_path.parent() {
                ensure_dir_exists(&parent.to_path_buf())?;
            }
            std::fs::copy(entry.path(), &output_path)?;
        }
    }

    Ok(final_mod_folder)
}

pub fn install_7z_mod(
    path: &PathBuf,
    staging_directory: &PathBuf,
) -> Result<PathBuf, ModInstallError> {
    info!("Installing mod from 7z: {:?}", path);

    let mod_name = path
        .file_stem()
        .ok_or(ModInstallError::InvalidName {
            path: path.to_string_lossy().to_string(),
        })?
        .to_string_lossy()
        .to_string();

    let final_mod_folder = staging_directory.join(&mod_name);

    if final_mod_folder.exists() {
        return Err(ModInstallError::ModAlreadyExists {
            mod_name: mod_name.clone(),
        });
    }

    let temp_dir = staging_directory.join(format!(".tmp_{}", mod_name));
    std::fs::create_dir_all(&temp_dir)?;

    sevenz_rust2::decompress_file(path, &temp_dir).map_err(|e| {
        error!("7z extraction failed: {:?}", e);
        let _ = std::fs::remove_dir_all(&temp_dir);
        ModInstallError::InvalidArchive
    })?;

    let mod_root = match find_mod_root_in_dir(&temp_dir) {
        Ok(root) => root,
        Err(e) => {
            let _ = std::fs::remove_dir_all(&temp_dir);
            return Err(e);
        }
    };

    if let Err(e) = std::fs::create_dir_all(&final_mod_folder) {
        let _ = std::fs::remove_dir_all(&temp_dir);
        return Err(ModInstallError::Io(e));
    }

    for entry in walkdir::WalkDir::new(&mod_root) {
        let entry = match entry {
            Ok(entry) => entry,
            Err(error) => {
                error!("Failed to walk extracted directory: {:?}", error);
                let _ = std::fs::remove_dir_all(&temp_dir);
                return Err(ModInstallError::Io(error.into()));
            }
        };

        // NOTE: strip the discovered mod_root, not the original archive path -
        // entry.path() lives under temp_dir/mod_root, never under the archive file itself.
        let relative_path = entry.path().strip_prefix(&mod_root).unwrap();

        let output_path = final_mod_folder.join(relative_path);

        let result = (|| -> Result<(), std::io::Error> {
            if entry.file_type().is_dir() {
                ensure_dir_exists(&output_path)?;
            } else {
                if let Some(parent) = output_path.parent() {
                    ensure_dir_exists(&parent.to_path_buf())?;
                }
                std::fs::copy(entry.path(), &output_path)?;
            }
            Ok(())
        })();

        if let Err(e) = result {
            let _ = std::fs::remove_dir_all(&temp_dir);
            return Err(ModInstallError::Io(e));
        }
    }

    let _ = std::fs::remove_dir_all(&temp_dir);
    Ok(final_mod_folder)
}

pub fn install_rar_mod(
    path: &PathBuf,
    staging_directory: &PathBuf,
) -> Result<PathBuf, ModInstallError> {
    info!("Installing mod from RAR: {:?}", path);

    let mod_name = path
        .file_stem()
        .ok_or(ModInstallError::InvalidName {
            path: path.to_string_lossy().to_string(),
        })?
        .to_string_lossy()
        .to_string();

    let final_mod_folder = staging_directory.join(&mod_name);
    if final_mod_folder.exists() {
        return Err(ModInstallError::ModAlreadyExists {
            mod_name: mod_name.clone(),
        });
    }

    let temp_dir = staging_directory.join(format!(".tmp_{}", mod_name));
    std::fs::create_dir_all(&temp_dir)?;

    let extract_result = (|| -> Result<(), ModInstallError> {
        let mut archive = unrar::Archive::new(path)
            .open_for_processing()
            .map_err(|e| {
                error!("Failed to open RAR: {:?}", e);
                ModInstallError::InvalidArchive
            })?;

        loop {
            match archive.read_header() {
                Ok(Some(header)) => {
                    archive = header.extract_with_base(&temp_dir).map_err(|e| {
                        error!("Failed to extract RAR entry: {:?}", e);
                        ModInstallError::InvalidArchive
                    })?;
                }
                Ok(None) => break,
                Err(e) => {
                    error!("Failed to read RAR header: {:?}", e);
                    return Err(ModInstallError::InvalidArchive);
                }
            }
        }

        Ok(())
    })();

    if let Err(e) = extract_result {
        let _ = std::fs::remove_dir_all(&temp_dir);
        return Err(e);
    }

    let mod_root = match find_mod_root_in_dir(&temp_dir) {
        Ok(root) => root,
        Err(e) => {
            let _ = std::fs::remove_dir_all(&temp_dir);
            return Err(e);
        }
    };

    if let Err(e) = std::fs::create_dir_all(&final_mod_folder) {
        let _ = std::fs::remove_dir_all(&temp_dir);
        return Err(ModInstallError::Io(e));
    }

    for entry in walkdir::WalkDir::new(&mod_root) {
        let entry = match entry {
            Ok(entry) => entry,
            Err(error) => {
                error!("Failed to walk extracted directory: {:?}", error);
                let _ = std::fs::remove_dir_all(&temp_dir);
                return Err(ModInstallError::Io(error.into()));
            }
        };

        // NOTE: strip the discovered mod_root, not the original archive path -
        // entry.path() lives under temp_dir/mod_root, never under the archive file itself.
        let relative_path = entry.path().strip_prefix(&mod_root).unwrap();

        let output_path = final_mod_folder.join(relative_path);

        let result = (|| -> Result<(), std::io::Error> {
            if entry.file_type().is_dir() {
                ensure_dir_exists(&output_path)?;
            } else {
                if let Some(parent) = output_path.parent() {
                    ensure_dir_exists(&parent.to_path_buf())?;
                }
                std::fs::copy(entry.path(), &output_path)?;
            }
            Ok(())
        })();

        if let Err(e) = result {
            let _ = std::fs::remove_dir_all(&temp_dir);
            return Err(ModInstallError::Io(e));
        }
    }

    let _ = std::fs::remove_dir_all(&temp_dir);
    Ok(final_mod_folder)
}

pub fn install_mod(
    path: &PathBuf,
    staging_directory: &PathBuf,
) -> Result<PathBuf, ModInstallError> {
    // [TODO] add more error variants
    // PermissionDenied, DiskFull, etc.
    if !path.exists() {
        return Err(ModInstallError::PathNotFound {
            path: path.to_string_lossy().to_string(),
            mod_name: None,
        });
    }

    if path.is_dir() {
        return install_folder_mod(path, staging_directory);
    }

    let ext = path
        .extension()
        .map(|e| e.to_string_lossy().to_lowercase())
        .unwrap_or_default();

    match ext.as_str() {
        "rar" => install_rar_mod(path, staging_directory),
        "zip" => install_zip_mod(path, staging_directory),
        "7z" => install_7z_mod(path, staging_directory),
        _ => Err(ModInstallError::UnsupportedFormat),
    }
}
