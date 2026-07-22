use std::{collections::HashMap, fs, path::PathBuf};

use log::{info, warn, error};
use serde::{Deserialize, Serialize};

#[derive(thiserror::Error, Debug, Serialize)]
#[serde(tag = "type", content = "message")]
pub enum MetadataError {
    #[error("failed to serialize mod metadata: {0}")]
    Serialize(String),
    #[error("failed to save mod metadata: {0}")]
    Save(String),
    #[error("failed to load mod metadata: {0}")]
    Load(String),
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ModMetadata {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub author: Option<String>,
}

pub struct ModMetadataStore {
    path: PathBuf,
    data: HashMap<String, ModMetadata>,
}

impl ModMetadataStore {
    pub fn new(path: PathBuf) -> Self {
        let mut store = Self {
            path,
            data: HashMap::new(),
        };
        store.load().unwrap_or_else(|e| {
            warn!("Failed to load mod metadata: {:?}", e);
        });
        store
    }

    fn load(&mut self) -> Result<(), MetadataError> {
        if self.path.exists() {
            match fs::read_to_string(&self.path) {
                Ok(contents) => match serde_json::from_str(&contents) {
                    Ok(data) => {
                        self.data = data;
                        info!("Loaded mod metadata from {:?}", self.path);
                    }
                    Err(e) => {
                        error!("Failed to parse mod metadata: {:?}", e);
                        return Err(MetadataError::Load(e.to_string()));
                    }
                },
                Err(e) => {
                    error!("Failed to read mod metadata file: {:?}", e);
                    return Err(MetadataError::Load(e.to_string()));
                }
            }
        } else {
            error!("Mod metadata file does not exist at {:?}", self.path);
        }
        Ok(())
    }

    fn save(&self) -> Result<(), MetadataError> {
        let json = serde_json::to_string_pretty(&self.data)
            .map_err(|e| {
                error!("Failed to serialize mod metadata: {:?}", e);
                MetadataError::Serialize(e.to_string())
            })?;

        let tmp_path = self.path.with_extension("metadata.tmp");

        fs::write(&tmp_path, &json).map_err(|e| {
            error!("Failed to write temp mod metadata file: {:?}", e);
            MetadataError::Save(e.to_string())
        })?;

        fs::rename(&tmp_path, &self.path).map_err(|e| {
            error!("Failed to rename temp mod metadata file: {:?}", e);
            MetadataError::Save(e.to_string())
        })?;

        Ok(())
    }

    pub fn get_author(&self, mod_name: &str) -> Option<String> {
        self.data.get(mod_name).and_then(|m| m.author.clone())
    }

    pub fn set_author(&mut self, mod_name: String, author: Option<String>) -> Result<(), MetadataError> {
        let entry = self.data.entry(mod_name).or_default();
        entry.author = author;
        self.save()?;
        Ok(())
    }

    pub fn set_authors(&mut self, mod_names: &[String], author: Option<String>) -> Result<(), MetadataError> {
        for mod_name in mod_names {
            let entry = self.data.entry(mod_name.clone()).or_default();
            entry.author = author.clone();
        }
        self.save()?;
        Ok(())
    }

    pub fn apply_to_mod(&self, bd2mod: &mut super::BD2Mod) {
        if let Some(metadata) = self.data.get(&bd2mod.name) {
            bd2mod.author = metadata.author.clone();
        }
    }

    pub fn apply_to_mods(&self, mods: &mut HashMap<String, super::BD2Mod>) {
        for (name, metadata) in &self.data {
            if let Some(bd2mod) = mods.get_mut(name) {
                bd2mod.author = metadata.author.clone();
            }
        }
    }

    pub fn rename_mod(&mut self, old_name: &str, new_name: &str) -> Result<(), MetadataError> {
        if let Some(metadata) = self.data.remove(old_name) {
            self.data.insert(new_name.to_string(), metadata);
            self.save()?;
        }
        Ok(())
    }

    pub fn remove_mod(&mut self, mod_name: &str) -> Result<(), MetadataError> {
        if self.data.remove(mod_name).is_some() {
            self.save()?;
        }
        Ok(())
    }

    pub fn import_from_legacy(&mut self, legacy_mods: &HashMap<String, HashMap<String, serde_json::Value>>) -> Result<(), MetadataError> {
        for (mod_name, mod_info) in legacy_mods {
            if let Some(author) = mod_info.get("author").and_then(|a| a.as_str()) {
                let entry = self.data.entry(mod_name.clone()).or_default();
                if entry.author.is_some() {
                    info!("Overwriting author for mod '{}' from legacy data: '{}' -> '{}'", mod_name, entry.author.as_ref().unwrap(), author);
                } else {
                    info!("Setting author for mod '{}' from legacy data: '{}'", mod_name, author);
                }
                entry.author = Some(author.to_string());
            }
        }
        self.save()?;
        Ok(())
    }
}
