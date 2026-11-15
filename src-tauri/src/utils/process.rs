use std::ffi::OsStr;
use std::process::Command;

pub fn host_command(program: impl AsRef<OsStr>) -> Command {
    let mut command = Command::new(program);
    if let Some(appdir) = std::env::var("APPDIR").ok().filter(|dir| !dir.is_empty()) {
        for (key, value) in std::env::vars_os() {
            let value = value.to_string_lossy();
            if !value.contains(&appdir) {
                continue;
            }
            if key == "PATH" || key == "XDG_DATA_DIRS" {
                let host: Vec<&str> = value.split(':').filter(|dir| !dir.starts_with(&appdir)).collect();
                command.env(&key, host.join(":"));
            } else {
                command.env_remove(&key);
            }
        }
    }
    command
}

/// works like open of tauri
pub fn open_external(app: &tauri::AppHandle, target: &str) -> Result<(), String> {
    #[cfg(windows)]
    {
        use tauri_plugin_opener::OpenerExt;
        let result = if target.starts_with("http") {
            app.opener().open_url(target, None::<&str>)
        } else {
            app.opener().open_path(target, None::<&str>)
        };
        result.map_err(|error| error.to_string())
    }

    #[cfg(not(windows))]
    {
        let _ = app;
        let mut child = host_command("xdg-open").arg(target).spawn().map_err(|error| error.to_string())?;
        
        std::thread::spawn(move || child.wait());
        Ok(())
    }
}
