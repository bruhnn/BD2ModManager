use std::path::PathBuf;

use serde::Serialize;

#[cfg(not(windows))]
mod bottles;
#[cfg(not(windows))]
mod faugus;
#[cfg(not(windows))]
mod heroic;
#[cfg(not(windows))]
mod lutris;
#[cfg(not(windows))]
mod steam;

#[cfg_attr(windows, allow(dead_code))]
#[derive(Serialize, Debug, Clone, Copy, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum LauncherApp {
    Faugus,
    Lutris,
    Heroic,
    Bottles,
    Steam,
}

#[cfg_attr(windows, allow(dead_code))]
#[derive(Serialize, Debug, Clone, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct LauncherEntry {
    pub app: LauncherApp,
    pub game_id: String,
    pub flatpak: bool,
    #[serde(skip)]
    pub game_dir: PathBuf,
    #[serde(skip)]
    pub prefix: Option<PathBuf>,
}

#[cfg(not(windows))]
pub use linux::*;

#[cfg(not(windows))]
mod linux {
    use std::path::{Path, PathBuf};
    use std::process::{Command, Stdio};

    use log::debug;

    use super::{bottles, faugus, heroic, lutris, steam, LauncherApp, LauncherEntry};
    use crate::game::locate::{is_game_dir, LocatedGame};
    use crate::utils::process::host_command;

    pub trait Launcher: Sync {
        fn app(&self) -> LauncherApp;
        fn entries(&self) -> Vec<LauncherEntry>;
        fn launch(&self, entry: &LauncherEntry) -> std::io::Result<()>;
    }

    static LAUNCHERS: &[&dyn Launcher] = &[
        &faugus::Faugus,
        &lutris::Lutris,
        &heroic::Heroic,
        &bottles::Bottles,
        &steam::Steam,
    ];

    fn all_entries() -> impl Iterator<Item = LauncherEntry> {
        LAUNCHERS
            .iter()
            .flat_map(|launcher| launcher.entries())
            .filter(|entry| {
                let valid = is_game_dir(&entry.game_dir);
                if !valid {
                    debug!(
                        "{:?} entry {} points to {:?}, not a game folder",
                        entry.app, entry.game_id, entry.game_dir
                    );
                }
                valid
            })
    }

    pub fn locate() -> Vec<LocatedGame> {
        let mut found: Vec<LocatedGame> = Vec::new();
        for entry in all_entries() {
            let path = entry.game_dir.to_string_lossy().to_string();
            if found.iter().any(|game| game.path == path) {
                continue;
            }
            found.push(LocatedGame {
                path,
                launcher: Some(entry),
            });
        }
        found
    }

    pub fn entry_for(game_dir: &Path) -> Option<LauncherEntry> {
        let target = game_dir.canonicalize().ok()?;
        all_entries().find(|entry| {
            entry
                .game_dir
                .canonicalize()
                .is_ok_and(|path| path == target)
        })
    }

    pub fn launch(entry: &LauncherEntry) -> std::io::Result<()> {
        let launcher = LAUNCHERS
            .iter()
            .find(|launcher| launcher.app() == entry.app)
            .ok_or_else(|| {
                std::io::Error::new(std::io::ErrorKind::Unsupported, "launcher not supported")
            })?;
        launcher.launch(entry)
    }

    pub(super) fn home() -> Option<PathBuf> {
        std::env::var_os("HOME")
            .filter(|home| !home.is_empty())
            .map(PathBuf::from)
    }

    pub(super) fn flatpak_dir(app_id: &str, kind: &str) -> Option<PathBuf> {
        home().map(|home| home.join(".var/app").join(app_id).join(kind))
    }

    pub(super) fn expand_home(path: &str) -> PathBuf {
        match (path.strip_prefix("~/"), home()) {
            (Some(rest), Some(home)) => home.join(rest),
            _ => PathBuf::from(path),
        }
    }

    pub(super) fn flatpak_run(app_id: &str) -> Command {
        let mut command = host_command("flatpak");
        command.args(["run", app_id]);
        command
    }

    pub(super) fn spawn_detached(mut command: Command) -> std::io::Result<()> {
        let mut child = command
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()?;
        std::thread::spawn(move || {
            let _ = child.wait();
        });
        Ok(())
    }
}
