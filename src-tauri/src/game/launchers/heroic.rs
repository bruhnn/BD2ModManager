use std::path::{Path, PathBuf};

use percent_encoding::{utf8_percent_encode, NON_ALPHANUMERIC};
use serde_json::Value;

use super::{
    expand_home, flatpak_dir, flatpak_run, spawn_detached, Launcher, LauncherApp, LauncherEntry,
};
use crate::game::locate::game_dir_from_exe;
use crate::utils::process::host_command;

const FLATPAK_ID: &str = "com.heroicgameslauncher.hgl";

pub struct Heroic;

fn config_dirs() -> Vec<(PathBuf, bool)> {
    [
        (dirs::config_dir().map(|dir| dir.join("heroic")), false),
        (
            flatpak_dir(FLATPAK_ID, "config").map(|dir| dir.join("heroic")),
            true,
        ),
    ]
    .into_iter()
    .filter_map(|(dir, flatpak)| Some((dir?, flatpak)))
    .filter(|(dir, _)| dir.is_dir())
    .collect()
}

fn read_json(path: &Path) -> Option<Value> {
    serde_json::from_str(&std::fs::read_to_string(path).ok()?).ok()
}

fn parse_sideload_library(library: &Value) -> Vec<(String, String)> {
    let Some(games) = library.get("games").and_then(Value::as_array) else {
        return Vec::new();
    };
    games
        .iter()
        .filter(|game| {
            game.get("is_installed")
                .and_then(Value::as_bool)
                .unwrap_or(true)
        })
        .filter_map(|game| {
            let app_name = game.get("app_name")?.as_str()?;
            let exe = game.get("install")?.get("executable")?.as_str()?;
            Some((app_name.to_string(), exe.to_string()))
        })
        .collect()
}

fn wine_prefix(
    game_config: Option<&Value>,
    global_config: Option<&Value>,
    app_name: &str,
) -> Option<PathBuf> {
    let from_game = game_config
        .and_then(|c| c.get(app_name))
        .and_then(|c| c.get("winePrefix"));
    let from_global = global_config
        .and_then(|c| c.get("defaultSettings"))
        .and_then(|c| c.get("winePrefix"));
    from_game
        .or(from_global)
        .and_then(Value::as_str)
        .filter(|prefix| !prefix.is_empty())
        .map(expand_home)
}

impl Launcher for Heroic {
    fn app(&self) -> LauncherApp {
        LauncherApp::Heroic
    }

    fn entries(&self) -> Vec<LauncherEntry> {
        let mut entries = Vec::new();
        for (dir, flatpak) in config_dirs() {
            let Some(library) = read_json(&dir.join("sideload_apps/library.json")) else {
                continue;
            };
            let global_config = read_json(&dir.join("config.json"));
            for (app_name, exe) in parse_sideload_library(&library) {
                let Some(game_dir) = game_dir_from_exe(&exe) else {
                    continue;
                };
                let game_config =
                    read_json(&dir.join("GamesConfig").join(format!("{app_name}.json")));
                let prefix = wine_prefix(game_config.as_ref(), global_config.as_ref(), &app_name);
                entries.push(LauncherEntry {
                    app: LauncherApp::Heroic,
                    game_id: app_name,
                    flatpak,
                    game_dir,
                    prefix,
                });
            }
        }
        entries
    }

    fn launch(&self, entry: &LauncherEntry) -> std::io::Result<()> {
        let url = format!(
            "heroic://launch?appName={}&runner=sideload",
            utf8_percent_encode(&entry.game_id, NON_ALPHANUMERIC)
        );
        let mut command = if entry.flatpak {
            flatpak_run(FLATPAK_ID)
        } else {
            host_command("xdg-open")
        };
        command.arg(url);
        spawn_detached(command)
    }
}
