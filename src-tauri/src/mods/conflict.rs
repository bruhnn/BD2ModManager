use std::collections::HashMap;

use crate::mods::{BD2Mod, BD2ModType};

pub fn detect_conflicts(mods: &mut HashMap<String, BD2Mod>) {
    let mut conflict_map: HashMap<BD2ModType, Vec<String>> = HashMap::new();

    for (name, bd2_mod) in mods.iter_mut() {
        bd2_mod.conflicts_with.clear();
        if let Some(ref mod_type) = bd2_mod.mod_type {
            conflict_map
                .entry(mod_type.clone())
                .or_default()
                .push(name.clone());
        }
    }

    let mut conflicts_to_apply: Vec<(String, Vec<String>)> = Vec::new();

    for (_mod_type, names) in conflict_map.iter() {
        if names.len() > 1 {
            // Each mod conflicts with all others of the same type + id
            // Dating also compares real_id, so different parts don't conflict
            for name in names {
                let mut conflict_with = names.clone();
                conflict_with.retain(|n| n != name);
                conflicts_to_apply.push((name.clone(), conflict_with));
            }
        }
    }

    for (name, conflict_with) in conflicts_to_apply {
        if let Some(m) = mods.get_mut(&name) {
            //     if !m.errors.contains(&BD2ModError::HasConflict) {
            //         m.errors.push(BD2ModError::HasConflict);
            //     }
            for conflict_name in conflict_with {
                if !m.conflicts_with.contains(&conflict_name) {
                    m.conflicts_with.push(conflict_name);
                }
            }
        }
    }
}
