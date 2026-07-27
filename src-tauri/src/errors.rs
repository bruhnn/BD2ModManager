use crate::{mods::{delete::ModDeleteError, install::ModInstallError, metadata::MetadataError, preview::PreviewError, rename::ModRenameError, sync::ModSyncError}, profiles::types::ProfileError};

#[derive(thiserror::Error, Debug)]
pub enum ModError {
    #[error("game directory is not set")]
    GameDirectoryNotSet,
    #[error("invalid sync method: {0}")]
    SyncMethodInvalid(String),

    #[error(transparent)]
    Io(#[from] std::io::Error),
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
    #[error("unknown error: {0}")]
    Unknown(String)
}

impl serde::Serialize for ModError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where S: serde::Serializer {
        use serde::ser::SerializeStruct;
        let mut s = serializer.serialize_struct("Error", 2)?;
         let type_ = match self {
            ModError::Io(_) => "io",
            ModError::Install(_) => "install",
            ModError::Delete(_) => "delete",
            ModError::Sync(_) => "sync",
            ModError::Rename(_) => "rename",
            ModError::Profile(_) => "profile",
            ModError::Metadata(_) => "metadata",
            ModError::Preview(_) => "preview",
            ModError::Unknown(_) => "unknown",
            ModError::GameDirectoryNotSet => "game_directory_not_set",
            ModError::SyncMethodInvalid(_) => "sync_method_invalid",
        };
        s.serialize_field("type", type_)?;
        s.serialize_field("message", &self.to_string())?;
        s.end()
    }
}

