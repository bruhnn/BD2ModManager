<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';

import NavigationButton from './NavigationButton.vue';
import NavigationSection from './NavigationSection.vue'
import { Bolt, Component, Play, Puzzle, Settings, Users } from 'lucide-vue-next';
import { useModsStore } from '../../stores/mods';
import { invoke } from '@tauri-apps/api/core';
import { useSettingsStore } from '../../stores/settings';
import { useI18n } from 'vue-i18n';
import { useConfirm } from '../../plugins/ConfirmService';
import { useLoggingStore } from '../../stores/logging';
import Select from '../common/Select.vue';
import { useProfilesStore } from '../../stores/profiles.ts';
import MultiButton from '../common/MultiButton.vue';
import { useNotificationStore } from '../../stores/notification.ts';

const { t } = useI18n()
const notificationStore = useNotificationStore()
const confirm = useConfirm()
const loggingStore = useLoggingStore()
const settingsStore = useSettingsStore()
const gameVersion = ref<string | null>(null)
const { isSyncNeeded } = useModsStore()
const { getGameVersion } = useSettingsStore()

onMounted(async () => {
    gameVersion.value = await getGameVersion()
})

async function launchGame(vanilla: boolean = false) {
    if (await isSyncNeeded() && !vanilla) {
        const result = await confirm.confirm({
            title: t('sidebar.confirmations.unsyncedMods.title'),
            message: t('sidebar.confirmations.unsyncedMods.message'),
            acceptButton: { label: t('sidebar.confirmations.unsyncedMods.actions.launchAnyway') },
            rejectButton: { label: t('common.actions.cancel') }
        })
        if (!result.confirmed) return
    }

    await invoke("launch_game", {
            vanilla
        }).then(() => {
            notificationStore.add({ severity: 'success', title: t('sidebar.notifications.gameLaunched.title'), duration: 3000 })
        }).catch((error) => {
            loggingStore.logError('Failed to launch game', error)
            notificationStore.add({ severity: 'error', title: t('sidebar.notifications.gameLaunchError.title'), message: t('sidebar.notifications.gameLaunchError.description'), duration: 5000 })
        })
}

const headerImage = computed(() => {
    if (import.meta.env.DEV) return `headers/header7.png`
    return `headers/header${Math.floor(Math.random() * 7) + 1}.png`
})

watch(() => settingsStore.settings.gameDirectory, (gameDir) => {
    if (gameDir) getGameVersion().then(v => { gameVersion.value = v })
})

const profilesStore = useProfilesStore()
function onProfileSelected(profile_id: string) {
    profilesStore.switchProfile(profile_id)
}
</script>

<template>
    <div
        class="flex flex-col min-h-0 h-full gap-0 overflow-y-auto min-w-70 max-w-70 border-r border-border-subtle bg-surface-panel">

        <!-- header -->
        <div class="h-32 flex items-center flex-col justify-center gap-1 relative overflow-hidden">
            <span class="font-cinzel font-bold text-xl">BROWNDUST II</span>
            <span v-if="gameVersion" class="text-xs font-semibold flex gap-2 items-center justify-center">
                Game v{{ gameVersion }}
            </span>
            <img :src="headerImage"
                class="absolute inset-0 w-full h-full object-cover opacity-35 mask-[linear-gradient(to_bottom,black_50%,transparent_100%)] pointer-events-none select-none" />
        </div>

        <!-- navigation -->
        <div>
            <NavigationSection :title="$t('sidebar.sections.navigation')">
                <NavigationButton :icon="Component" :label="$t('sidebar.tabs.mods')" value="mods" />
                <NavigationButton :icon="Users" :label="$t('sidebar.tabs.characters')" value="characters" />
                <NavigationButton icon-src="/icons/dating.png" :label="$t('sidebar.tabs.dating')" value="dating" />
            </NavigationSection>
            <NavigationSection :title="$t('sidebar.sections.settings')">
                <NavigationButton :icon="Bolt" :label="$t('sidebar.tabs.profiles')" value="profiles" />
                <NavigationButton :icon="Puzzle" :label="$t('sidebar.tabs.browndustx')" value="bdx" />
                <NavigationButton :icon="Settings" :label="$t('sidebar.tabs.settings')" value="settings" />
            </NavigationSection>
        </div>

        <!-- profile section -->
        <div>
            <NavigationSection :title="$t('sidebar.sections.currentProfile')">
                <Select :model-value="profilesStore.activeProfileId"
                    :options="profilesStore.sortedProfiles.map(p => ({ label: p.name, value: p.id }))"
                    :placeholder="$t('sidebar.sections.currentProfilePlaceholder')"
                    @update:model-value="onProfileSelected" size="lg" />
            </NavigationSection>
        </div>

        <span class="flex-1" />

        <!-- <span class="border border-border-subtle h-px w-full"></span> -->
         
        <div class="m-2 flex flex-col gap-1">
            <MultiButton :label="$t('sidebar.actions.launchGame')" :icon="Play" variant="primary" size="lg"
                class="w-full [&>button:first-child]:flex-1" @click="launchGame()"
                :actions="[
                    {
                        label: $t('sidebar.actions.launchGameWithoutMods'),
                        icon: Play,
                        clicked: () => launchGame(true)
                    },
                ]" />
        </div>
    </div>
</template>

<style scoped></style>