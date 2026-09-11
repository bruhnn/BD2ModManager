import { readonly, ref } from "vue";
import { defineStore } from "pinia";
import { invoke } from "@tauri-apps/api/core"
import { useLoggingStore } from "./logging";

export type Language = "en" | "cn" | "jp" | "tw" | "kr"

interface Settings {
    theme?: string,
    language?: Language,
    gameDirectory?: string | null,
    stagingDirectory?: string | null,
    searchModsRecursively: boolean,
    syncMethod?: string,
    checkForAppUpdates: boolean,
    autoUpdateModPreview: boolean,
    autoUpdateGameData: boolean,
    skipUpdateVersion?: string | null,
    autoSyncMods: boolean,
    isFirstLaunch: boolean,
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
            loadSettings() // or Object.assign(settings, value)
        })
    }

    async function locateGamePath(): Promise<string[] | null> {
        // [TODO] find on steam too
        try {
            const paths = await invoke<string[]>("locate_game");
            return paths;
        } catch (err) {
            loggingStore.logError("Failed to locate game path", err);
            return null;
        }
    }

    function validateGamePath(path: string): Promise<boolean> {
        return invoke<boolean>("validate_game_path", { path })
    }

    const availableThemes = ref([
        { label: 'Dark 1', value: 'dark-1' },
        { label: 'Dark 2', value: 'dark-2' },
        { label: "Dark 3", value: "dark-3" },
        { label: 'Dark 4', value: 'dark-4' },
        { label: 'Light 1', value: 'light-1' },
        { label: 'Light 2', value: 'light-2' },
    ])

    return {
        settings: readonly(settings),

        loadSettings,
        getSettings,
        saveSettings,

        // BrownDustX
        locateGamePath,
        validateGamePath,

        // themes
        availableThemes: availableThemes,
    }
})
