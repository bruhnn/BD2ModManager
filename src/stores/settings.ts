import { computed, readonly, ref } from "vue";
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
    // Persisted mod filter state
    modFilterOnlyEnabled: boolean,
    modFilterOnlyDisabled: boolean,
    modFilterOnlyConflicts: boolean,
    modFilterOnlyErrors: boolean,
    modFilterHideErrors: boolean,
    modFilterTypes: string[],
}

export const useSettingsStore = defineStore("settings", () => {
    const settings = ref<Settings>({} as Settings)
    const loggingStore = useLoggingStore()

    const checkingForAppUpdates = ref(false)
    const appUpdateStatus = ref<{
        checking: boolean,
        version?: string,
        currentVersion?: string,
        downloadUrl?: string,
        changelog?: string[],
    } | null>({
        checking: false,
    })

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

    function getAppVersion(): Promise<string | null> {
        return invoke('get_app_version')
    }

    function getModPreviewVersion(): Promise<string | null> {
        return invoke('get_mod_preview_version')
    }

    async function checkForAppUpdate() {
        checkingForAppUpdates.value = true
        appUpdateStatus.value = null

        try {
            // it will block untils downloades finisih
            await invoke<{ version: string, currentVersion: string, downloadUrl?: string, changelog?: string[] }>('check_for_app_update').then((result) => {
                if (result) {
                    appUpdateStatus.value = {
                        checking: false,
                        version: result.version,
                        currentVersion: result.currentVersion,
                        downloadUrl: result.downloadUrl,
                        changelog: result.changelog,
                    }
                }
            })
        } catch (err) {
            appUpdateStatus.value = null
            loggingStore.logError("Failed to check for app update", err)
        } finally {
            checkingForAppUpdates.value = false
        }

        return appUpdateStatus.value
    }

    async function installAppUpdate() {
        await invoke('install_app_update')
    }

    function checkForModPreviewUpdate() {
        return invoke('check_for_mod_preview_update')
    }

    function updateModPreview() {
        return invoke('update_mod_preview')
    }

    function updateGameData() {
        return invoke('update_game_data')
    }

    // it will stay on settings for now
    function getBrowndustxVersion(): Promise<{
        status: "Installed" | "NotInstalled" | "InstalledButOutdated" | null,
        version: string
    } | null> {
        return invoke('get_browndustx_version')
    }

    function getGameVersion(): Promise<string | null> {
        return invoke('get_game_version')
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
        appUpdateStatus: readonly(computed(() => ({
            checking: checkingForAppUpdates.value,
            ...(appUpdateStatus.value ?? {}),
        }))),

        loadSettings,
        getSettings,
        saveSettings,

        // version/update
        getAppVersion,
        getModPreviewVersion,
        getBrowndustxVersion,
        getGameVersion,
        checkForAppUpdate,
        checkForModPreviewUpdate,
        updateModPreview,
        updateGameData,
        installAppUpdate,

        // BrownDustX
        locateGamePath,
        validateGamePath,

        // themes
        availableThemes: availableThemes,
    }
})