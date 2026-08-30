use std::path::Path;
use sys_locale::get_locale;
use tauri::Manager;

#[tauri::command]
pub fn path_exists(path: String) -> bool {
    Path::new(&path).exists()
}

#[tauri::command]
pub fn is_folder(path: String) -> bool {
    Path::new(&path).is_dir()
}

#[tauri::command]
pub fn is_portable() -> bool {
    #[cfg(feature = "portable")]
    {
        true
    }
    #[cfg(not(feature = "portable"))]
    {
        false
    }
}

#[tauri::command]
pub fn get_user_locale() -> String {
    get_locale().unwrap_or_else(|| String::from("en-US"))
}

#[tauri::command]
pub fn get_logs_directory(app: tauri::AppHandle) -> Result<String, String> {
    app.path()
        .app_log_dir()
        .map(|path| path.to_string_lossy().into_owned())
        .map_err(|error| error.to_string())
}
