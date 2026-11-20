use std::{
    fs,
    io::{self, BufRead, BufReader, Read},
    path::{Path, PathBuf},
    process::{Command, Stdio},
};

use log::{error, info};
use serde::{Deserialize, Serialize};
use walkdir::WalkDir;

use crate::{
    mods::{BD2Mod, types::BD2ModError},
    utils::files::copy_preserving_mtime,
};

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

const OLD_VERSION: SpineVersion = SpineVersion { major: 4, minor: 1 };

#[cfg(windows)]
const CONVERTER: &[u8] = include_bytes!("../../binaries/BD2Sconverter-x86_64-pc-windows-msvc.exe");
#[cfg(windows)]
const CONVERTER_FILE: &str = "BD2Sconverter.exe";
#[cfg(not(windows))]
const CONVERTER: &[u8] = include_bytes!("../../binaries/BD2Sconverter-x86_64-unknown-linux-gnu");
#[cfg(not(windows))]
const CONVERTER_FILE: &str = "BD2Sconverter";

pub fn extract_converter(tools_dir: &Path) -> io::Result<PathBuf> {
    let path = tools_dir.join(CONVERTER_FILE);
    let up_to_date = match fs::read(&path) {
        Ok(data) => data == CONVERTER,
        Err(_) => false,
    };
    if up_to_date {
        return Ok(path);
    }

    fs::create_dir_all(tools_dir)?;
    fs::write(&path, CONVERTER)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(&path, fs::Permissions::from_mode(0o755))?;
    }
    info!("Extracted the Spine converter to {}", path.display());
    Ok(path)
}

fn mod_files(mod_path: &Path) -> impl Iterator<Item = PathBuf> {
    WalkDir::new(mod_path)
        .into_iter()
        .filter_map(Result::ok)
        .filter(|entry| entry.file_type().is_file())
        .map(|entry| entry.into_path())
}

#[derive(Serialize, Debug, Clone)]
#[serde(rename_all = "camelCase")]
pub struct OldSpineMod {
    pub mod_name: String,
    pub display_name: String,
    // relative to the mod folder
    pub files: Vec<String>,
    #[serde(skip)]
    path: PathBuf,
}


pub fn is_spine41_version(mod_path: &Path) -> Vec<String> {
    let mut files: Vec<String> = mod_files(mod_path)
        .filter(|path| {
            let extension = path.extension().and_then(|ext| ext.to_str()).unwrap_or_default();
            (extension.eq_ignore_ascii_case("skel") || extension.eq_ignore_ascii_case("json"))
                && read_spine_version(path) == Some(OLD_VERSION)
        })
        .map(|path| path.strip_prefix(mod_path).unwrap().to_string_lossy().replace('\\', "/"))
        .collect();
    files.sort();
    files
}

pub fn find_old_spine_mods(mods: &[BD2Mod]) -> Vec<OldSpineMod> {
    let mut found = Vec::new();
    for bd2mod in mods.iter().filter(|m| !m.errors.contains(&BD2ModError::Unmanaged)) {
        let files = is_spine41_version(&bd2mod.path);
        if files.is_empty() {
            continue;
        }
        found.push(OldSpineMod {
            mod_name: bd2mod.name.clone(),
            display_name: bd2mod.display_name.clone(),
            files,
            path: bd2mod.path.clone(),
        });
    }
    if !found.is_empty() {
        info!("Found {} mod(s) made for Spine {}", found.len(), OLD_VERSION);
    }
    found
}

#[derive(Serialize, Debug, Clone, Copy)]
#[serde(rename_all = "camelCase")]
pub enum ConvertPhase {
    Backup,
    Convert,
}

#[derive(Serialize, Debug, Clone, Copy)]
#[serde(rename_all = "camelCase")]
pub struct ConvertProgress {
    pub phase: ConvertPhase,
    pub done: usize,
    pub total: usize,
}

#[derive(Serialize, Debug)]
#[serde(rename_all = "camelCase")]
pub struct ConvertFailure {
    pub mod_name: String,
    pub file: String,
    pub error: String,
}

#[derive(Serialize, Debug, Default)]
#[serde(rename_all = "camelCase")]
pub struct ConvertResult {
    pub converted: Vec<String>,
    pub failed: Vec<ConvertFailure>,
    pub backup_path: Option<String>,
    // nothing is converted when the backup fails
    pub backup_error: Option<String>,
}

fn backup_mods(mods: &[OldSpineMod], backup_root: &Path, progress: &dyn Fn(ConvertProgress)) -> io::Result<()> {
    let files: Vec<(PathBuf, PathBuf)> = mods
        .iter()
        .flat_map(|m| {
            mod_files(&m.path).map(|file| {
                let target = backup_root.join(&m.mod_name).join(file.strip_prefix(&m.path).unwrap());
                (file, target)
            })
        })
        .collect();

    for (done, (source, target)) in files.iter().enumerate() {
        progress(ConvertProgress { phase: ConvertPhase::Backup, done, total: files.len() });
        fs::create_dir_all(target.parent().unwrap())?;
        copy_preserving_mtime(source, target)?;
    }
    Ok(())
}

#[derive(Deserialize)]
struct ConverterLine {
    file: String,
    ok: bool,
    error: Option<String>,
}

fn convert_mod(converter: &Path, old_mod: &OldSpineMod, on_file: &mut dyn FnMut(ConverterLine)) -> io::Result<()> {
    let mut command = Command::new(converter);
    command
        .arg("convert")
        .args(old_mod.files.iter().map(|file| old_mod.path.join(file)))
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        command.creation_flags(CREATE_NO_WINDOW);
    }

    let mut child = command.spawn()?;
    for line in BufReader::new(child.stdout.take().unwrap()).lines() {
        let line = line?;
        match serde_json::from_str(&line) {
            Ok(result) => on_file(result),
            Err(_) => error!("Unexpected output from the Spine converter: {}", line),
        }
    }
    let output = child.wait_with_output()?;
    if !output.status.success() {
        return Err(io::Error::other(format!(
            "The Spine converter stopped ({}): {}",
            output.status,
            String::from_utf8_lossy(&output.stderr).trim()
        )));
    }
    Ok(())
}

pub fn convert_mods(
    converter: &Path,
    mods: &[BD2Mod],
    mod_names: &[String],
    backup_directory: Option<&Path>,
    progress: &dyn Fn(ConvertProgress),
) -> ConvertResult {
    // check again, because te files may have changed while the user was deciding
    let to_convert: Vec<OldSpineMod> = find_old_spine_mods(mods)
        .into_iter()
        .filter(|m| mod_names.contains(&m.mod_name))
        .collect();

    let mut result = ConvertResult::default();

    if let Some(backup_directory) = backup_directory {
        let backup_root = backup_directory.join(format!(
            "spine-{}-{}",
            OLD_VERSION,
            chrono::Local::now().format("%Y%m%d_%H%M%S")
        ));
        if let Err(error) = backup_mods(&to_convert, &backup_root, progress) {
            error!("Backup before converting mods failed: {}", error);
            let _ = fs::remove_dir_all(&backup_root);
            result.backup_error = Some(error.to_string());
            return result;
        }
        result.backup_path = Some(backup_root.to_string_lossy().to_string());
    }

    let total = to_convert.iter().map(|m| m.files.len()).sum();
    let mut done = 0;
    
    progress(ConvertProgress { phase: ConvertPhase::Convert, done, total });

    for old_mod in &to_convert {
        let mut converted = 0;
        let mut on_file = |line: ConverterLine| {
            done += 1;
            progress(ConvertProgress { phase: ConvertPhase::Convert, done, total });
            if line.ok {
                converted += 1;
                return;
            }
            let file = Path::new(&line.file).strip_prefix(&old_mod.path).unwrap_or(Path::new(&line.file));
            let error = line.error.unwrap_or_default();
            error!("Failed to convert {}/{}: {}", old_mod.mod_name, file.display(), error);
            result.failed.push(ConvertFailure {
                mod_name: old_mod.mod_name.clone(),
                file: file.to_string_lossy().replace('\\', "/"),
                error,
            });
        };

        if let Err(error) = convert_mod(converter, old_mod, &mut on_file) {
            error!("Failed to convert {}: {}", old_mod.mod_name, error);
            result.failed.push(ConvertFailure {
                mod_name: old_mod.mod_name.clone(),
                file: String::new(),
                error: error.to_string(),
            });
        } else if converted == old_mod.files.len() {
            result.converted.push(old_mod.mod_name.clone());
        }
    }

    info!(
        "Spine {} conversion: {} mod(s) converted, {} failure(s)",
        OLD_VERSION,
        result.converted.len(),
        result.failed.len()
    );
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

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

    #[test]
    fn backup_dir_validation() {
        let tmp = TempDir::new().unwrap();
        let staging = tmp.path().join("mods");
        let game = tmp.path().join("game");
        fs::create_dir_all(&staging).unwrap();
        fs::create_dir_all(game.join("BepInEx/plugins/BrownDustX/mods")).unwrap();
        let check = |dir: &Path| is_valid_backup_dir(dir, &staging, &game).unwrap();
        assert_eq!(default_backup_dir(&staging), tmp.path().join("mods-backups"));
        assert!(check(&default_backup_dir(&staging)));
        assert!(!check(&staging));
        assert!(!check(&staging.join("backups")));
        assert!(!check(tmp.path()));
        assert!(!check(&game.join("BepInEx/plugins/BrownDustX/mods/backups")));
        assert!(check(&game.join("backups-outside-mods")));
    }

    #[test]
    fn finds_spine_41_files() {
        let tmp = TempDir::new().unwrap();
        let dir = tmp.path().join("ModA");
        fs::create_dir_all(&dir).unwrap();
        let mut skel = vec![0x12; 8];
        skel.push(7);
        skel.extend_from_slice(b"4.1.24");
        fs::write(dir.join("char.skel"), &skel).unwrap();
        fs::write(dir.join("other.json"), br#"{"skeleton":{"spine":"4.2.43"}}"#).unwrap();
        fs::write(dir.join("cutscene.json"), br#"{"skeleton":{"spine":"4.1.11"}}"#).unwrap();

        let discovered = crate::mods::discover::create_mod(tmp.path(), &dir, None);
        assert_eq!(discovered.errors, vec![BD2ModError::SpineVersion41]);

        let mods = vec![BD2Mod { path: dir, name: "ModA".into(), ..Default::default() }];
        let found = find_old_spine_mods(&mods);
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].files, vec!["char.skel", "cutscene.json"]);
    }
}
