pub mod game;
pub mod installer;
pub mod launchers;
pub mod locate;
#[cfg(not(windows))]
pub mod wine;
pub mod commands;
