use std::path::{Path, PathBuf};

use serde::Serialize;

const GAME_EXE: &str = "BrownDust II.exe";

#[derive(Serialize, Debug, Clone, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum LauncherApp {
    Faugus,
}

// launcher entry that runs an install (Linux: Wine/Proton)
#[derive(Serialize, Debug, Clone, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct LauncherEntry {
    pub app: LauncherApp,
    // id of the game inside the launcher (Faugus: gameid)
    pub game_id: String,
    // the launcher is the Flatpak version (decides how to run it)
    pub flatpak: bool,
}

#[derive(Serialize, Debug, Clone, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct LocatedGame {
    // game folder (the one containing BrownDust II.exe)
    pub path: String,
    // launcher that runs this install (Linux only)
    pub launcher: Option<LauncherEntry>,
}

pub fn is_game_dir(path: &Path) -> bool {
    path.join(GAME_EXE).exists() && path.join("BrownDust II_Data").exists()
}

// Game folder from an exe path saved by a launcher, if that exe is the game itself
#[cfg_attr(windows, allow(dead_code))]
fn game_dir_from_exe(exe: &str) -> Option<PathBuf> {
    let exe = Path::new(exe);
    let name = exe.file_name()?.to_str()?;
    if !name.eq_ignore_ascii_case(GAME_EXE) {
        return None;
    }
    exe.parent().map(Path::to_path_buf)
}

#[cfg(not(windows))]
pub mod faugus {
    use std::path::{Path, PathBuf};
    use std::process::Stdio;

    use crate::utils::process::host_command;

    use log::{debug, warn};

    use super::{game_dir_from_exe, is_game_dir, LauncherApp, LauncherEntry, LocatedGame};

    const FLATPAK_ID: &str = "io.github.Faugus.faugus-launcher";

    // games.json of every Faugus install, and whether it's the Flatpak one
    fn games_files() -> Vec<(PathBuf, bool)> {
        let home = std::env::var_os("HOME").map(PathBuf::from);
        let mut data_dirs = Vec::new();
        if let Some(xdg) = std::env::var_os("XDG_DATA_HOME").filter(|v| !v.is_empty()) {
            data_dirs.push((PathBuf::from(xdg), false));
        }
        if let Some(home) = &home {
            data_dirs.push((home.join(".local/share"), false));
            data_dirs.push((home.join(".var/app").join(FLATPAK_ID).join("data"), true));
        }

        let mut files: Vec<(PathBuf, bool)> = Vec::new();
        for (dir, flatpak) in data_dirs {
            // XDG_DATA_HOME is usually ~/.local/share, so the same file can show up twice
            let Ok(file) = dir.join("faugus-launcher/games.json").canonicalize() else { continue };
            if !files.iter().any(|(known, _)| *known == file) {
                files.push((file, flatpak));
            }
        }
        files
    }

    // (game folder, gameid) for every entry whose exe is the game. Doesn't check the disk.
    pub(super) fn parse_games(content: &str) -> Vec<(PathBuf, String)> {
        let Ok(serde_json::Value::Array(games)) = serde_json::from_str(content) else {
            return Vec::new();
        };
        games
            .iter()
            .filter_map(|game| {
                let id = game.get("gameid")?.as_str()?;
                let dir = game_dir_from_exe(game.get("path")?.as_str()?)?;
                Some((dir, id.to_string()))
            })
            .collect()
    }

    pub fn locate() -> Vec<LocatedGame> {
        let mut found: Vec<LocatedGame> = Vec::new();
        for (file, flatpak) in games_files() {
            let content = match std::fs::read_to_string(&file) {
                Ok(content) => content,
                Err(error) => {
                    warn!("Failed to read {:?}: {}", file, error);
                    continue;
                }
            };
            for (dir, game_id) in parse_games(&content) {
                if !is_game_dir(&dir) {
                    debug!("Faugus entry {} points to {:?}, not a game folder", game_id, dir);
                    continue;
                }
                let path = dir.to_string_lossy().to_string();
                if found.iter().any(|game| game.path == path) {
                    continue;
                }
                found.push(LocatedGame {
                    path,
                    launcher: Some(LauncherEntry { app: LauncherApp::Faugus, game_id, flatpak }),
                });
            }
        }
        found
    }

    // Faugus entry for this game folder, looked up again on every launch so it
    // also works for folders picked by hand and never uses a stale id
    pub fn entry_for(game_dir: &Path) -> Option<LauncherEntry> {
        let target = game_dir.canonicalize().ok()?;
        locate()
            .into_iter()
            .find(|game| Path::new(&game.path).canonicalize().is_ok_and(|path| path == target))
            .and_then(|game| game.launcher)
    }

    pub fn launch(entry: &LauncherEntry) -> std::io::Result<()> {
        let mut command = if entry.flatpak {
            let mut command = host_command("flatpak");
            command.args(["run", FLATPAK_ID]);
            command
        } else {
            host_command("faugus-launcher")
        };
        let mut child = command
            .args(["--game", &entry.game_id])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()?;
        // reap it when it exits so it doesn't stay as a zombie process
        std::thread::spawn(move || {
            let _ = child.wait();
        });
        Ok(())
    }
}
