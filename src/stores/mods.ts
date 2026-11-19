import { Channel, invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { defineStore } from 'pinia';
import { computed, readonly, ref } from 'vue';
import { Character, useCharactersStore } from './characters';
import { useLoggingStore } from './logging';
import { useDebounceFn } from '@vueuse/core';
import { useSettingsStore } from './settings';
import { useProfilesStore } from './profiles';
import { useNotificationStore } from './notification';
import { getErrorMessage } from '../utils/errors';
import { useI18n } from 'vue-i18n';
import { SyncResult } from '../composables/useModSyncEvents';
import { useSyncStateStore } from './syncState';
import { isInstallingAppUpdate } from '../composables/useUpdater';
import { globalModals } from '../composables/useGlobalModals';

export type BD2ModType =
    | { type: 'Standing'; id: string }
    | { type: 'Cutscene'; id: string }
    | { type: 'Scene'; id: string }
    | { type: 'NPC'; id: string }
    | { type: 'Dating'; id: string; real_id: string }
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

export interface ConvertedMod {
    modName: string,
    gameFolder: string,
    gameVersion: string,
    stagingVersion: string,
}

export interface ConvertedModsInfo {
    mods: ConvertedMod[],
    defaultBackupDirectory: string,
}

export interface CopyConvertedModsResult {
    copied: string[],
    failed: { modName: string, error: string }[],
    backupPath: string | null,
}

// export function isError

export const useModsStore = defineStore('mods', () => {
    const { t } = useI18n()
    const settingsStore = useSettingsStore()
    const charactersStore = useCharactersStore()
    const loggingStore = useLoggingStore()
    const notificationStore = useNotificationStore()

    const modsCache = ref<Map<string, BD2Mod>>(new Map())

    const autoSyncMs = computed(() => settingsStore.settings.autoSyncModsDelay)

    // is syncing or unsycing too
    const isSyncing = ref(false);
    const isSyncNeeded = ref(false);
    const isSyncBlocked = computed(() => {
        return settingsStore.settings.useGameFolderAsStaging && settingsStore.settings.gameDirectory !== null

        // if (!settingsStore.settings.gameDirectory) return true
        // if (!settingsStore.settings.stagingDirectory) return true

        // let gameMods = `${settingsStore.settings.gameDirectory}/BepInEx/plugins/BrownDustX/mods`
        // let staging = settingsStore.settings.stagingDirectory
        
        // const normalizePath = (path: string) => {
        
        // const normalized = path.replace(/\\/g, '/').replace(/\/+$/, '');
        // return /^[a-z]:/i.test(normalized) ? normalized.toLowerCase() : normalized;
        // };

        // const stagingPath = normalizePath(staging);
        // const gameModsPath = normalizePath(gameMods);

        // if (
        //     stagingPath === gameModsPath ||
        //     stagingPath.startsWith(`${gameModsPath}/`) ||
        //     gameModsPath.startsWith(`${stagingPath}/`)
        // ) {
        //     return true
        // }
    })

    const debouncedSync = useDebounceFn(async () => {
        if (!settingsStore.settings.autoSyncMods || settingsStore.settings.useGameFolderAsStaging) return;

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
                title: t("modsTab.notifications.autoSync.error.title"),
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
        await checkIsSyncNeeded()
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
            checkIsSyncNeeded()
            return mods
        } catch (error) {
            for (const mod of previousStates) {
                if (mod.enabled !== undefined) {
                    setModsState([mod.name], mod.enabled)
                }
            }

            // with the game folder as staging some mods may have been moved before the error
            if (settingsStore.settings.useGameFolderAsStaging) {
                await discoverMods().catch(e => loggingStore.logError('Failed to refresh mods after a failed toggle:', e))
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
            checkIsSyncNeeded()
            return mods
        } catch (error) {
            for (const mod of previousStates) {
                if (mod.enabled !== undefined) {
                    setModsState([mod.name], mod.enabled)
                }
            }

            // with the game folder as staging some mods may have been moved before the error
            if (settingsStore.settings.useGameFolderAsStaging) {
                await discoverMods().catch(e => loggingStore.logError('Failed to refresh mods after a failed toggle:', e))
            }

            throw error
        }
    }
    async function previewMods(modNames: string[]): Promise<void> {
        return invoke("preview_mods", { modNames })
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
            checkIsSyncNeeded()
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
        await useProfilesStore().loadProfiles()
        debouncedSync()
        checkIsSyncNeeded()
        return mod
    }

    async function syncMods(removeUnmanagedMods: boolean = false): Promise<SyncResult | undefined> {
        if (isInstallingAppUpdate.value) return
        if (isSyncing.value) {
            // add to queue or just log?
            // raise an error?
            // let the backend handle it? raise an error etc
            loggingStore.logDebug("Sync in progress, skipping sync.");
            return
        }

        if (isSyncBlocked.value) {
            loggingStore.logDebug("Sync is blocked due to settings, skipping sync. Probably you enabled 'Use game folder as staging' and the game directory is set, which blocks sync.");
            return
        }

        debouncedSync.cancel()

        isSyncing.value = true;
        try {
            await useSyncStateStore().ready
            if (!(await resolveConvertedMods())) {
                loggingStore.logDebug("Sync cancelled: converted mods were not copied to the mods folder.");
                return
            }
            let result = await invoke<SyncResult>("sync_mods", { removeUnmanagedMods })
            
            return result
        } finally {
            if (removeUnmanagedMods) {
                try {
                    await discoverMods()
                } catch (error) {
                    loggingStore.logError('Failed to refresh mods after sync:', error)
                }
            }
            try {
                await checkIsSyncNeeded()
            } catch (error) {
                loggingStore.logError('Failed to check if sync is needed:', error)
            }
            isSyncing.value = false;
        }
    }

    // mods converted in the game folder (ex. by BrownDustX) would be overwritten by sync,
    // so ask to copy them to the mods folder first. Resolves false if the sync should stop.
    async function resolveConvertedMods(): Promise<boolean> {
        const info = await getConvertedMods()
        if (!info.mods.length) return true

        loggingStore.logInfo(`Found ${info.mods.length} mod(s) converted in the game folder.`)
        return new Promise<boolean>((resolve) => {
            globalModals.convertedMods.showModal({
                mods: info.mods,
                defaultBackupDirectory: info.defaultBackupDirectory,
                onResolve: resolve,
            })
        })
    }

    function getConvertedMods(): Promise<ConvertedModsInfo> {
        return invoke<ConvertedModsInfo>("get_converted_mods")
    }

    function copyConvertedMods(modNames: string[], backupDirectory: string | null): Promise<CopyConvertedModsResult> {
        return invoke<CopyConvertedModsResult>("copy_converted_mods", { modNames, backupDirectory })
    }

    async function unsyncMods(removeUnmanagedMods: boolean = false): Promise<SyncResult | undefined> {
        if (isInstallingAppUpdate.value) return
        if (isSyncing.value) {
            loggingStore.logDebug("Sync in progress, skipping unsync.");
            return;
        }

        debouncedSync.cancel()

        isSyncing.value = true;
        try {
            await useSyncStateStore().ready
            // unsync deletes the game copies, the conversion would be lost
            if (!(await resolveConvertedMods())) {
                loggingStore.logDebug("Unsync cancelled: converted mods were not copied to the mods folder.");
                return
            }
            let result = await invoke<SyncResult>("unsync_mods", { removeUnmanagedMods })
            
            return result
        } finally {
            if (removeUnmanagedMods) {
                try {
                    await discoverMods()
                } catch (error) {
                    loggingStore.logError('Failed to refresh mods after unsync:', error)
                }
            }
            try {
                await checkIsSyncNeeded()
            } catch (error) {
                loggingStore.logError('Failed to check if sync is needed:', error)
            }
            isSyncing.value = false;
        }
    }

    async function checkIsSyncNeeded(): Promise<boolean> {
        let result = await invoke<boolean>("is_sync_needed")
        isSyncNeeded.value = result
        return result
    }

    async function setModAuthor(modNames: string | string[], author: string | null): Promise<BD2Mod[]> {
        const names = Array.isArray(modNames) ? modNames : [modNames]
        const mods = await invoke<BD2Mod[]>("set_mod_author", { modNames: names, author })
        updateMods(mods)
        return mods
    }

    function applyPreviewModChanges(mods: BD2Mod[]) {
        updateMods(mods)
        debouncedSync()
        checkIsSyncNeeded().catch(error => loggingStore.logError("Failed to check if sync is needed:", error))
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
        isSyncNeeded: readonly(isSyncNeeded),
        isSyncBlocked: readonly(isSyncBlocked),
        discoverMods,
        applyPreviewModChanges,
        enableMods,
        disableMods,
        previewMods,
        installModFromZip,
        installModFromFolder,
        syncMods,
        unsyncMods,
        setModAuthor,
        checkIsSyncNeeded,
        deleteMods,
        renameMod,
        copyConvertedMods
    }
})
