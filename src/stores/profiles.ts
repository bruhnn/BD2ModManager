import { invoke } from "@tauri-apps/api/core";
import { defineStore } from "pinia";
import { ref, computed } from "vue";

export interface Profile {
    id: string,
    name: string,
    description: string,
    createdAt: string,
    active: boolean,
    enabledMods: Array<string>
}

interface ProfilesState {
    activeProfile: Profile | null,
    profiles: Array<Profile>
}

export const useProfilesStore = defineStore("profiles", () => {
    const activeProfile = ref<Profile | null>(null);
    const activeProfileId = ref<string | null>(null);
    const profiles = ref<Profile[]>([]);

    const sortedProfiles = computed(() => {
        return [...profiles.value].sort((a, b) => {
            if (a.id === "default") return -1;
            if (b.id === "default") return 1;
            return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime();
        });
    });

    async function loadProfiles() {
        const result = await invoke<ProfilesState>("get_profiles");
        activeProfile.value = result.activeProfile;
        activeProfileId.value = result.activeProfile?.id || null;
        profiles.value = result.profiles;
    }

    async function switchProfile(id: string) {
        await invoke("switch_profile", { id });
        activeProfile.value = getProfileById(id);
        activeProfileId.value = id;
    }

    async function createProfile(name: string, description: string | null, templateId: string | null) {
        await invoke("create_profile", { name, description, templateId });
        await loadProfiles();
    }

    async function deleteProfile(id: string) {
        await invoke("delete_profile", { id });
        await loadProfiles();
    }

    async function editProfile(id: string, name: string, description: string | null) {
        await invoke("edit_profile", { id, name, description });
        await loadProfiles();
    }

    function getProfileById(id: string): Profile | null {
        return profiles.value.find(p => p.id === id) || null;
    }

    // Replace a profile's entire enabled-mods list.
    async function setProfileEnabledMods(id: string, modNames: string[]) {
        await invoke("set_profile_enabled_mods", { profileId: id, modNames });
        await loadProfiles();
    }

    return {
        activeProfile,
        activeProfileId,
        profiles,
        sortedProfiles,
        loadProfiles,
        switchProfile,
        createProfile,
        deleteProfile,
        getProfileById,
        editProfile,
        setProfileEnabledMods
    };
});