import { readonly, ref } from "vue";
import { defineStore } from "pinia";
import { invoke } from "@tauri-apps/api/core"
import { useLoggingStore } from "./logging";

export type Language = "en" | "cn" | "jp" | "tw" | "kr"

// game/locate.rs
export interface LauncherEntry {
    app: "faugus",
    gameId: string,
    flatpak: boolean,
}

export interface LocatedGame {
    path: string,
    launcher: LauncherEntry | null,
}

//game/commands.rs
export type StagingPathError = { kind: "notFound" } | { kind: "overlapsGameMods" }

interface Settings {
    theme?: string,
    language?: Language,
    gameDirectory?: string | null,
    stagingDirectory?: string | null,
    searchModsRecursively: boolean,
    syncMethod?: string,
    checkForAppUpdates: boolean,
    updateChannel: string,
    autoUpdateModPreview: boolean,
    autoUpdateGameData: boolean,
    skipUpdateVersion?: string | null,
    autoSyncMods: boolean,
    autoSyncModsDelay: number,
    isFirstLaunch: boolean,
    recentGameDirectories: string[],
    recentStagingDirectories: string[],
}

export const useSettingsStore = defineStore("settings", () => {
    const settings = ref<Settings>({} as Settings)
    const loggingStore = useLoggingStore()

    async function loadSettings() {
        settings.value = await invoke<Settings>("get_settings");
    }

    async function getSettings(): Promise<Settings> {
        // const result = await invoke<Settings>("get_settings");
        // Object.assign(settings, result);
        return invoke<Settings>("get_settings");
    }

    async function saveSettings(value: Partial<Settings>) {
        // ex. {theme: ..., language: ...}
        // ex 2. {gameDirectory: ...}
        return invoke("set_settings", { value }).then((_value) => {
            return loadSettings() // or Object.assign(settings, value)
        })
    }

    async function locateGamePath(): Promise<LocatedGame[] | null> {
        try {
            const paths = await invoke<LocatedGame[] | null>("locate_game");
            return paths;
        } catch (err) {
            loggingStore.logError("Failed to locate game path", err);
            return null;
        }
    }

    function validateGamePath(path: string): Promise<boolean> {
        return invoke<boolean>("validate_game_path", { path })
    }

    async function validateStagingPath(path: string): Promise<StagingPathError | null> {
        try {
            await invoke("validate_staging_path", { path })
            return null
        } catch (err) {
            return err as StagingPathError
        }
    }

    return {
        settings: readonly(settings),

        loadSettings,
        getSettings,
        saveSettings,

        // BrownDustX
        locateGamePath,
        validateGamePath,
        validateStagingPath,
    }
})
