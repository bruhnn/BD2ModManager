// Mods converted in the game folder (ex. BrownDustX converting Spine 4.1 mods to 4.2 in place).
//
// With the copy sync method the game folder only holds copies, so the next sync would
// overwrite the converted files with the old ones from staging. This finds those mods and
// copies the converted files back into staging, so staging stays the source of truth.

use std::{
    cmp::Ordering,
    collections::HashMap,
    fs,
    io::{self, Read},
    path::{Path, PathBuf},
};

use log::{info, warn};
use serde::Serialize;
use walkdir::WalkDir;

use crate::{
    mods::{
        BD2Mod,
        sync::{SyncMethod, load_manifest, resolve_mod_source},
        types::BD2ModError,
    },
    utils::files::{copy_preserving_mtime, is_link},
};

// files BrownDustX may rewrite when converting a mod
const CONVERTED_EXTENSIONS: &[&str] = &["skel", "json", "atlas"];
const TEMP_SUFFIX: &str = ".bd2mm-tmp";
// the version is in the skeleton block at the start of a JSON skeleton
const JSON_HEADER_LIMIT: u64 = 64 * 1024;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct SpineVersion {
    pub major: u32,
    pub minor: u32,
}

impl std::fmt::Display for SpineVersion {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}.{}", self.major, self.minor)
    }
}

fn parse_version(version: &str) -> Option<SpineVersion> {
    let mut parts = version.trim().split('.');
    let major = parts.next()?.parse().ok()?;
    let minor = parts.next()?.parse().ok()?;
    Some(SpineVersion { major, minor })
}

// binary skeleton (Spine 4.x): 8 byte hash, then the version as a varint length + utf8 string
fn read_binary_version(header: &[u8]) -> Option<SpineVersion> {
    let mut index = 8;
    let mut length: u32 = 0;
    for shift in (0..35).step_by(7) {
        let byte = *header.get(index)?;
        index += 1;
        length |= ((byte & 0x7F) as u32) << shift;
        if byte & 0x80 == 0 {
            break;
        }
    }
    // 0 = null, 1 = empty string
    let length = length.checked_sub(1)? as usize;
    if length == 0 || length > 32 {
        return None;
    }
    let version = std::str::from_utf8(header.get(index..index + length)?).ok()?;
    if !version.chars().all(|c| c.is_ascii_digit() || c == '.') {
        return None;
    }
    parse_version(version)
}

// JSON skeleton: { "skeleton": { "spine": "4.1.24", ... }, ... }
fn read_json_version(text: &str) -> Option<SpineVersion> {
    let skeleton = text.find("\"skeleton\"")?;
    let rest = &text[skeleton..];
    let spine = rest.find("\"spine\"")?;
    let rest = rest[spine + "\"spine\"".len()..].trim_start();
    let rest = rest.strip_prefix(':')?.trim_start();
    let rest = rest.strip_prefix('"')?;
    let end = rest.find('"')?;
    parse_version(&rest[..end])
}

pub fn read_spine_version(path: &Path) -> Option<SpineVersion> {
    let mut header = Vec::new();
    fs::File::open(path)
        .ok()?
        .take(JSON_HEADER_LIMIT)
        .read_to_end(&mut header)
        .ok()?;

    // by extension: a binary skeleton can start with '{' (its hash is random)
    if path.extension().is_some_and(|ext| ext.eq_ignore_ascii_case("json")) {
        let text = header.strip_prefix(b"\xEF\xBB\xBF").unwrap_or(&header);
        return read_json_version(&String::from_utf8_lossy(text));
    }
    read_binary_version(&header)
}

fn has_converted_extension(path: &Path) -> bool {
    path.extension()
        .and_then(|ext| ext.to_str())
        .map(|ext| {
            CONVERTED_EXTENSIONS
                .iter()
                .any(|allowed| ext.eq_ignore_ascii_case(allowed))
        })
        .unwrap_or(false)
}

fn files_differ(a: &fs::Metadata, b: &fs::Metadata) -> bool {
    a.len() != b.len() || a.modified().ok() != b.modified().ok()
}

// a file that exists in both copies of the mod and is different in the game folder
struct ChangedFile {
    relative: PathBuf,
    game_version: Option<SpineVersion>,
    staging_version: Option<SpineVersion>,
}

fn changed_files(game_path: &Path, staging_path: &Path) -> io::Result<Vec<ChangedFile>> {
    let mut changed = Vec::new();

    for entry in WalkDir::new(game_path).follow_links(false).min_depth(1) {
        let entry = entry.map_err(io::Error::from)?;
        if !entry.file_type().is_file() || !has_converted_extension(entry.path()) {
            continue;
        }

        let relative = entry.path().strip_prefix(game_path).unwrap().to_path_buf();
        let staging_file = staging_path.join(&relative);

        let staging_metadata = match fs::symlink_metadata(&staging_file) {
            Ok(metadata) if metadata.is_file() && !is_link(&metadata) => metadata,
            Ok(_) => continue,
            Err(error) if error.kind() == io::ErrorKind::NotFound => continue,
            Err(error) => return Err(error),
        };

        if !files_differ(&entry.metadata().map_err(io::Error::from)?, &staging_metadata) {
            continue;
        }

        changed.push(ChangedFile {
            game_version: read_spine_version(entry.path()),
            staging_version: read_spine_version(&staging_file),
            relative,
        });
    }

    Ok(changed)
}

// versions of the converted files, or None if the mod wasn't converted to a newer Spine version
fn converted_versions(files: &[ChangedFile]) -> Option<(SpineVersion, SpineVersion)> {
    let mut game_version: Option<SpineVersion> = None;
    let mut staging_version: Option<SpineVersion> = None;

    for file in files {
        let (Some(game), Some(staging)) = (file.game_version, file.staging_version) else {
            continue;
        };
        match game.cmp(&staging) {
            // the game copy is older than staging: staging was updated, let sync replace it
            Ordering::Less => return None,
            Ordering::Equal => {}
            Ordering::Greater => {
                game_version = game_version.max(Some(game));
                staging_version = Some(staging_version.map_or(staging, |v| v.min(staging)));
            }
        }
    }

    Some((game_version?, staging_version?))
}

#[derive(Serialize, Debug, Clone)]
#[serde(rename_all = "camelCase")]
pub struct ConvertedMod {
    pub mod_name: String,
    pub game_folder: String,
    pub game_version: String,
    pub staging_version: String,
}

struct ConvertedModPaths {
    info: ConvertedMod,
    game_path: PathBuf,
    staging_path: PathBuf,
    files: Vec<PathBuf>,
}

fn find_converted(
    game_directory: &Path,
    mods: &[BD2Mod],
) -> Result<Vec<ConvertedModPaths>, crate::mods::sync::ModSyncError> {
    let Some(manifest) = load_manifest(&game_directory.join(".bd2mm.json"))? else {
        return Ok(Vec::new());
    };

    let game_mods_path = game_directory.join("BepInEx/plugins/BrownDustX/mods/BD2MM");
    if !game_mods_path.is_dir() {
        return Ok(Vec::new());
    }

    let staging_mods: HashMap<&str, &BD2Mod> = mods
        .iter()
        .filter(|m| !m.errors.contains(&BD2ModError::Unmanaged))
        .map(|m| (m.name.as_str(), m))
        .collect();

    let mut converted = Vec::new();

    for entry in &manifest.synced_mods {
        // with symlinks the game folder points at staging, there is nothing to copy back
        if entry.method != SyncMethod::Copy {
            continue;
        }
        let Some(staging_mod) = staging_mods.get(entry.mod_name.as_str()) else {
            continue;
        };

        let game_path = game_mods_path.join(&entry.game_folder);
        match fs::symlink_metadata(&game_path) {
            Ok(metadata) if metadata.is_dir() && !is_link(&metadata) => {}
            _ => continue,
        }

        let staging_path = match resolve_mod_source(&staging_mod.path, &game_mods_path) {
            Ok(path) => path,
            Err(error) => {
                warn!("Skipping {} while checking for converted mods: {}", entry.mod_name, error);
                continue;
            }
        };

        let files = match changed_files(&game_path, &staging_path) {
            Ok(files) => files,
            Err(error) => {
                warn!("Failed to compare {} with the game folder: {}", entry.mod_name, error);
                continue;
            }
        };

        let Some((game_version, staging_version)) = converted_versions(&files) else {
            continue;
        };

        converted.push(ConvertedModPaths {
            info: ConvertedMod {
                mod_name: entry.mod_name.clone(),
                game_folder: entry.game_folder.replace('\\', "/"),
                game_version: game_version.to_string(),
                staging_version: staging_version.to_string(),
            },
            game_path,
            staging_path,
            files: files.into_iter().map(|file| file.relative).collect(),
        });
    }

    Ok(converted)
}

pub fn find_converted_mods(
    game_directory: &Path,
    mods: &[BD2Mod],
) -> Result<Vec<ConvertedMod>, crate::mods::sync::ModSyncError> {
    let converted: Vec<ConvertedMod> = find_converted(game_directory, mods)?
        .into_iter()
        .map(|m| m.info)
        .collect();
    if !converted.is_empty() {
        info!("Found {} mod(s) converted in the game folder", converted.len());
    }
    Ok(converted)
}

// lowercase absolute path, resolving the part that exists (the rest may not be created yet)
fn normalize(path: &Path) -> io::Result<PathBuf> {
    let path = std::path::absolute(path)?;
    let parent = path
        .ancestors()
        .find(|parent| parent.exists())
        .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "Path parent was not found"))?;
    let resolved = parent.canonicalize()?.join(path.strip_prefix(parent).unwrap());
    Ok(PathBuf::from(resolved.to_string_lossy().to_lowercase()))
}

fn overlaps(a: &Path, b: &Path) -> bool {
    a.starts_with(b) || b.starts_with(a)
}

pub fn is_valid_backup_dir(
    backup_directory: &Path,
    staging_directory: &Path,
    game_directory: &Path,
) -> io::Result<bool> {
    let backup = normalize(backup_directory)?;
    let staging = normalize(staging_directory)?;
    let game_mods = normalize(&game_directory.join("BepInEx/plugins/BrownDustX/mods"))?;
    Ok(!overlaps(&backup, &staging) && !overlaps(&backup, &game_mods))
}

pub fn default_backup_dir(staging_directory: &Path) -> PathBuf {
    let name = staging_directory
        .file_name()
        .map(|name| name.to_string_lossy().into_owned())
        .unwrap_or_else(|| "mods".into());
    staging_directory.with_file_name(format!("{}-backups", name))
}

fn temp_path(path: &Path) -> PathBuf {
    let mut name = path.file_name().unwrap_or_default().to_os_string();
    name.push(TEMP_SUFFIX);
    path.with_file_name(name)
}

// copies the converted files into staging without leaving a mod half updated:
// 1. copy every game file next to its staging file as a temp file
// 2. back up the staging files
// 3. replace the staging files with the temp files
fn copy_mod_files(converted: &ConvertedModPaths, backup: Option<&Path>) -> io::Result<()> {
    let pairs: Vec<(PathBuf, PathBuf, PathBuf)> = converted
        .files
        .iter()
        .map(|relative| {
            let target = converted.staging_path.join(relative);
            (converted.game_path.join(relative), temp_path(&target), target)
        })
        .collect();

    let remove_temps = |pairs: &[(PathBuf, PathBuf, PathBuf)]| {
        for (_, temp, _) in pairs {
            let _ = fs::remove_file(temp);
        }
    };

    for (source, temp, _) in &pairs {
        let result = copy_preserving_mtime(source, temp).and_then(|_| {
            if fs::metadata(source)?.len() != fs::metadata(temp)?.len() {
                return Err(io::Error::other(format!("Copy of {:?} is incomplete", source)));
            }
            Ok(())
        });
        if let Err(error) = result {
            remove_temps(&pairs);
            return Err(error);
        }
    }

    if let Some(backup) = backup {
        for (relative, (_, _, target)) in converted.files.iter().zip(&pairs) {
            let destination = backup.join(relative);
            let result = destination
                .parent()
                .map_or(Ok(()), fs::create_dir_all)
                .and_then(|_| copy_preserving_mtime(target, &destination));
            if let Err(error) = result {
                remove_temps(&pairs);
                return Err(error);
            }
        }
    }

    for (index, (_, temp, target)) in pairs.iter().enumerate() {
        if let Err(error) = fs::rename(temp, target) {
            // put back the files already replaced, if we have them
            if let Some(backup) = backup {
                for relative in &converted.files[..index] {
                    let _ = copy_preserving_mtime(&backup.join(relative), &converted.staging_path.join(relative));
                }
            }
            remove_temps(&pairs[index..]);
            return Err(error);
        }
    }

    Ok(())
}

#[derive(Serialize, Debug)]
#[serde(rename_all = "camelCase")]
pub struct CopyConvertedFailure {
    pub mod_name: String,
    pub error: String,
}

#[derive(Serialize, Debug)]
#[serde(rename_all = "camelCase")]
pub struct CopyConvertedResult {
    pub copied: Vec<String>,
    pub failed: Vec<CopyConvertedFailure>,
    pub backup_path: Option<String>,
}

pub fn copy_converted_mods(
    game_directory: &Path,
    mods: &[BD2Mod],
    mod_names: &[String],
    backup_directory: Option<&Path>,
) -> Result<CopyConvertedResult, crate::mods::sync::ModSyncError> {
    // check again, the files may have changed while the user was deciding
    let converted: Vec<ConvertedModPaths> = find_converted(game_directory, mods)?
        .into_iter()
        .filter(|m| mod_names.contains(&m.info.mod_name))
        .collect();

    let backup_root = backup_directory.map(|dir| {
        dir.join(chrono::Local::now().format("%Y%m%d_%H%M%S").to_string())
    });

    let mut result = CopyConvertedResult {
        copied: Vec::new(),
        failed: Vec::new(),
        backup_path: None,
    };

    for converted_mod in &converted {
        let backup = backup_root.as_ref().map(|root| root.join(&converted_mod.info.mod_name));
        match copy_mod_files(converted_mod, backup.as_deref()) {
            Ok(()) => {
                info!(
                    "Copied {} converted file(s) of {} into staging",
                    converted_mod.files.len(),
                    converted_mod.info.mod_name
                );
                result.copied.push(converted_mod.info.mod_name.clone());
            }
            Err(error) => {
                warn!("Failed to copy converted mod {}: {}", converted_mod.info.mod_name, error);
                result.failed.push(CopyConvertedFailure {
                    mod_name: converted_mod.info.mod_name.clone(),
                    error: error.to_string(),
                });
            }
        }
    }

    for name in mod_names {
        if !converted.iter().any(|m| &m.info.mod_name == name) {
            warn!("{} is no longer a converted mod, skipped", name);
        }
    }

    if !result.copied.is_empty() {
        result.backup_path = backup_root.map(|root| root.to_string_lossy().to_string());
    }

    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn binary_header(version: &str) -> Vec<u8> {
        let mut data = vec![0x12; 8];
        data.push(version.len() as u8 + 1);
        data.extend_from_slice(version.as_bytes());
        data.extend_from_slice(&[0, 0, 0]);
        data
    }

    #[test]
    fn reads_binary_version() {
        assert_eq!(read_binary_version(&binary_header("4.1.24")), Some(SpineVersion { major: 4, minor: 1 }));
        assert_eq!(read_binary_version(&binary_header("4.2.43")), Some(SpineVersion { major: 4, minor: 2 }));
        assert_eq!(read_binary_version(&[0; 4]), None);
        assert_eq!(read_binary_version(&binary_header("abc")), None);
    }

    #[test]
    fn reads_binary_version_starting_with_a_brace() {
        let dir = tempfile::TempDir::new().unwrap();
        let path = dir.path().join("char.skel");
        let mut data = binary_header("4.1.11");
        data[0] = b'{';
        fs::write(&path, data).unwrap();
        assert_eq!(read_spine_version(&path), Some(SpineVersion { major: 4, minor: 1 }));
    }

    #[test]
    fn reads_json_version() {
        let json = r#"{ "skeleton": { "hash": "x", "spine" : "4.1.24", "x": 0 }, "bones": [] }"#;
        assert_eq!(read_json_version(json), Some(SpineVersion { major: 4, minor: 1 }));
        assert_eq!(read_json_version(r#"{ "bones": [] }"#), None);
    }

    fn changed(game: Option<(u32, u32)>, staging: Option<(u32, u32)>) -> ChangedFile {
        let version = |v: Option<(u32, u32)>| v.map(|(major, minor)| SpineVersion { major, minor });
        ChangedFile {
            relative: PathBuf::new(),
            game_version: version(game),
            staging_version: version(staging),
        }
    }

    #[test]
    fn detects_converted_mods() {
        let v41 = Some((4, 1));
        let v42 = Some((4, 2));
        assert!(converted_versions(&[changed(v42, v41), changed(None, None)]).is_some());
        assert!(converted_versions(&[changed(v42, v41), changed(v41, v42)]).is_none());
        assert!(converted_versions(&[changed(v41, v41)]).is_none());
        assert!(converted_versions(&[changed(None, None)]).is_none());
        assert!(converted_versions(&[]).is_none());
    }

    #[test]
    fn copies_files_with_backup() {
        let root = tempfile::tempdir().unwrap();
        let game = root.path().join("game/modA");
        let staging = root.path().join("staging/modA");
        let backup = root.path().join("backup/modA");
        fs::create_dir_all(&game).unwrap();
        fs::create_dir_all(&staging).unwrap();
        fs::write(game.join("char.skel"), binary_header("4.2.43")).unwrap();
        fs::write(staging.join("char.skel"), binary_header("4.1.24")).unwrap();

        let converted = ConvertedModPaths {
            info: ConvertedMod {
                mod_name: "modA".into(),
                game_folder: "modA".into(),
                game_version: "4.2".into(),
                staging_version: "4.1".into(),
            },
            game_path: game.clone(),
            staging_path: staging.clone(),
            files: vec![PathBuf::from("char.skel")],
        };
        copy_mod_files(&converted, Some(&backup)).unwrap();

        assert_eq!(read_spine_version(&staging.join("char.skel")), Some(SpineVersion { major: 4, minor: 2 }));
        assert_eq!(read_spine_version(&backup.join("char.skel")), Some(SpineVersion { major: 4, minor: 1 }));
        assert!(!temp_path(&staging.join("char.skel")).exists());
        // same size and mtime, so sync sees nothing to do
        assert!(!files_differ(
            &fs::metadata(game.join("char.skel")).unwrap(),
            &fs::metadata(staging.join("char.skel")).unwrap()
        ));
    }

    // ---- full flow tests on a fake game + staging folder ----

    #[cfg(unix)]
    use std::os::unix::fs::PermissionsExt;

    struct Sandbox {
        _root: tempfile::TempDir,
        game: PathBuf,
        staging: PathBuf,
        backups: PathBuf,
        manifest: Vec<serde_json::Value>,
        mods: Vec<BD2Mod>,
    }

    impl Sandbox {
        fn new() -> Self {
            let root = tempfile::tempdir().unwrap();
            let game = root.path().join("game");
            let staging = root.path().join("mods");
            fs::create_dir_all(game.join("BepInEx/plugins/BrownDustX/mods/BD2MM")).unwrap();
            fs::create_dir_all(&staging).unwrap();
            Sandbox {
                backups: root.path().join("mods-backups"),
                _root: root,
                game,
                staging,
                manifest: Vec::new(),
                mods: Vec::new(),
            }
        }

        fn game_mod(&self, folder: &str) -> PathBuf {
            self.game.join("BepInEx/plugins/BrownDustX/mods/BD2MM").join(folder)
        }

        // a synced mod: same files in staging and game, then `game_files` overwrite the game copy
        fn add(&mut self, name: &str, method: &str, staging_files: &[(&str, Vec<u8>)], game_files: &[(&str, Vec<u8>)]) {
            let folder = name.replace('/', "_");
            let staging_mod = self.staging.join(name);
            let game_mod = self.game_mod(&folder);
            fs::create_dir_all(&staging_mod).unwrap();
            fs::create_dir_all(&game_mod).unwrap();
            for (file, data) in staging_files {
                fs::write(staging_mod.join(file), data).unwrap();
                copy_preserving_mtime(&staging_mod.join(file), &game_mod.join(file)).unwrap();
            }
            // newer mtime, like a real conversion
            std::thread::sleep(std::time::Duration::from_millis(20));
            for (file, data) in game_files {
                fs::write(game_mod.join(file), data).unwrap();
            }
            self.manifest.push(serde_json::json!({ "mod_name": name, "game_folder": folder, "method": method }));
            self.mods.push(BD2Mod { name: name.into(), path: staging_mod, ..Default::default() });
            self.save_manifest();
        }

        fn save_manifest(&self) {
            let manifest = serde_json::json!({
                "method": "Copy",
                "synced_mods": self.manifest,
                "synced_at": "2026-11-19T00:00:00Z",
            });
            fs::write(self.game.join(".bd2mm.json"), manifest.to_string()).unwrap();
        }

        fn found(&self) -> Vec<String> {
            find_converted_mods(&self.game, &self.mods).unwrap().into_iter().map(|m| m.mod_name).collect()
        }

        fn copy(&self, names: &[&str], backup: bool) -> CopyConvertedResult {
            let names: Vec<String> = names.iter().map(|n| n.to_string()).collect();
            copy_converted_mods(&self.game, &self.mods, &names, backup.then_some(self.backups.as_path())).unwrap()
        }

        fn staging_version(&self, name: &str, file: &str) -> Option<String> {
            read_spine_version(&self.staging.join(name).join(file)).map(|v| v.to_string())
        }
    }

    fn json_skel(version: &str) -> Vec<u8> {
        format!(r#"{{"skeleton":{{"hash":"x","spine":"{}","width":1}},"bones":[]}}"#, version).into_bytes()
    }

    fn files_41() -> Vec<(&'static str, Vec<u8>)> {
        vec![
            ("char.skel", binary_header("4.1.24")),
            ("char.atlas", b"char.png\nsize: 1,1\n".to_vec()),
            ("char.png", b"png".to_vec()),
            ("char.modfile", b"".to_vec()),
        ]
    }

    #[test]
    fn detection_rules() {
        let mut sb = Sandbox::new();
        let converted = [("char.skel", binary_header("4.2.43"))];
        sb.add("converted", "Copy", &files_41(), &converted);
        sb.add("nested/json", "Copy", &[("char.json", json_skel("4.1.24"))], &[("char.json", json_skel("4.2.43"))]);
        sb.add("symlink_method", "Symlink", &files_41(), &converted);
        sb.add("unchanged", "Copy", &files_41(), &[]);
        sb.add("game_older", "Copy", &[("char.skel", binary_header("4.2.43"))], &[("char.skel", binary_header("4.1.24"))]);
        sb.add("same_version_edit", "Copy", &files_41(), &[("char.skel", binary_header("4.1.25"))]);
        sb.add("only_png_changed", "Copy", &files_41(), &[("char.png", b"other".to_vec())]);
        sb.add("garbage_skel", "Copy", &files_41(), &[("char.skel", b"not a skeleton".to_vec())]);

        // staging copy deleted after syncing
        sb.add("deleted_in_staging", "Copy", &files_41(), &converted);
        sb.mods.retain(|m| m.name != "deleted_in_staging");

        // unmanaged copy in the game folder is never listed
        sb.add("unmanaged", "Copy", &files_41(), &converted);
        sb.mods.iter_mut().find(|m| m.name == "unmanaged").unwrap().errors.push(BD2ModError::Unmanaged);

        let mut found = sb.found();
        found.sort();
        assert_eq!(found, vec!["converted", "nested/json"]);

        let info = find_converted_mods(&sb.game, &sb.mods).unwrap();
        let converted = info.iter().find(|m| m.mod_name == "converted").unwrap();
        assert_eq!((converted.game_version.as_str(), converted.staging_version.as_str()), ("4.2", "4.1"));
        assert_eq!(info.iter().find(|m| m.mod_name == "nested/json").unwrap().game_folder, "nested_json");
    }

    #[test]
    fn no_manifest_or_game_folder() {
        let sb = Sandbox::new();
        assert!(sb.found().is_empty()); // no manifest
        fs::write(sb.game.join(".bd2mm.json"), "{ broken").unwrap();
        assert!(find_converted_mods(&sb.game, &sb.mods).is_err()); // sync would fail the same way
        let empty = tempfile::tempdir().unwrap();
        assert!(find_converted_mods(empty.path(), &[]).unwrap().is_empty());
    }

    #[test]
    #[cfg(unix)]
    fn game_folder_symlink_is_skipped() {
        let mut sb = Sandbox::new();
        sb.add("linked", "Copy", &files_41(), &[("char.skel", binary_header("4.2.43"))]);
        let game_mod = sb.game_mod("linked");
        let elsewhere = sb.game.join("elsewhere");
        fs::rename(&game_mod, &elsewhere).unwrap();
        std::os::unix::fs::symlink(&elsewhere, &game_mod).unwrap();
        assert!(sb.found().is_empty());
    }

    #[test]
    fn copy_with_backup_then_nothing_to_sync() {
        let mut sb = Sandbox::new();
        sb.add("a", "Copy", &files_41(), &[
            ("char.skel", binary_header("4.2.43")),
            ("char.atlas", b"char.png\nsize: 1,1\nfilter: Linear,Linear\n".to_vec()),
            ("char.png.bytes", b"bdx extra file".to_vec()),
        ]);
        sb.add("b/nested", "Copy", &[("char.json", json_skel("4.1.24"))], &[("char.json", json_skel("4.2.43"))]);
        fs::write(sb.staging.join("a/readme.txt"), "only in staging").unwrap();

        let result = sb.copy(&["a", "b/nested"], true);
        assert_eq!(result.copied, vec!["a", "b/nested"]);
        assert!(result.failed.is_empty());
        let backup = PathBuf::from(result.backup_path.unwrap());
        assert!(backup.starts_with(&sb.backups));

        // staging updated
        assert_eq!(sb.staging_version("a", "char.skel").as_deref(), Some("4.2"));
        assert_eq!(sb.staging_version("b/nested", "char.json").as_deref(), Some("4.2"));
        assert!(fs::read_to_string(sb.staging.join("a/char.atlas")).unwrap().contains("filter"));
        // files BDX added are not copied, files only in staging are kept
        assert!(!sb.staging.join("a/char.png.bytes").exists());
        assert!(sb.staging.join("a/char.png").exists());
        assert!(sb.staging.join("a/readme.txt").exists());
        // backup has the old files only
        assert_eq!(read_spine_version(&backup.join("a/char.skel")).unwrap().to_string(), "4.1");
        assert!(!fs::read_to_string(backup.join("a/char.atlas")).unwrap().contains("filter"));
        assert!(!backup.join("a/char.png").exists());
        assert_eq!(read_spine_version(&backup.join("b/nested/char.json")).unwrap().to_string(), "4.1");

        // nothing converted anymore, and the sync check sees the spine files as equal
        assert!(sb.found().is_empty());
        assert!(crate::utils::files::dirs_match(&sb.staging.join("b/nested"), &sb.game_mod("b_nested")).unwrap());
        // no temp files left
        let temps = WalkDir::new(&sb.staging).into_iter().flatten()
            .filter(|e| e.file_name().to_string_lossy().ends_with(TEMP_SUFFIX)).count();
        assert_eq!(temps, 0);
    }

    #[test]
    fn copy_without_backup() {
        let mut sb = Sandbox::new();
        sb.add("a", "Copy", &files_41(), &[("char.skel", binary_header("4.2.43"))]);
        let result = sb.copy(&["a"], false);
        assert_eq!(result.copied, vec!["a"]);
        assert!(result.backup_path.is_none());
        assert!(!sb.backups.exists());
        assert_eq!(sb.staging_version("a", "char.skel").as_deref(), Some("4.2"));
    }

    #[test]
    fn copy_skips_names_not_converted_anymore() {
        let mut sb = Sandbox::new();
        sb.add("a", "Copy", &files_41(), &[("char.skel", binary_header("4.2.43"))]);
        sb.add("b", "Copy", &files_41(), &[]);
        let result = sb.copy(&["a", "b", "missing"], true);
        assert_eq!(result.copied, vec!["a"]);
        assert!(result.failed.is_empty());
    }

    #[test]
    fn nothing_copied_has_no_backup_path() {
        let mut sb = Sandbox::new();
        sb.add("b", "Copy", &files_41(), &[]);
        let result = sb.copy(&["b"], true);
        assert!(result.copied.is_empty() && result.failed.is_empty() && result.backup_path.is_none());
    }

    #[test]
    #[cfg(unix)]
    fn read_only_staging_mod_fails_without_changes() {
        let mut sb = Sandbox::new();
        sb.add("locked", "Copy", &files_41(), &[("char.skel", binary_header("4.2.43"))]);
        sb.add("ok", "Copy", &files_41(), &[("char.skel", binary_header("4.2.43"))]);
        let locked = sb.staging.join("locked");
        fs::set_permissions(&locked, fs::Permissions::from_mode(0o555)).unwrap();

        let result = sb.copy(&["locked", "ok"], true);
        fs::set_permissions(&locked, fs::Permissions::from_mode(0o755)).unwrap();

        // the other mod still copies
        assert_eq!(result.copied, vec!["ok"]);
        assert_eq!(result.failed.len(), 1);
        assert_eq!(result.failed[0].mod_name, "locked");
        assert!(!result.failed[0].error.is_empty());
        // original untouched, no temp file
        assert_eq!(sb.staging_version("locked", "char.skel").as_deref(), Some("4.1"));
        assert!(!locked.join(format!("char.skel{}", TEMP_SUFFIX)).exists());
        // still listed, so the next sync asks again
        assert_eq!(sb.found(), vec!["locked"]);
    }

    #[test]
    #[cfg(unix)]
    fn backup_failure_keeps_original() {
        let mut sb = Sandbox::new();
        sb.add("a", "Copy", &files_41(), &[("char.skel", binary_header("4.2.43"))]);
        fs::create_dir_all(&sb.backups).unwrap();
        fs::set_permissions(&sb.backups, fs::Permissions::from_mode(0o555)).unwrap();

        let result = sb.copy(&["a"], true);
        fs::set_permissions(&sb.backups, fs::Permissions::from_mode(0o755)).unwrap();

        assert!(result.copied.is_empty());
        assert_eq!(result.failed.len(), 1);
        assert!(result.backup_path.is_none());
        assert_eq!(sb.staging_version("a", "char.skel").as_deref(), Some("4.1"));
        assert!(!sb.staging.join(format!("a/char.skel{}", TEMP_SUFFIX)).exists());
    }

    #[test]
    #[cfg(unix)]
    fn unreadable_game_file_fails_without_changes() {
        let mut sb = Sandbox::new();
        sb.add("a", "Copy", &files_41(), &[
            ("char.skel", binary_header("4.2.43")),
            ("char.atlas", b"changed".to_vec()),
        ]);
        let game_atlas = sb.game_mod("a").join("char.atlas");
        let converted = find_converted(&sb.game, &sb.mods).unwrap();
        // the file becomes unreadable after the check (ex. the game locks it)
        fs::set_permissions(&game_atlas, fs::Permissions::from_mode(0o000)).unwrap();
        let result = copy_mod_files(&converted[0], None);
        fs::set_permissions(&game_atlas, fs::Permissions::from_mode(0o644)).unwrap();

        assert!(result.is_err());
        assert_eq!(sb.staging_version("a", "char.skel").as_deref(), Some("4.1"));
        let temps = fs::read_dir(sb.staging.join("a")).unwrap().flatten()
            .filter(|e| e.file_name().to_string_lossy().ends_with(TEMP_SUFFIX)).count();
        assert_eq!(temps, 0);
    }

    #[test]
    fn rename_failure_restores_replaced_files() {
        let mut sb = Sandbox::new();
        sb.add("a", "Copy", &files_41(), &[
            ("char.atlas", b"converted atlas".to_vec()),
            ("char.skel", binary_header("4.2.43")),
        ]);
        let mut converted = find_converted(&sb.game, &sb.mods).unwrap().remove(0);
        converted.files.sort(); // atlas first, then skel
        assert_eq!(converted.files, vec![PathBuf::from("char.atlas"), PathBuf::from("char.skel")]);

        // make the second rename fail: replace the staging skel with a non-empty folder
        let skel = sb.staging.join("a/char.skel");
        let original_skel = fs::read(&skel).unwrap();
        fs::remove_file(&skel).unwrap();
        fs::create_dir_all(skel.join("x")).unwrap();
        // backup still needs the original to copy, so give it from elsewhere
        let backup = sb.backups.join("run/a");
        fs::create_dir_all(&backup).unwrap();

        // run the steps manually: the backup of char.skel would fail on a folder,
        // so check the restore logic with a backup made beforehand
        fs::write(backup.join("char.skel"), &original_skel).unwrap();
        copy_preserving_mtime(&sb.staging.join("a/char.atlas"), &backup.join("char.atlas")).unwrap();
        let only_rename = ConvertedModPaths { files: converted.files.clone(), ..converted };
        let result = copy_mod_files(&only_rename, Some(&backup));
        assert!(result.is_err());

        // atlas was put back to the original
        assert_eq!(fs::read(sb.staging.join("a/char.atlas")).unwrap(), b"char.png\nsize: 1,1\n");
        let temps = fs::read_dir(sb.staging.join("a")).unwrap().flatten()
            .filter(|e| e.file_name().to_string_lossy().ends_with(TEMP_SUFFIX)).count();
        assert_eq!(temps, 0);
    }

    #[test]
    fn backup_dir_validation() {
        let sb = Sandbox::new();
        let check = |dir: &Path| is_valid_backup_dir(dir, &sb.staging, &sb.game).unwrap();
        assert!(check(&sb.backups));
        assert!(check(&default_backup_dir(&sb.staging)));
        assert_eq!(default_backup_dir(&sb.staging), sb.backups);
        assert!(!check(&sb.staging));
        assert!(!check(&sb.staging.join("backups")));
        assert!(!check(sb.staging.parent().unwrap())); // contains staging
        assert!(!check(&sb.game.join("BepInEx/plugins/BrownDustX/mods/backups")));
        assert!(check(&sb.game.join("backups-outside-mods")));
    }

}
