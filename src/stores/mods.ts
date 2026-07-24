import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { defineStore } from 'pinia';
import { computed, readonly, ref, shallowRef } from 'vue';
import { Character, useCharactersStore } from './characters';
import { useLoggingStore } from './logging';
import { useProfilesStore } from './profiles';

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
export const useModsStore = defineStore('mods', () => {
    const charactersStore = useCharactersStore()
    const loggingStore = useLoggingStore()

    const mods = shallowRef<BD2Mod[]>([]);
    const modsCache = ref<Map<string, BD2Mod>>(new Map());

    const extendedMods = computed(() => {
        return mods.value.map((mod) => {
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

    function getModByName(name: string): BD2Mod | undefined {
        return modsCache.value.get(name);
    }

    async function discoverMods() {
        return invoke("discover_mods")
    }

    async function enableMods(mod_names: String[]) {
        return invoke("enable_mods", { modNames: mod_names })
    }

    // Enable mods in a specific profile (may differ from the active one).
    async function enableModsInProfile(profileId: string, mod_names: string[]) {
        return invoke("enable_mods_in_profile", { profileId, modNames: mod_names })
    }

    async function disableMods(mod_names: String[]) {
        return invoke("disable_mods", { modNames: mod_names })
    }

    async function previewMod(mod_name: string) {
        const mod = getModByName(mod_name);

        if (!mod) {
            loggingStore.logError(`previewMod: Mod not found: ${mod_name}`);
            return
        }

        return invoke("preview_mod", { path: mod.path })
    }

    async function installModFromZip(path: string) {
        return invoke("install_mod_from_zip", { path })
    }

    async function installModFromFolder(path: string) {
        return await invoke("install_mod_from_folder", { path })
    }

    async function syncMods() {
        return invoke("sync_mods")
    }

    async function unsyncMods() {
        return invoke("unsync_mods")
    }

    async function deleteMods(mod_names: String[]) {
        return invoke("delete_mods", { modNames: mod_names })
    }

    async function renameMod(oldName: string, newName: string) {
        const mod = getModByName(oldName);
        if (!mod) {
            loggingStore.logError(`renameMod: Mod not found: ${oldName}`);
            return;
        }

        return invoke("rename_mod", { oldName, newName })
    }

    async function setModAuthor(modNames: string | string[], author: string | null) {
        const names = Array.isArray(modNames) ? modNames : [modNames];
        return invoke("set_mod_author", { modNames: names, author: author || null });
    }

    async function isSyncNeeded(): Promise<boolean> {
        // on rust backend it will compare the current modlist with the manifest inside game folder, if different then it needs to sync
        return invoke("is_sync_needed")
    }

    // events
    listen("mods-changed", async (event) => {
        // triggered on discover mods, enable/disable mods, profile switch
        loggingStore.logInfo("Mods updated event received");

        const modsList = event.payload as BD2Mod[];

        mods.value = modsList;

        modsCache.value.clear();
        modsList.forEach((mod) => {
            modsCache.value.set(mod.name, mod);
        }
        );

        try {
            await useProfilesStore().loadProfiles();
        } catch (error) {
            loggingStore.logError("Failed to refresh profiles after mods change:", error);
        }
    })

    return {
        mods: readonly(extendedMods),
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
        renameMod,
        enableModsInProfile
    }
})