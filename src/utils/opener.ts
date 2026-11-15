import { invoke } from '@tauri-apps/api/core';

// Drop-in replacements for openUrl/openPath from @tauri-apps/plugin-opener.
// They go through the open_external command, which on Linux starts the browser or file manager
// without the AppImage's environment (see src-tauri/src/utils/process.rs).
export function openUrl(url: string): Promise<void> {
    return invoke('open_external', { target: url });
}

export function openPath(path: string): Promise<void> {
    return invoke('open_external', { target: path });
}
