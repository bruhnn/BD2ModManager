import { defineStore } from "pinia";
import { readonly, ref, watch } from "vue";
import { useSettingsStore } from "./settings";
import { invoke } from "@tauri-apps/api/core";
import { useLoggingStore } from "./logging";

// #[derive(Serialize)]
// #[serde(tag = "type", content = "reason")]
// pub enum CanRemove {
//     Yes,
//     No(String),
// }

type CanRemove = { type: "Yes" } | { type: "No"; reason: string }

interface VersionInfo {
    status: "Installed" | "InstalledButOutdated" | "NotInstalled",
    version: string,
    canRemove: CanRemove,
    canConfigure: boolean
}

export const useGameStore = defineStore("game", () => {
    const loggingStore = useLoggingStore()

    const settingsStore = useSettingsStore()

    const gameVersion = ref<string | null>(null)
    const bepinexVersion = ref<VersionInfo | null>(null)
    const browndustxVersion = ref<VersionInfo | null>(null)
    const configurationManagerVersion = ref<VersionInfo | null>(null)

    const isGameRunning = ref<boolean>(false)

    async function launchGame() {}

    async function refresh() {
        if (!settingsStore.settings.gameDirectory) {
            gameVersion.value = null
            browndustxVersion.value = null
            configurationManagerVersion.value = null
            return
        }

        const [game, bepinex, bdx, configManager] = await Promise.all([
            invoke<string | null>('get_game_version'),
            invoke<VersionInfo | null>('get_bepinex_version'),
            invoke<VersionInfo | null>('get_browndustx_version'),
            invoke<VersionInfo | null>('get_configmanager_version'),
        ])

        loggingStore.logDebug("Game:", game)
        loggingStore.logDebug("BepInEx:", JSON.stringify(bepinex))
        loggingStore.logDebug("BrowndustX:", JSON.stringify(bdx))
        loggingStore.logDebug("Configuration Manager:", JSON.stringify(configManager))

        gameVersion.value = game
        bepinexVersion.value = bepinex
        browndustxVersion.value = bdx
        configurationManagerVersion.value = configManager
    }

    watch(
        () => settingsStore.settings.gameDirectory,
        (_) => {
            // always refresh when game directory changes, even if it's null
            refresh()
        },
        {
            immediate: true
        }
    )

    return {
        gameVersion: readonly(gameVersion),
        bepinexVersion: readonly(bepinexVersion),
        browndustxVersion: readonly(browndustxVersion),
        configurationManagerVersion: readonly(configurationManagerVersion),
        isGameRunning: readonly(isGameRunning),
        launchGame,
        refresh
    }
})