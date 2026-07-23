use std::sync::{Arc, Mutex};

use crate::{BD2ModManager, config::BD2Config};

pub struct BundledAssets(pub std::collections::HashSet<String>);

pub struct AppState {
    pub mod_manager: Arc<Mutex<BD2ModManager>>,
    pub config: Arc<Mutex<BD2Config>>,
}