use std::{
    fs,
    path::{Path, PathBuf},
};

use log::{debug, info, warn};

const DLL_OVERRIDES: &str = r"[Software\\Wine\\DllOverrides]";

pub fn ensure_bepinex_override(game_dir: &Path, prefix: Option<&Path>) {
    if !game_dir.join("winhttp.dll").exists() {
        return;
    }
    let Some(prefix) = prefix else {
        debug!(
            "No Wine prefix known for {:?}, skipping winhttp override",
            game_dir
        );
        return;
    };
    let prefix = &wine_prefix(prefix);
    match ensure_winhttp_override(prefix) {
        Ok(true) => info!("Added winhttp override to {:?}", prefix),
        Ok(false) => debug!("winhttp override already set in {:?}", prefix),
        Err(error) => warn!("Couldn't set winhttp override in {:?}: {}", prefix, error),
    }
}

pub fn is_prefix(path: &Path) -> bool {
    path.join("drive_c").is_dir() && path.join("user.reg").is_file()
}

fn wine_prefix(path: &Path) -> PathBuf {
    let pfx = path.join("pfx");
    if !is_prefix(path) && is_prefix(&pfx) {
        pfx
    } else {
        path.to_path_buf()
    }
}

fn ensure_winhttp_override(prefix: &Path) -> std::io::Result<bool> {
    let reg_path = prefix.join("user.reg");
    let text = fs::read_to_string(&reg_path)?;

    let Some(new_text) = with_override(&text, "winhttp", "native,builtin") else {
        return Ok(false);
    };

    fs::copy(&reg_path, prefix.join("user.reg.bak"))?;
    fs::write(&reg_path, new_text)?;
    Ok(true)
}

fn with_override(reg: &str, dll: &str, value: &str) -> Option<String> {
    let wanted = format!("\"{dll}\"=\"{value}\"");
    let key = format!("\"{}\"=", dll.to_ascii_lowercase());
    let mut lines: Vec<String> = reg.lines().map(String::from).collect();

    match lines
        .iter()
        .position(|line| line.starts_with(DLL_OVERRIDES))
    {
        Some(start) => {
            let end = lines[start + 1..]
                .iter()
                .position(|line| line.is_empty())
                .map_or(lines.len(), |i| start + 1 + i);

            match (start + 1..end).find(|&i| lines[i].to_ascii_lowercase().starts_with(&key)) {
                Some(i) if lines[i] == wanted => return None,
                Some(i) => lines[i] = wanted,
                None => lines.insert(end, wanted),
            }
        }
        None => {
            lines.push(String::new());
            lines.push(DLL_OVERRIDES.to_string());
            lines.push(wanted);
        }
    }

    let mut out = lines.join("\n");
    out.push('\n');
    Some(out)
}
