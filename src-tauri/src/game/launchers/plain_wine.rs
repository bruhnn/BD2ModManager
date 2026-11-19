use std::path::Path;

use super::{spawn_detached, Launcher, LauncherApp, LauncherEntry};
use crate::game::locate::{is_game_dir, GAME_EXE};
use crate::game::wine::is_prefix;
use crate::utils::process::host_command;

pub struct PlainWine;

pub fn entry_for(game_dir: &Path) -> Option<LauncherEntry> {
    if !is_game_dir(game_dir) {
        return None;
    }
    let prefix = game_dir.ancestors().skip(1).find(|dir| is_prefix(dir))?;
    Some(LauncherEntry {
        app: LauncherApp::Wine,
        game_id: String::new(),
        flatpak: false,
        game_dir: game_dir.to_path_buf(),
        prefix: Some(prefix.to_path_buf()),
    })
}

impl Launcher for PlainWine {
    fn app(&self) -> LauncherApp {
        LauncherApp::Wine
    }

    fn entries(&self) -> Vec<LauncherEntry> {
        Vec::new()
    }

    fn launch(&self, entry: &LauncherEntry) -> std::io::Result<()> {
        let prefix = entry.prefix.as_deref().ok_or_else(|| {
            std::io::Error::new(std::io::ErrorKind::NotFound, "Wine prefix not found")
        })?;
        let mut command = host_command("wine");
        command
            .arg(entry.game_dir.join(GAME_EXE))
            .current_dir(&entry.game_dir)
            .env("WINEPREFIX", prefix);
        spawn_detached(command)
    }
}
