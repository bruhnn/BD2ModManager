use log::info;
use serde::{Deserialize, Serialize};
use std::{fs::File, path::PathBuf};
use zip::ZipArchive;

use crate::utils::files::ensure_dir_exists;

#[derive(thiserror::Error, Debug, Serialize, Deserialize)]
pub enum ModInstallError {
    #[error("path not found: {path}")]
    PathNotFound { path: String },
    #[error("invalid mod name")]
    InvalidName,
    #[error("invalid archive format")]
    InvalidFormat,
    #[error("mod already exists")]
    ModAlreadyExists,
    #[error("invalid mod")]
    InvalidMod,
    #[error("multiple mods found in archive")]
    MultipleModsFound,
    #[error("unsupported archive format")]
    UnsupportedFormat,
}

fn find_mod_root(archive: &mut ZipArchive<File>) -> Result<String, ModInstallError> {
    let mut mod_roots = Vec::new();

    for index in 0..archive.len() {
        let file = archive
            .by_index(index)
            .map_err(|_| ModInstallError::InvalidFormat)?;
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
        Err(ModInstallError::InvalidMod)
    }
}

/// Find the mod root inside an extracted temp directory by locating the .modfile
fn find_mod_root_in_dir(dir: &PathBuf) -> Result<PathBuf, ModInstallError> {
    let mut mod_roots = Vec::new();

    for entry in walkdir::WalkDir::new(dir) {
        let entry = entry.map_err(|_| ModInstallError::InvalidFormat)?;
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
        Err(ModInstallError::InvalidMod)
    }
}

pub fn install_zip_mod(
    path: &PathBuf,
    staging_directory: &PathBuf,
) -> Result<PathBuf, ModInstallError> {
    info!("Installing mod from ZIP: {:?}", path);

    let mod_name = path
        .file_stem()
        .ok_or(ModInstallError::InvalidName)?
        .to_string_lossy()
        .to_string();

    let final_mod_folder = staging_directory.join(&mod_name);
    if final_mod_folder.exists() {
        return Err(ModInstallError::ModAlreadyExists);
    }

    let file = File::open(path).map_err(|_| ModInstallError::PathNotFound {
        path: path.to_string_lossy().to_string(),
    })?;

    let mut archive = ZipArchive::new(file).map_err(|_| ModInstallError::InvalidFormat)?;
    let mod_root = find_mod_root(&mut archive)?;

    for i in 0..archive.len() {
        let mut file = archive
            .by_index(i)
            .map_err(|_| ModInstallError::InvalidFormat)?;

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
                ensure_dir_exists(&output_path).map_err(|_| ModInstallError::InvalidFormat)?;
            } else {
                if let Some(parent) = output_path.parent() {
                    ensure_dir_exists(&parent.to_path_buf())
                        .map_err(|_| ModInstallError::InvalidFormat)?;
                }
                let mut output_file =
                    File::create(&output_path).map_err(|_| ModInstallError::InvalidFormat)?;
                std::io::copy(&mut file, &mut output_file)
                    .map_err(|_| ModInstallError::InvalidFormat)?;
            }
        }
    }

    Ok(final_mod_folder)
}

pub fn install_folder_mod(
    path: &PathBuf,
    staging_directory: &PathBuf,
) -> Result<PathBuf, ModInstallError> {
    info!("Installing mod from folder: {:?}", path);

    if !path.exists() || !path.is_dir() {
        return Err(ModInstallError::PathNotFound {
            path: path.to_string_lossy().to_string(),
        });
    }

    let mod_name = path
        .file_name()
        .ok_or(ModInstallError::InvalidName)?
        .to_string_lossy()
        .to_string();

    let final_mod_folder = staging_directory.join(&mod_name);

    if final_mod_folder.exists() {
        return Err(ModInstallError::ModAlreadyExists);
    }

    std::fs::create_dir_all(&final_mod_folder).map_err(|_| ModInstallError::InvalidFormat)?;

    for entry in walkdir::WalkDir::new(path) {
        let entry = entry.map_err(|_| ModInstallError::InvalidFormat)?;
        let relative_path = entry
            .path()
            .strip_prefix(path)
            .map_err(|_| ModInstallError::InvalidFormat)?;
        let output_path = final_mod_folder.join(relative_path);

        if entry.file_type().is_dir() {
            ensure_dir_exists(&output_path).map_err(|_| ModInstallError::InvalidFormat)?;
        } else {
            if let Some(parent) = output_path.parent() {
                ensure_dir_exists(&parent.to_path_buf())
                    .map_err(|_| ModInstallError::InvalidFormat)?;
            }
            std::fs::copy(entry.path(), &output_path)
                .map_err(|_| ModInstallError::InvalidFormat)?;
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
        .ok_or(ModInstallError::InvalidName)?
        .to_string_lossy()
        .to_string();

    let final_mod_folder = staging_directory.join(&mod_name);
    if final_mod_folder.exists() {
        return Err(ModInstallError::ModAlreadyExists);
    }

    let temp_dir = staging_directory.join(format!(".tmp_{}", mod_name));
    std::fs::create_dir_all(&temp_dir).map_err(|_| ModInstallError::InvalidFormat)?;

    sevenz_rust2::decompress_file(path, &temp_dir).map_err(|e| {
        log::error!("7z extraction failed: {:?}", e);
        let _ = std::fs::remove_dir_all(&temp_dir);
        ModInstallError::InvalidFormat
    })?;

    let mod_root = match find_mod_root_in_dir(&temp_dir) {
        Ok(root) => root,
        Err(e) => {
            let _ = std::fs::remove_dir_all(&temp_dir);
            return Err(e);
        }
    };

    std::fs::create_dir_all(&final_mod_folder).map_err(|_| {
        let _ = std::fs::remove_dir_all(&temp_dir);
        ModInstallError::InvalidFormat
    })?;

    for entry in walkdir::WalkDir::new(&mod_root) {
        let entry = match entry {
            Ok(e) => e,
            Err(_) => {
                let _ = std::fs::remove_dir_all(&temp_dir);
                return Err(ModInstallError::InvalidFormat);
            }
        };

        let relative_path = entry
            .path()
            .strip_prefix(&mod_root)
            .map_err(|_| ModInstallError::InvalidFormat)?;

        let output_path = final_mod_folder.join(relative_path);

        if entry.file_type().is_dir() {
            ensure_dir_exists(&output_path).map_err(|_| ModInstallError::InvalidFormat)?;
        } else {
            if let Some(parent) = output_path.parent() {
                ensure_dir_exists(&parent.to_path_buf())
                    .map_err(|_| ModInstallError::InvalidFormat)?;
            }
            std::fs::copy(entry.path(), &output_path)
                .map_err(|_| ModInstallError::InvalidFormat)?;
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
        .ok_or(ModInstallError::InvalidName)?
        .to_string_lossy()
        .to_string();

    let final_mod_folder = staging_directory.join(&mod_name);
    if final_mod_folder.exists() {
        return Err(ModInstallError::ModAlreadyExists);
    }

    let temp_dir = staging_directory.join(format!(".tmp_{}", mod_name));
    std::fs::create_dir_all(&temp_dir).map_err(|_| ModInstallError::InvalidFormat)?;

    let extract_result = (|| -> Result<(), ModInstallError> {
        let mut archive = unrar::Archive::new(path)
            .open_for_processing()
            .map_err(|e| {
                log::error!("Failed to open RAR: {:?}", e);
                ModInstallError::InvalidFormat
            })?;

        loop {
            match archive.read_header() {
                Ok(Some(header)) => {
                    archive = header.extract_with_base(&temp_dir).map_err(|e| {
                        log::error!("Failed to extract RAR entry: {:?}", e);
                        ModInstallError::InvalidFormat
                    })?;
                }
                Ok(None) => break,
                Err(e) => {
                    log::error!("Failed to read RAR header: {:?}", e);
                    return Err(ModInstallError::InvalidFormat);
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

    std::fs::create_dir_all(&final_mod_folder).map_err(|_| {
        let _ = std::fs::remove_dir_all(&temp_dir);
        ModInstallError::InvalidFormat
    })?;

    for entry in walkdir::WalkDir::new(&mod_root) {
        let entry = match entry {
            Ok(e) => e,
            Err(_) => {
                let _ = std::fs::remove_dir_all(&temp_dir);
                return Err(ModInstallError::InvalidFormat);
            }
        };

        let relative_path = entry
            .path()
            .strip_prefix(&mod_root)
            .map_err(|_| ModInstallError::InvalidFormat)?;

        let output_path = final_mod_folder.join(relative_path);

        if entry.file_type().is_dir() {
            ensure_dir_exists(&output_path).map_err(|_| ModInstallError::InvalidFormat)?;
        } else {
            if let Some(parent) = output_path.parent() {
                ensure_dir_exists(&parent.to_path_buf())
                    .map_err(|_| ModInstallError::InvalidFormat)?;
            }
            std::fs::copy(entry.path(), &output_path)
                .map_err(|_| ModInstallError::InvalidFormat)?;
        }
    }

    let _ = std::fs::remove_dir_all(&temp_dir);
    Ok(final_mod_folder)
}

pub fn install_mod(
    path: &PathBuf,
    staging_directory: &PathBuf,
) -> Result<PathBuf, ModInstallError> {
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
