<script setup lang="ts">
import { Bolt, ChevronRight, Component, Play, Puzzle, Settings, Users } from '@lucide/vue';

import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import { invoke } from '@tauri-apps/api/core';

import { useModsStore } from '../../stores/mods';
import { useLoggingStore } from '../../stores/logging';
import { useProfilesStore } from '../../stores/profiles.ts';
import { useNotificationStore } from '../../stores/notification.ts';
import { useGameStore } from '../../stores/game.ts';
import { useConfirm } from '../../plugins/ConfirmService';

import NavigationSection from './NavigationSection.vue'
import NavigationButton from './NavigationButton.vue';
import MultiButton from '../common/MultiButton.vue';
import Select from '../common/Select.vue';
import { globalModals } from '../../composables/useGlobalModals.ts';

const { t } = useI18n()
const notificationStore = useNotificationStore()
const confirm = useConfirm()
const loggingStore = useLoggingStore()
const modsStore = useModsStore()
const gameStore = useGameStore()

async function launchGame(vanilla: boolean = false) {
    if (modsStore.isSyncNeeded && !vanilla) {
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
            notificationStore.add({ type: 'success', title: t('sidebar.notifications.launchGame.success.title'), duration: 3000 })
        }).catch((error) => {
            loggingStore.logError('Failed to launch game', error)
            notificationStore.add({ type: 'error', title: t('sidebar.notifications.launchGame.error.title'), message: t('sidebar.notifications.launchGame.error.message'), duration: 5000 })
        })
}

const headerImage = computed(() => {
    if (import.meta.env.DEV) return `headers/header7.webp`
    return `headers/header${Math.floor(Math.random() * 13) + 1}.webp`
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
        <div class="h-32 flex items-center flex-col justify-center gap-1 relative shrink-0 group-hover">
            <span class="font-cinzel font-bold text-xl z-2">BROWNDUST II</span>
            <span v-if="gameStore.gameVersion" class="text-xs font-semibold flex gap-2 items-center justify-center z-2">
                Game v{{ gameStore.gameVersion }}
            </span>
            <img :src="headerImage"
                class="absolute top-0 inset-x-0 w-full h-48 object-cover opacity-60 group-hover:opacity-100 mask-[linear-gradient(to_bottom,black_0%,rgba(0,0,0,.6)_45%,rgba(0,0,0,.2)_75%,transparent_100%)] pointer-events-none select-none" />
        </div>

        <!-- navigation -->
        <div class="relative">
            <NavigationSection :title="$t('sidebar.sections.navigation')">
                <NavigationButton :icon="Component" :label="$t('sidebar.tabs.mods')" value="mods" />
                <NavigationButton :icon="Users" :label="$t('sidebar.tabs.characters')" value="characters" />
            </NavigationSection>
            <NavigationSection :title="$t('sidebar.sections.settings')">
                <NavigationButton :icon="Bolt" :label="$t('sidebar.tabs.profiles')" value="profiles" />
                <NavigationButton :icon="Puzzle" :label="$t('sidebar.tabs.modLoader')" value="mod-loader" />
                <NavigationButton :icon="Settings" :label="$t('sidebar.tabs.settings')" value="settings" />
            </NavigationSection>
        </div>

        <!-- profile section -->
        <div class="relative">
            <NavigationSection :title="$t('sidebar.sections.currentProfile')">
                <Select :model-value="profilesStore.activeProfileId"
                    :options="profilesStore.sortedProfiles.map(p => ({ label: p.name, value: p.id }))"
                    :placeholder="$t('sidebar.sections.currentProfilePlaceholder')"
                    @update:model-value="onProfileSelected" size="lg" />
            </NavigationSection>
        </div>

        <span class="flex-1" />

        <!-- <span class="border border-border-subtle h-px w-full"></span> -->
        <div class="mx-2 flex">
            <button class="bg-transparent text-sm text-text-secondary cursor-pointer flex w-full items-center justify-between gap-1 px-2 py-2 rounded-md hover:bg-state-hover transition-all duration-150 ease-in-out"
            @click="globalModals.whatsNew.showModal()">
                {{ $t("whatsNew.title") }}
                <ChevronRight class="w-4 h-4 text-text-secondary inline-block" />
            </button>
        </div>
         
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
