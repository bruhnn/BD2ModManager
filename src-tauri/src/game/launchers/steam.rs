use std::path::{Path, PathBuf};

use log::warn;

use super::{flatpak_run, spawn_detached, Launcher, LauncherApp, LauncherEntry};
use crate::game::locate::game_dir_from_exe;
use crate::utils::process::host_command;

const FLATPAK_ID: &str = "com.valvesoftware.Steam";

pub struct Steam;

fn shortcut_game_dir(executable: &str) -> Option<PathBuf> {
    game_dir_from_exe(executable.trim().trim_matches('"'))
}

fn compatdata(steam_dir: &Path, app_id: u32) -> PathBuf {
    steam_dir
        .join("steamapps/compatdata")
        .join(app_id.to_string())
}

fn rungameid(app_id: u32) -> u64 {
    ((app_id as u64) << 32) | 0x0200_0000
}

impl Launcher for Steam {
    fn app(&self) -> LauncherApp {
        LauncherApp::Steam
    }

    fn entries(&self) -> Vec<LauncherEntry> {
        let Ok(steam_dirs) = steamlocate::locate_all() else {
            return Vec::new();
        };
        let mut entries = Vec::new();
        for steam_dir in steam_dirs {
            let shortcuts = match steam_dir.shortcuts() {
                Ok(shortcuts) => shortcuts,
                Err(error) => {
                    warn!(
                        "Failed to read Steam shortcuts in {:?}: {}",
                        steam_dir.path(),
                        error
                    );
                    continue;
                }
            };
            let flatpak = steam_dir.path().to_string_lossy().contains(FLATPAK_ID);
            for shortcut in shortcuts.flatten() {
                let Some(game_dir) = shortcut_game_dir(&shortcut.executable) else {
                    continue;
                };
                entries.push(LauncherEntry {
                    app: LauncherApp::Steam,
                    game_id: shortcut.app_id.to_string(),
                    flatpak,
                    game_dir,
                    prefix: Some(compatdata(steam_dir.path(), shortcut.app_id)),
                });
            }
        }
        entries
    }

    fn launch(&self, entry: &LauncherEntry) -> std::io::Result<()> {
        let app_id: u32 = entry.game_id.parse().map_err(|_| {
            std::io::Error::new(std::io::ErrorKind::InvalidInput, "invalid shortcut appid")
        })?;
        let mut command = if entry.flatpak {
            flatpak_run(FLATPAK_ID)
        } else {
            host_command("steam")
        };
        command.arg(format!("steam://rungameid/{}", rungameid(app_id)));
        spawn_detached(command)
    }
}
