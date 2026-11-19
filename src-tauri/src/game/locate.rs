use std::path::{Path, PathBuf};

use serde::Serialize;

use super::launchers::LauncherEntry;

pub const GAME_EXE: &str = "BrownDust II.exe";

#[derive(Serialize, Debug, Clone, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct LocatedGame {
    pub path: String,
    pub launcher: Option<LauncherEntry>,
}

pub fn is_game_dir(path: &Path) -> bool {
    path.join(GAME_EXE).exists() && path.join("BrownDust II_Data").exists()
}

#[cfg_attr(windows, allow(dead_code))]
pub fn game_dir_from_exe(exe: &str) -> Option<PathBuf> {
    let exe = Path::new(exe);
    let name = exe.file_name()?.to_str()?;
    if !name.eq_ignore_ascii_case(GAME_EXE) {
        return None;
    }
    exe.parent().map(Path::to_path_buf)
}
