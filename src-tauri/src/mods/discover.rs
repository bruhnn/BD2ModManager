use log::{debug, info, warn};
use rayon::prelude::*;
use walkdir::WalkDir;
use std::{
    collections::HashMap, ffi::OsStr, fs::{self, read_dir}, path::Path, sync::Arc, time::Instant,
};

use crate::{
    mods::{BD2Mod, sync::load_manifest, types::BD2ModError, utils::{game_folder_name, get_mod_type}}, utils::{files::has_extension, is_archive},
};


const MAX_DEPTH: usize = 15;

static MOD_EXTENSIONS: &[&str] = &["png", "modfile", "atlas", "skel", "json"];

#[derive(Debug, Default)]
struct ModAnalysis {
    has_modfile: bool,
    has_images: bool,
    has_skel: bool,
    has_atlas: bool,
    has_textures_folder: bool,
}

fn is_textures_folder(path: &Path) -> bool {
    path.file_name()
        .and_then(OsStr::to_str)
        .map(|name| name.to_ascii_lowercase() == "textures")
        .unwrap_or(false)
}

impl ModAnalysis {
    fn analyze_entry(&mut self, entry: &fs::DirEntry) {
        let path = entry.path();

        if path.is_file() {
            if let Some(ext) = path.extension().and_then(OsStr::to_str) {
                match ext.to_ascii_lowercase().as_str() {
                    "modfile" => self.has_modfile = true,
                    "png" => self.has_images = true,
                    "skel" | "json" => self.has_skel = true,
                    "atlas" => self.has_atlas = true,
                    _ => {}
                }
            }
        } else if path.is_dir() {
            if is_textures_folder(&path) {
                self.has_textures_folder = true;
            }
        }
    }

    fn determine_mod_status(&self) -> (bool, Option<BD2ModError>) {
        let is_mod = self.has_modfile
            || self.has_skel
            || self.has_atlas
            || self.has_textures_folder;

        if !is_mod {
            debug!("No mod related files found in the directory.");
            return (false, None);
        }

        if !self.has_modfile {
            return (true, Some(BD2ModError::MissingModfile));
        }

        if self.has_skel && !self.has_atlas {
            return (true, Some(BD2ModError::MissingAtlasFile));
        }

        if !self.has_images && !self.has_textures_folder {
            return (true, Some(BD2ModError::MissingTextures));
        }

        (true, None)
    }
}

pub fn analyze_mod_path(path: &Path) -> (bool, Option<BD2ModError>) {
    if path.is_file() {
        return if is_archive(path) {
            (true, Some(BD2ModError::ArchiveNotExtracted))
        } else if has_extension(path, MOD_EXTENSIONS) {
            (true, Some(BD2ModError::ShouldBeInFolder))
        } else {
            (false, None)
        };
    }

    let mut analysis = ModAnalysis::default();

    match read_dir(path) {
        Ok(entries) => {
            entries
                .filter_map(|e| {
                    e.map_err(|err| warn!("Failed to read entry in {:?}: {}", path, err))
                        .ok()
                })
                .for_each(|entry| analysis.analyze_entry(&entry));
        }
        Err(e) => {
            warn!("Failed to read directory {:?}: {}", path, e);
        }
    }

    analysis.determine_mod_status()
}

pub fn create_mod(staging_directory: &Path, path: &Path, error: Option<BD2ModError>) -> BD2Mod {
    // normalize names from 'parent\mod' to 'parent/mod'
    let full_name = path
        .strip_prefix(staging_directory)
        .unwrap_or(path)
        .to_string_lossy()
        .replace("\\", "/");

    let display_name = path
        .file_name()
        .map(|name| name.to_string_lossy().into_owned())
        .unwrap_or_else(|| "unknown".to_string());


    BD2Mod {
        path: path.to_path_buf(),
        name: full_name,
        display_name,
        mod_type: get_mod_type(path),
        errors: error.into_iter().collect(),
        ..Default::default()
    }
}

fn discover_mods_recursive(dir: &Path, staging_directory: &Path, depth: usize) -> Vec<BD2Mod> {
    if depth >= MAX_DEPTH {
        warn!(
            "Max depth ({}) reached at {:?}, stopping recursion",
            MAX_DEPTH, dir
        );
        return Vec::new();
    }

    let staging_dir = Arc::new(staging_directory.to_path_buf());

    match fs::read_dir(dir) {
        Ok(entries) => entries
            .filter_map(|e| {
                e.map_err(|err| warn!("Failed to read entry in {:?}: {}", dir, err))
                    .ok()
            })
            .par_bridge()
            .filter(|entry| !is_textures_folder(&entry.path()))
            .flat_map(|entry| {
                let path = entry.path();
                let (is_mod, error) = analyze_mod_path(&path);
                debug!("(is_mod = {:?}) {:?} -> error = {:?}", is_mod, path, error);
                if is_mod {
                    vec![create_mod(&staging_dir, &path, error)]
                } else if path.is_dir() {
                    discover_mods_recursive(&path, &staging_dir, depth + 1)
                } else {
                    warn!("Path {:?} not valid! {:?}", path, error);
                    Vec::new()
                }
            })
            .collect(),
        Err(e) => {
            warn!("Failed to read directory {:?}: {}", dir, e);
            Vec::new()
        }
    }
}

pub fn discover_staging_mods(staging_directory: &Path, recursive: bool) -> Vec<BD2Mod> {
    let start: Instant = Instant::now();

    let mods: Vec<BD2Mod> = if recursive {
        discover_mods_recursive(staging_directory, staging_directory, 0)
    } else {
        match fs::read_dir(staging_directory) {
            Ok(entries) => entries
                .filter_map(|e| {
                    e.map_err(|err| {
                        warn!("Failed to read entry in {:?}: {}", staging_directory, err)
                    })
                    .ok()
                })
                .par_bridge()
                .filter_map(|entry| {
                    let path = entry.path();
                    let (is_mod, error) = analyze_mod_path(&path);
                    debug!("(is_mod = {:?}) {:?} -> error = {:?}", is_mod, path, error);
                    if is_mod {
                        Some(create_mod(staging_directory, &path, error))
                    } else {
                        None
                    }
                })
                .collect(),
            Err(e) => {
                warn!(
                    "Failed to read staging directory {:?}: {}",
                    staging_directory, e
                );
                Vec::new()
            }
        }
    };

    info!("discover_staging_mods() took {:?}", start.elapsed());
    mods
}


pub fn discover_unmanaged_mods(game_directory: &Path, staging_mods: &mut [BD2Mod]) -> Vec<BD2Mod> {
    let manifest_path = game_directory.join(".bd2mm.json");

    let manifest = match load_manifest(&manifest_path) {
        Ok(manifest) => manifest,
        Err(error) => {
            warn!("Failed to load manifest: {}", error);
            return Vec::new();
        }
    };

    let game_mods_path =
        game_directory.join("BepInEx/plugins/BrownDustX/mods");

    // staging mods by the folder name they get in the game
    let staging_by_folder: HashMap<String, usize> = staging_mods
        .iter()
        .enumerate()
        .map(|(index, m)| (game_folder_name(&m.name).to_lowercase(), index))
        .collect();
    
    let mut mods_unmanaged = Vec::new();

    let mut entries = WalkDir::new(&game_mods_path)
        .follow_links(false)
        .min_depth(1)
        .into_iter();

    while let Some(entry) = entries.next() {
        let Ok(entry) = entry else {
            continue;
        };

        let path = entry.path().to_path_buf();

        let relative = path
            .strip_prefix(&game_mods_path)
            .unwrap_or(&path)
            .to_string_lossy()
            .replace('\\', "/");

        let is_managed = manifest.as_ref().is_some_and(|manifest| {
            manifest.synced_mods.iter().any(|mod_entry| {
                let managed_path = format!("BD2MM/{}", mod_entry.game_folder.replace('\\', "/"));
                managed_path.eq_ignore_ascii_case(&relative)
            })
        });

        if is_managed {
            if entry.file_type().is_dir() {
                entries.skip_current_dir();
            }

            continue;
        }
        if entry.file_type().is_dir() || entry.file_type().is_symlink() {
            let staging_index = relative
                .split_once('/')
                .filter(|(root, _)| root.eq_ignore_ascii_case("BD2MM"))
                .and_then(|(_, folder)| staging_by_folder.get(&folder.to_lowercase()))
                .copied();

            if let Some(index) = staging_index {
                let errors = &mut staging_mods[index].errors;
                if !errors.iter().any(|e| matches!(e, BD2ModError::UnmanagedButInStaging)) {
                    errors.insert(0, BD2ModError::UnmanagedButInStaging);
                }
                if entry.file_type().is_dir() {
                    entries.skip_current_dir();
                }
                continue;
            }
        }

        if entry.file_type().is_symlink() {
            let (is_mod, error) = analyze_mod_path(&path);

            if is_mod {
                let mut _mod = create_mod(&game_mods_path, &path, error);
                _mod.name = format!("BD2MMUnmanaged/{}", _mod.name);
                _mod.errors.insert(0, BD2ModError::Unmanaged);
                mods_unmanaged.push(_mod);
            }
            continue;
        }

        if !entry.file_type().is_dir() {
            continue;
        }

        let (is_mod, error) = analyze_mod_path(&path);

        if is_mod {
            let mut _mod = create_mod(
                &game_mods_path,
                &path,
                error,
            );
            // we add a new namespce just to not collide with staging with the same name
            _mod.name = format!("BD2MMUnmanaged/{}", _mod.name);
            _mod.errors.insert(0, BD2ModError::Unmanaged);

            mods_unmanaged.push(_mod);

            entries.skip_current_dir();
        }
    }

    mods_unmanaged
}
