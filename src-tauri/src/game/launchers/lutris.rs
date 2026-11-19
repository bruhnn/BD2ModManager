use std::path::{Path, PathBuf};

use log::warn;
use rusqlite::{Connection, OpenFlags};
use saphyr::{LoadableYamlNode, Yaml};

use super::{
    expand_home, flatpak_dir, flatpak_run, spawn_detached, Launcher, LauncherApp, LauncherEntry,
};
use crate::game::locate::game_dir_from_exe;
use crate::game::wine::is_prefix;
use crate::utils::process::host_command;

const FLATPAK_ID: &str = "net.lutris.Lutris";

pub struct Lutris;

struct Install {
    config_dir: PathBuf,
    db_path: PathBuf,
    flatpak: bool,
}

fn installs() -> Vec<Install> {
    let mut roots = vec![(dirs::config_dir(), dirs::data_dir(), false)];
    roots.push((
        flatpak_dir(FLATPAK_ID, "config"),
        flatpak_dir(FLATPAK_ID, "data"),
        true,
    ));

    roots
        .into_iter()
        .filter_map(|(config, data, flatpak)| {
            let data_dir = data?.join("lutris");
            let config_dir = config
                .map(|c| c.join("lutris"))
                .filter(|c| c.is_dir())
                .unwrap_or_else(|| data_dir.clone());
            let db_path = read_pga_path(&config_dir.join("lutris.conf"))
                .unwrap_or_else(|| data_dir.join("pga.db"));
            db_path.is_file().then_some(Install {
                config_dir,
                db_path,
                flatpak,
            })
        })
        .collect()
}

fn read_pga_path(conf: &Path) -> Option<PathBuf> {
    let content = std::fs::read_to_string(conf).ok()?;
    let mut section = "";
    for line in content.lines().map(str::trim) {
        if let Some(name) = line.strip_prefix('[').and_then(|l| l.strip_suffix(']')) {
            section = name;
        } else if section == "lutris" {
            if let Some((key, value)) = line.split_once('=') {
                if key.trim() == "pga_path" && !value.trim().is_empty() {
                    return Some(expand_home(value.trim()));
                }
            }
        }
    }
    None
}

fn read_games(db_path: &Path) -> rusqlite::Result<Vec<(i64, Option<String>, String)>> {
    let conn = Connection::open_with_flags(
        db_path,
        OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX,
    )?;
    let mut stmt = conn.prepare(
        "SELECT id, directory, configpath FROM games
         WHERE installed = 1 AND runner = 'wine' AND configpath IS NOT NULL AND configpath != ''",
    )?;
    let rows = stmt.query_map([], |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)))?;
    rows.collect()
}

fn parse_game_config(content: &str, directory: Option<&str>) -> Option<(PathBuf, Option<PathBuf>)> {
    let docs = Yaml::load_from_str(content).ok()?;
    let game = docs.first()?.as_mapping_get("game")?;
    let get = |key: &str| {
        game.as_mapping_get(key)
            .and_then(|v| v.as_str())
            .filter(|v| !v.is_empty())
    };

    let mut exe = expand_home(get("exe")?);
    if exe.is_relative() {
        exe = expand_home(directory.filter(|d| !d.is_empty())?).join(exe);
    }
    let prefix = get("prefix").map(expand_home).or_else(|| find_prefix(&exe));
    Some((exe, prefix))
}

fn find_prefix(exe: &Path) -> Option<PathBuf> {
    exe.ancestors().skip(1).find_map(|dir| {
        [dir.to_path_buf(), dir.join("prefix"), dir.join("pfx")]
            .into_iter()
            .find(|path| is_prefix(path))
    })
}

impl Launcher for Lutris {
    fn app(&self) -> LauncherApp {
        LauncherApp::Lutris
    }

    fn entries(&self) -> Vec<LauncherEntry> {
        let mut entries = Vec::new();
        for install in installs() {
            let games = match read_games(&install.db_path) {
                Ok(games) => games,
                Err(error) => {
                    warn!("Failed to read {:?}: {}", install.db_path, error);
                    continue;
                }
            };
            for (id, directory, configpath) in games {
                let config = install
                    .config_dir
                    .join("games")
                    .join(format!("{configpath}.yml"));
                let Ok(content) = std::fs::read_to_string(&config) else {
                    continue;
                };
                let Some((exe, prefix)) = parse_game_config(&content, directory.as_deref()) else {
                    continue;
                };
                let Some(game_dir) = game_dir_from_exe(&exe.to_string_lossy()) else {
                    continue;
                };
                entries.push(LauncherEntry {
                    app: LauncherApp::Lutris,
                    game_id: id.to_string(),
                    flatpak: install.flatpak,
                    game_dir,
                    prefix,
                });
            }
        }
        entries
    }

    fn launch(&self, entry: &LauncherEntry) -> std::io::Result<()> {
        let mut command = if entry.flatpak {
            flatpak_run(FLATPAK_ID)
        } else {
            host_command("lutris")
        };
        command.arg(format!("lutris:rungameid/{}", entry.game_id));
        spawn_detached(command)
    }
}
