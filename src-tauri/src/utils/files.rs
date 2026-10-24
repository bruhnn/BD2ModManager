use std::{
    fs::{self, copy, create_dir_all, read, read_dir},
    io,
    path::{Path, PathBuf},
};

use sha2::{Digest, Sha256};
use walkdir::WalkDir;
use std::time::SystemTime;
use std::os::windows::fs::MetadataExt;
use std::os::windows::ffi::OsStrExt;
use windows_sys::Win32::Storage::FileSystem::GetDiskFreeSpaceExW;

use crate::mods::{install::ModInstallError, sync::ModSyncError};

pub fn has_extension(path: &Path, extensions: &[&str]) -> bool {
    if let Some(ext) = path.extension() {
        if let Some(ext_str) = ext.to_str() {
            return extensions.iter().any(|e| e.eq_ignore_ascii_case(ext_str));
        }
    }
    false
}

pub fn is_archive(path: &Path) -> bool {
    let archive_exts = ["zip", "rar", "7z", "tar", "gz", "bz2", "xz"];
    has_extension(path, &archive_exts)
}

pub fn is_image(path: &Path) -> bool {
    let image_exts = ["png", "jpg", "jpeg"];
    has_extension(path, &image_exts)
}

pub fn has_folder(folder: &Path, name: &str) -> bool {
    if let Ok(entries) = read_dir(folder) {
        for entry in entries.flatten() {
            let path = entry.path();

            if path.is_dir() {
                if let Some(filename) = path.file_name() {
                    if filename == name {
                        return true;
                    }
                }
            }
        }
    }
    return false;
}

pub fn copy_dir_all(src: &Path, dst: &Path) -> Result<(), ModInstallError> {
    let metadata = fs::symlink_metadata(src)?;

    // FILE_ATTRIBUTE_REPARSE_POINT
    if metadata.file_attributes() & 0x400 != 0 {
        return Err(ModInstallError::ModContainsSymlink {
            path: src.to_string_lossy().to_string(),
        });
    }

    if !dst.exists() {
        create_dir_all(dst)?;
    }

    for entry in read_dir(src)? {
        let entry = entry?;
        let entry_path = entry.path();
        let dest_path = dst.join(entry.file_name());

        let metadata = fs::symlink_metadata(&entry_path)?;

        if metadata.file_attributes() & 0x400 != 0 {
            return Err(ModInstallError::ModContainsSymlink {
                path: entry_path.to_string_lossy().to_string(),
            });
        }

        if metadata.is_dir() {
            copy_dir_all(&entry_path, &dest_path)?;
        } else {
            copy(&entry_path, &dest_path)?;
        }
    }

    Ok(())
}

pub fn dirs_match(src: &Path, dst: &Path) -> Result<bool, ModSyncError> {
    let source = fs::symlink_metadata(src)?;
    if source.file_attributes() & 0x400 != 0 {
        return Err(ModSyncError::ModContainsSymlink {
            path: src.to_string_lossy().to_string(),
        });
    }
    let destination = match fs::symlink_metadata(dst) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(false),
        Err(error) => return Err(error.into()),
    };
    if destination.file_attributes() & 0x400 != 0 || source.is_dir() != destination.is_dir() {
        return Ok(false);
    }
    if !source.is_dir() {
        return Ok(source.len() == destination.len() && source.modified()? == destination.modified()?);
    }

    for entry in read_dir(src)? {
        let entry = entry?;
        if !dirs_match(&entry.path(), &dst.join(entry.file_name()))? {
            return Ok(false);
        }
    }
    for entry in read_dir(dst)? {
        let entry = entry?;
        match fs::symlink_metadata(src.join(entry.file_name())) {
            Ok(_) => {},
            Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(false),
            Err(error) => return Err(error.into()),
        }
    }
    Ok(true)
}

pub fn sync_dirs(src: &Path, dst: &Path) -> Result<bool, ModSyncError> {
    let metadata = fs::symlink_metadata(src)?;

    // FILE_ATTRIBUTE_REPARSE_POINT
    if metadata.file_attributes() & 0x400 != 0 {
        return Err(ModSyncError::ModContainsSymlink {
            path: src.to_string_lossy().to_string(),
        });
    }

    let mut updated = false;

    let source = PathBuf::from(src.canonicalize()?.to_string_lossy().to_lowercase());
    let parent = dst.ancestors().skip(1).find(|parent| parent.exists()).ok_or_else(|| {
        io::Error::new(io::ErrorKind::NotFound, "Destination parent was not found")
    })?;
    let destination = PathBuf::from(parent.canonicalize()?.join(dst.strip_prefix(parent).unwrap()).to_string_lossy().to_lowercase());
    if source.starts_with(&destination) || destination.starts_with(&source) {
        return Err(ModSyncError::DirectoriesNested);
    }
    match fs::symlink_metadata(dst) {
        Ok(metadata) if metadata.file_attributes() & 0x400 != 0 || !metadata.is_dir() => {
            crate::mods::sync::remove_mod_path(dst)?;
            updated = true;
        }
        Ok(_) => {},
        Err(error) if error.kind() == io::ErrorKind::NotFound => {},
        Err(error) => return Err(error.into()),
    }

    if !dst.exists() {
        create_dir_all(dst)?;
        updated = true;
    }

    // Copy/update files from src too dst
    for entry in read_dir(src)? {
        let entry = entry?;
        let src_path = entry.path();
        let dst_path = dst.join(entry.file_name());

        let metadata = fs::symlink_metadata(&src_path)?;

        if metadata.file_attributes() & 0x400 != 0 {
            return Err(ModSyncError::ModContainsSymlink {
                path: src_path.to_string_lossy().to_string(),
            });
        }

        if metadata.is_dir() {
            if sync_dirs(&src_path, &dst_path)? {
                updated = true;
            }
        } else {
            match fs::symlink_metadata(&dst_path) {
                Ok(metadata) if metadata.file_attributes() & 0x400 != 0 || metadata.is_dir() => {
                    crate::mods::sync::remove_mod_path(&dst_path)?;
                    updated = true;
                }
                Ok(_) => {},
                Err(error) if error.kind() == io::ErrorKind::NotFound => {},
                Err(error) => return Err(error.into()),
            }
            let needs_copy = if dst_path.exists() {
                let src_meta = src_path.metadata()?;
                let dst_meta = dst_path.metadata()?;

                src_meta.len() != dst_meta.len()
                    || src_meta.modified().unwrap_or(SystemTime::UNIX_EPOCH)
                        != dst_meta.modified().unwrap_or(SystemTime::UNIX_EPOCH)
            } else {
                true
            };

            if needs_copy {
                copy(&src_path, &dst_path)?;
                updated = true;
            }
        }
    }

    //  Remove files from dst that don’t exist in src
    for entry in read_dir(dst)? {
        let entry = entry?;
        let dst_path = entry.path();
        let src_path = src.join(entry.file_name());

        if !src_path.exists() {
            crate::mods::sync::remove_mod_path(&dst_path)?;
            updated = true;
        }
    }

    Ok(updated)
}

pub fn hash_directory<P: AsRef<Path>>(dir: P) -> io::Result<String> {
    let mut hasher = Sha256::new();

    let entries: Vec<_> = WalkDir::new(&dir)
        .sort_by_file_name()
        .into_iter()
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| io::Error::new(io::ErrorKind::Other, e))?;

    for entry in entries {
        if entry.file_type().is_file() {
            if let Ok(relative_path) = entry.path().strip_prefix(&dir) {
                hasher.update(relative_path.to_string_lossy().as_bytes());
            }

            let contents = read(entry.path())?;
            hasher.update(&contents);
        }
    }

    Ok(format!("{:x}", hasher.finalize()))
}

pub fn ensure_dir_exists(path: &PathBuf) -> Result<(), std::io::Error> {
    if !path.exists() {
        std::fs::create_dir_all(path)?;
    }
    Ok(())
}

pub fn cleanup_empty_dirs(game_path: &PathBuf, file_list: &[String]) {
    let mut dirs: Vec<PathBuf> = Vec::new();
    for f in file_list {
        let full = game_path.join(f);
        let mut current = full.parent().map(|p| p.to_path_buf());
        while let Some(dir) = current {
            if !dir.starts_with(game_path) || dir == *game_path {
                break;
            }
            dirs.push(dir.clone());
            current = dir.parent().map(|p| p.to_path_buf());
        }
    }
    dirs.sort();
    dirs.dedup();
    dirs.sort_by(|a, b| b.components().count().cmp(&a.components().count()));

    for dir in &dirs {
        if dir.exists() && dir.is_dir() {
            let _ = fs::remove_dir(dir);
        }
    }
}


pub fn get_available_size(path: &PathBuf) -> Result<u64, std::io::Error> {
    let path: Vec<u16> = path
    .as_os_str()
    .encode_wide()
    .chain(std::iter::once(0))
    .collect();

    let mut available_space: u64 = 0;

    let result = unsafe {
        GetDiskFreeSpaceExW(
            path.as_ptr(),
            &mut available_space,
            std::ptr::null_mut(),
            std::ptr::null_mut(),
        )
    };

    if result == 0 {
        return Err(std::io::Error::last_os_error().into());
    }

    Ok(available_space)
}

pub fn get_directory_size(path: &PathBuf) -> Result<u64, std::io::Error> {
    let mut size = 0u64;

    for entry in WalkDir::new(path).follow_links(false) {
        let entry = entry.map_err(std::io::Error::from)?;

        if entry.file_type().is_file() {
            size += entry.metadata().map_err(std::io::Error::from)?.len();
        }
    }

    Ok(size)
}

pub fn get_file_size(path: &PathBuf) -> Result<u64, std::io::Error> {
    let size = fs::metadata(path)?.len();
    Ok(size)
}