use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Debug, Clone, PartialEq, Hash, Serialize, Deserialize)]
pub enum BD2ModError {
    MissingModfile,
    MissingTextures,
    MissingAtlasFile,
    ShouldBeInFolder,
    ArchiveNotExtracted,
    Unmanaged, // not in staging, but in game folder
    UnmanagedButInStaging, // in staging, not in game folder
}

#[derive(Debug, Clone, PartialEq, Hash, Eq, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum BD2ModType {
    Standing { id: String },
    Cutscene { id: String },
    Scene { id: String },
    NPC { id: String },
    Dating { id: String, real_id: String },
    Minigame { id: Option<String> },
}

#[derive(Debug, Clone, PartialEq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BD2Mod {
    pub path: PathBuf,
    pub name: String,
    pub display_name: String,
    pub mod_type: Option<BD2ModType>,
    pub conflicts_with: Vec<String>,
    pub errors: Vec<BD2ModError>,
    pub enabled: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub author: Option<String>,
}

impl Default for BD2Mod {
    fn default() -> Self {
        BD2Mod {
            path: PathBuf::new(),
            name: String::new(),
            display_name: String::new(),
            mod_type: None,
            errors: Vec::new(),
            conflicts_with: Vec::new(),
            enabled: false,
            author: None,
        }
    }
}
