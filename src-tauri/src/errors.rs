use serde::Serializer;

use crate::{mods::{delete::ModDeleteError, install::ModInstallError, metadata::MetadataError, preview::PreviewError, rename::ModRenameError, sync::ModSyncError}, profiles::types::ProfileError};

fn get_type_name<T>() -> &'static str {
    let type_name = std::any::type_name::<T>();
    type_name.rsplit("::").next().unwrap_or(type_name)
}

fn get_error_type<T: serde::Serialize>(err: &T) -> String {
    match serde_json::to_value(err) {
        Ok(serde_json::Value::Object(map)) => map
            .get("type")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
            .unwrap_or_else(|| get_type_name::<T>().to_string()),
        _ => get_type_name::<T>().to_string(),
    }
}

fn get_error_details<T: serde::Serialize>(err: &T) -> serde_json::Value {
    match serde_json::to_value(err) {
        Ok(serde_json::Value::Object(map)) => map
            .get("details")
            .cloned()
            .unwrap_or(serde_json::Value::Null),
        _ => serde_json::Value::Null,
    }
}

// { parent: "ModInstallError", type: "Io", details: { kind: "PermissionDenied" }, message: "I/O error: Permission denied" }
// { parent: "ModInstallError", type: "PathNotFound", details: { path: "path/to/mod", mod_name: "mod_name" }, message: "The path 'path/to/mod' was not found for mod 'mod_name'" }
// { parent: "ProfileError", type: "LoadFailed", details: { kind: "PermissionDenied" }, message: "failed to load profiles: Permission denied" }
// { parent: "AppError", type: "Io", details: { kind: "PermissionDenied" }, message: "I/O error: Permission denied" }
// { parent: "AppError", type: "GameRunning", details: {}, message: "Game is already running." }
// { parent: "AppError", type: "SyncMethodInvalid", details: { method: "method_name" }, message: "Sync method 'method_name' is invalid" }
#[derive(thiserror::Error, Debug)]
pub enum AppError {
    #[error("Game is already running.")]
    GameRunning,
    #[error("Game directory is not set")]
    GameDirectoryNotSet,
    #[error("Sync method '{method}' is invalid")]
    SyncMethodInvalid { method: String },

    #[error(transparent)]
    Install(#[from] ModInstallError),
    #[error(transparent)]
    Delete(#[from] ModDeleteError),
    #[error(transparent)]
    Sync(#[from] ModSyncError),
    #[error(transparent)]
    Rename(#[from] ModRenameError),
    #[error(transparent)]
    Profile(#[from] ProfileError),
    #[error(transparent)]
    Metadata(#[from] MetadataError),
    #[error(transparent)]
    Preview(#[from] PreviewError),

    #[error("An unknown error occurred: {0}")]
    Unknown(String)
}

impl serde::Serialize for AppError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where S: serde::Serializer {
        use serde::ser::SerializeStruct;

        let parent_type: &'static str = match self {
            // AppError::Io(_) => "Io",
            AppError::Install(_) => get_type_name::<ModInstallError>(),
            AppError::Delete(_) => get_type_name::<ModDeleteError>(),
            AppError::Sync(_) => get_type_name::<ModSyncError>(),
            AppError::Rename(_) => get_type_name::<ModRenameError>(),
            AppError::Profile(_) => get_type_name::<ProfileError>(),
            AppError::Metadata(_) => get_type_name::<MetadataError>(),
            AppError::Preview(_) => get_type_name::<PreviewError>(),
            AppError::GameDirectoryNotSet => get_type_name::<AppError>(),
            AppError::SyncMethodInvalid { method: _ } => get_type_name::<AppError>(),
            AppError::GameRunning => get_type_name::<AppError>(),
            AppError::Unknown(_) => get_type_name::<AppError>(),
        };
        
        let err_type: String = match self {
            AppError::Install(err) => get_error_type(err),
            AppError::Delete(err) => get_error_type(err),
            AppError::Sync(err) => get_error_type(err),
            AppError::Rename(err) => get_error_type(err),
            AppError::Profile(err) => get_error_type(err),
            AppError::Metadata(err) => get_error_type(err),
            AppError::Preview(err) => get_error_type(err),
            AppError::GameDirectoryNotSet => "GameDirectoryNotSet".to_string(),
            AppError::SyncMethodInvalid { method: _ } => "SyncMethodInvalid".to_string(),
            AppError::GameRunning => "GameRunning".to_string(),
            AppError::Unknown(_) => "Unknown".to_string(),
        };

        let details: serde_json::Value = match self {
            AppError::Install(err) => get_error_details(err),
            AppError::Delete(err) => get_error_details(err),
            AppError::Sync(err) => get_error_details(err),
            AppError::Rename(err) => get_error_details(err),
            AppError::Profile(err) => get_error_details(err),
            AppError::Metadata(err) => get_error_details(err),
            AppError::Preview(err) => get_error_details(err),
            AppError::GameDirectoryNotSet => serde_json::Value::Null,
            AppError::GameRunning => serde_json::Value::Null,
            AppError::SyncMethodInvalid { method } => serde_json::Value::String(method.clone()),
            AppError::Unknown(_) => serde_json::Value::Null,
        };

        let mut s: <S as Serializer>::SerializeStruct = serializer.serialize_struct("Error", 4)?;
        s.serialize_field("parent", parent_type)?;
        s.serialize_field("type", &err_type)?;
        s.serialize_field("details", &details)?;
        s.serialize_field("message", &self.to_string())?;
        s.end()
    }
}
