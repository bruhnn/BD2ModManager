use std::path::PathBuf;

pub fn rotate_logs(logs_dir: &PathBuf) {
    if !logs_dir.exists() {
        return;
    }

    // this function will only keep2 logs; will move logs.log to logs-<timestamp>.log, and delete the previous logs-<timestamp>.log if it exists

    let log_file = logs_dir.join("logs.log");
    if !log_file.exists() {
        return;
    }

    let timestamp = std::fs::metadata(&log_file)
        .and_then(|m| m.modified())
        .map(|t| {
            let dt: chrono::DateTime<chrono::Local> = t.into();
            dt.format("%Y-%m-%d_%H-%M-%S").to_string()
        })
        .unwrap_or_else(|_| chrono::Local::now().format("%Y-%m-%d_%H-%M-%S").to_string());

    let rotated_log_file = logs_dir.join(format!("logs-{}.log", timestamp));
    if let Err(e) = std::fs::rename(&log_file, &rotated_log_file) {
        eprintln!("Failed to rename log file: {e}");
        return;
    }

    let entries = match std::fs::read_dir(logs_dir) {
        Ok(e) => e,
        Err(e) => { eprintln!("Failed to read logs dir: {e}"); return; }
    };

    let old_logs: Vec<_> = entries
        .filter_map(|entry| {
            let entry = entry.ok()?;
            let file_name = entry.file_name().into_string().ok()?;
            if file_name.starts_with("logs-")
                && file_name.ends_with(".log")
                && entry.path() != rotated_log_file
            {
                Some(entry.path())
            } else {
                None
            }
        })
        .collect();

    for old_log in old_logs {
        if let Err(e) = std::fs::remove_file(&old_log) {
            eprintln!("Failed to remove old log file: {e}");
        }
    }
}
