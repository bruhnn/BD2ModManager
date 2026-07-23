use std::path::Path;
use sys_locale::get_locale;

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