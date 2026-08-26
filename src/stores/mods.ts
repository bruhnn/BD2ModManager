import { Channel, invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { defineStore } from 'pinia';
import { computed, readonly, ref } from 'vue';
import { Character, useCharactersStore } from './characters';
import { useLoggingStore } from './logging';
import { useDebounceFn } from '@vueuse/core';
import { useSettingsStore } from './settings';
import { useNotificationStore } from './notification';
import { getErrorMessage } from '../utils/errors';
import { useI18n } from 'vue-i18n';

export type BD2ModType =
    | { type: 'Standing'; id: string }
    | { type: 'Cutscene'; id: string }
    | { type: 'Scene'; id: string }
    | { type: 'NPC'; id: string }
    | { type: 'Dating'; id: string }
    | { type: 'Minigame' };

export interface BD2Mod {
    path: string,
    name: string,
    displayName: string,
    modType: BD2ModType,
    errors: readonly string[],
    conflictsWith: readonly string[],
    enabled: boolean,
    author?: string,
}

export interface BD2ModExtended extends BD2Mod {
    character?: Character
    conflictingMods: readonly BD2Mod[]
}

export interface ModDeleteError {
    type: "ModNotFound" | "PathNotFound" | "Io"
    details: {
        mod_name?: string
        path?: string
        kind?: string
    } | null
    message: string
}

export interface DeleteModsProgress {
    current: number,
    total: number,
    modName: string,
}

export interface DeleteModsResult {
    mods: BD2Mod[],
    deleted: readonly string[],
    failed: Record<string, ModDeleteError>,
}

export const useModsStore = defineStore('mods', () => {
    const { t } = useI18n()
    const settingsStore = useSettingsStore()
    const charactersStore = useCharactersStore()
    const loggingStore = useLoggingStore()
    const notificationStore = useNotificationStore()

    const modsCache = ref<Map<string, BD2Mod>>(new Map())

    const autoSyncMs = 3000

    // is syncing or unsycing too
    const isSyncing = ref(false);

    const debouncedSync = useDebounceFn(async () => {
        if (!settingsStore.settings.autoSyncMods) return;

        loggingStore.logDebug("Auto-syncing mods.");

        if (isSyncing.value) {
            loggingStore.logDebug("Sync in progress, skipping auto-sync.");
            return;
        }

        try {
            await syncMods();
        } catch (error) {
            loggingStore.logError(`An error occurred while auto-syncing mods: ${JSON.stringify(error)}`);

            notificationStore.add({
                type: "error",
                title: t("modsTab.notifications.autoSync.title"),
                message: getErrorMessage(t, error)
            });
        }
    }, autoSyncMs)

    const mods = computed<BD2Mod[]>(() => {
        return getMods()
    })

    const extendedMods = computed<BD2ModExtended[]>(() => {
        return getMods().map((mod) => {
            let character: Character | undefined = undefined;

            if (mod.modType && (mod.modType.type == "Cutscene" || mod.modType.type == "Standing")) {
                character = charactersStore.getCharacterById(mod.modType.id) ?? undefined
            } else if (mod.modType && mod.modType.type == "Dating") {
                character = charactersStore.getCharacterByDatingId(mod.modType.id) ?? undefined
            } else if (mod.modType && mod.modType.type == "NPC") {
                character = charactersStore.getCharacterByNpcId(mod.modType.id) ?? undefined
            }

            let conflictingMods: BD2Mod[] = []

            if (mod.enabled && mod.conflictsWith.length > 0) {
                mod.conflictsWith.forEach((modName) => {
                    let conflictingMod = getModByName(modName)
                    if (conflictingMod && conflictingMod.enabled) {
                        conflictingMods.push(conflictingMod)
                    }
                })
            }

            return { ...mod, character, conflictingMods }
        })
    })

    function getMods(): BD2Mod[] {
        return Array.from(modsCache.value.values());
    }

    function setMods(newMods: BD2Mod[]) {
        modsCache.value = new Map(newMods.map(m => [m.name, m]))
    }

    function updateMods(mods: BD2Mod[]) {
        mods.forEach((mod) => {
            modsCache.value.set(mod.name, mod)
        })
    }

    function getModByName(name: string): BD2Mod | undefined {
        return modsCache.value.get(name);
    }

    function setModsState(modNames: string[], state: boolean) {
        for (let modName of modNames) {
            let mod = getModByName(modName)
            if (mod) {
                mod.enabled = state
            }
        }
    }

    async function discoverMods(): Promise<BD2Mod[]> {
        const mods = await invoke<BD2Mod[]>("discover_mods")
        setMods(mods)
        return mods
    }

    async function enableMods(modNames: string[]): Promise<BD2Mod[]> {
        const previousStates = modNames.map(name => ({
            name,
            enabled: getModByName(name)?.enabled
        }))

        setModsState(modNames, true)

        try {
            const mods = await invoke<BD2Mod[]>("enable_mods", { modNames })
            updateMods(mods)
            debouncedSync()
            return mods
        } catch (error) {
            for (const mod of previousStates) {
                if (mod.enabled !== undefined) {
                    setModsState([mod.name], mod.enabled)
                }
            }

            throw error
        }
    }

    async function disableMods(modNames: string[]): Promise<BD2Mod[]> {
        const previousStates = modNames.map(name => ({
            name,
            enabled: getModByName(name)?.enabled
        }))

        setModsState(modNames, false)

        try {
            const mods = await invoke<BD2Mod[]>("disable_mods", { modNames })
            updateMods(mods)
            debouncedSync()
            return mods
        } catch (error) {
            for (const mod of previousStates) {
                if (mod.enabled !== undefined) {
                    setModsState([mod.name], mod.enabled)
                }
            }

            throw error
        }
    }
    async function previewMod(modName: string): Promise<undefined> {
        return invoke("preview_mod", { modName })
    }

    async function installModFromZip(path: string): Promise<BD2Mod> {
        const mod = await invoke<BD2Mod>("install_mod_from_zip", { path })
        updateMods([mod])
        return mod
    }

    async function installModFromFolder(path: string): Promise<BD2Mod> {
        const mod = await invoke<BD2Mod>("install_mod_from_folder", { path })
        updateMods([mod])
        return mod
    }

    async function deleteMods(modNames: string[], onProgress?: (progress: DeleteModsProgress) => void): Promise<DeleteModsResult> {
        const channel = new Channel<DeleteModsProgress>()
        if (onProgress) channel.onmessage = onProgress
        const result = await invoke<DeleteModsResult>("delete_mods", { modNames, onProgress: channel })
        console.log("DeleteModsResult:", result)
        if (result.deleted.length > 0) {
            // only updates the mods list if at least one mod was deleted, otherwise it will be the same as before
            setMods(result.mods)
            debouncedSync()
        }
        return result
    }

    async function renameMod(modName: string, newName: string): Promise<BD2Mod> {
        const mod = await invoke<BD2Mod>("rename_mod", { modName, newName })
        if (mod) {
            // add the new mod
            updateMods([mod])
            // remove the old mod
            modsCache.value.delete(modName)
        }
        debouncedSync()
        return mod
    }

    async function syncMods(): Promise<undefined> {
        if (isSyncing.value) {
            // add to queue or just log?
            // raise an error?
            // let the backend handle it? raise an error etc
            loggingStore.logDebug("Sync in progress, skipping sync.");
            return
        }

        isSyncing.value = true;
        try {
            return await invoke("sync_mods")
        } finally {
            isSyncing.value = false;
        }
    }

    async function unsyncMods(): Promise<undefined> {
        if (isSyncing.value) {
            loggingStore.logDebug("Sync in progress, skipping unsync.");
            return;
        }

        isSyncing.value = true;
        try {
            return await invoke("unsync_mods")
        } finally {
            isSyncing.value = false;
        }
    }

    async function isSyncNeeded(): Promise<boolean> {
        // on rust backend it will compare the current modlist with the manifest inside game folder, if different then it needs to sync
        return invoke<boolean>("is_sync_needed")
    }

    async function setModAuthor(modNames: string | string[], author: string | null): Promise<BD2Mod[]> {
        const names = Array.isArray(modNames) ? modNames : [modNames]
        const mods = await invoke<BD2Mod[]>("set_mod_author", { modNames: names, author })
        updateMods(mods)
        return mods
    }

    // events
    listen<BD2Mod[]>("mods-changed", async () => {
        notificationStore.add({
            type: "info",
            title: "Backend is asking to refresh mods.",
            duration: 15000
        })

        await discoverMods()
    })

    return {
        mods: readonly(mods),
        extendedMods: readonly(extendedMods),
        isSyncing: readonly(isSyncing),
        discoverMods,
        enableMods,
        disableMods,
        previewMod,
        installModFromZip,
        installModFromFolder,
        syncMods,
        unsyncMods,
        setModAuthor,
        isSyncNeeded,
        deleteMods,
        renameMod
    }
})
