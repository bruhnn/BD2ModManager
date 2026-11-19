use std::path::PathBuf;

use log::warn;

use super::{flatpak_run, spawn_detached, Launcher, LauncherApp, LauncherEntry};
use crate::game::locate::game_dir_from_exe;
use crate::utils::process::host_command;

const FLATPAK_ID: &str = "io.github.Faugus.faugus-launcher";

pub struct Faugus;

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
        let Ok(file) = dir.join("faugus-launcher/games.json").canonicalize() else {
            continue;
        };
        if !files.iter().any(|(known, _)| *known == file) {
            files.push((file, flatpak));
        }
    }
    files
}

#[derive(Debug, PartialEq)]
struct FaugusGame {
    id: String,
    dir: PathBuf,
    prefix: Option<PathBuf>,
}

fn parse_games(content: &str) -> Vec<FaugusGame> {
    let Ok(serde_json::Value::Array(games)) = serde_json::from_str(content) else {
        return Vec::new();
    };
    games
        .iter()
        .filter_map(|game| {
            let id = game.get("gameid")?.as_str()?;
            let dir = game_dir_from_exe(game.get("path")?.as_str()?)?;
            let prefix = game
                .get("prefix")
                .and_then(|prefix| prefix.as_str())
                .filter(|prefix| !prefix.is_empty())
                .map(PathBuf::from);
            Some(FaugusGame {
                id: id.to_string(),
                dir,
                prefix,
            })
        })
        .collect()
}

impl Launcher for Faugus {
    fn app(&self) -> LauncherApp {
        LauncherApp::Faugus
    }

    fn entries(&self) -> Vec<LauncherEntry> {
        let mut entries = Vec::new();
        for (file, flatpak) in games_files() {
            let content = match std::fs::read_to_string(&file) {
                Ok(content) => content,
                Err(error) => {
                    warn!("Failed to read {:?}: {}", file, error);
                    continue;
                }
            };
            for game in parse_games(&content) {
                entries.push(LauncherEntry {
                    app: LauncherApp::Faugus,
                    game_id: game.id,
                    flatpak,
                    game_dir: game.dir,
                    prefix: game.prefix,
                });
            }
        }
        entries
    }

    fn launch(&self, entry: &LauncherEntry) -> std::io::Result<()> {
        let mut command = if entry.flatpak {
            flatpak_run(FLATPAK_ID)
        } else {
            host_command("faugus-launcher")
        };
        command.args(["--game", &entry.game_id]);
        spawn_detached(command)
    }
}
