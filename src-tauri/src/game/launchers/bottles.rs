use std::path::{Path, PathBuf};

use saphyr::{LoadableYamlNode, YamlOwned};

use super::{expand_home, flatpak_dir, spawn_detached, Launcher, LauncherApp, LauncherEntry};
use crate::game::locate::game_dir_from_exe;
use crate::utils::process::host_command;

const FLATPAK_ID: &str = "com.usebottles.bottles";

pub struct Bottles;

fn bottles_dirs() -> Vec<(PathBuf, bool)> {
    let bases = [
        (dirs::data_dir().map(|dir| dir.join("bottles")), false),
        (
            flatpak_dir(FLATPAK_ID, "data").map(|dir| dir.join("bottles")),
            true,
        ),
    ];
    let mut dirs = Vec::new();
    for (base, flatpak) in bases {
        let Some(base) = base else { continue };
        if let Some(custom) = read_yaml(&base.join("data.yml"))
            .and_then(|data| yaml_str(&data, "custom_bottles_path").map(expand_home))
        {
            dirs.push((custom, flatpak));
        }
        dirs.push((base.join("bottles"), flatpak));
    }
    dirs.retain(|(dir, _)| dir.is_dir());
    dirs
}

fn read_yaml(path: &Path) -> Option<YamlOwned> {
    let content = std::fs::read_to_string(path).ok()?;
    YamlOwned::load_from_str(&content).ok()?.into_iter().next()
}

fn yaml_str<'a>(node: &'a YamlOwned, key: &str) -> Option<&'a str> {
    node.as_mapping_get(key)?
        .as_str()
        .filter(|value| !value.is_empty())
}

fn parse_bottle(bottle: &YamlOwned) -> Option<(String, Vec<(String, PathBuf)>)> {
    let name = yaml_str(bottle, "Name")?.to_string();
    let programs = bottle
        .as_mapping_get("External_Programs")
        .and_then(YamlOwned::as_mapping)
        .map(|programs| {
            programs
                .values()
                .filter_map(|program| {
                    let program_name = yaml_str(program, "name")?;
                    let from_path = yaml_str(program, "path").and_then(game_dir_from_exe);
                    let from_folder = || {
                        let folder = yaml_str(program, "folder")?;
                        game_dir_from_exe(&format!("{folder}/{}", yaml_str(program, "executable")?))
                    };
                    Some((program_name.to_string(), from_path.or_else(from_folder)?))
                })
                .collect()
        })
        .unwrap_or_default();
    Some((name, programs))
}

impl Launcher for Bottles {
    fn app(&self) -> LauncherApp {
        LauncherApp::Bottles
    }

    fn entries(&self) -> Vec<LauncherEntry> {
        let mut entries = Vec::new();
        for (dir, flatpak) in bottles_dirs() {
            let Ok(bottle_dirs) = std::fs::read_dir(&dir) else {
                continue;
            };
            for bottle_dir in bottle_dirs.flatten().map(|entry| entry.path()) {
                let Some(bottle) = read_yaml(&bottle_dir.join("bottle.yml")) else {
                    continue;
                };
                let Some((_, programs)) = parse_bottle(&bottle) else {
                    continue;
                };
                for (program, game_dir) in programs {
                    entries.push(LauncherEntry {
                        app: LauncherApp::Bottles,
                        game_id: program,
                        flatpak,
                        game_dir,
                        prefix: Some(bottle_dir.clone()),
                    });
                }
            }
        }
        entries
    }

    fn launch(&self, entry: &LauncherEntry) -> std::io::Result<()> {
        let bottle = entry
            .prefix
            .as_deref()
            .and_then(|prefix| read_yaml(&prefix.join("bottle.yml")))
            .and_then(|bottle| parse_bottle(&bottle))
            .map(|(name, _)| name)
            .ok_or_else(|| {
                std::io::Error::new(std::io::ErrorKind::NotFound, "bottle.yml not found")
            })?;

        let mut command = if entry.flatpak {
            let mut command = host_command("flatpak");
            command.args(["run", "--command=bottles-cli", FLATPAK_ID]);
            command
        } else {
            host_command("bottles-cli")
        };
        command.args(["run", "-b", &bottle, "-p", &entry.game_id]);
        spawn_detached(command)
    }
}
