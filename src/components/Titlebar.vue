<script setup lang="ts">
import { Minus, Square, SquareStop, X, Check, AlertTriangle, RotateCw, ScrollText, Heart, Sparkles } from '@lucide/vue';
import GithubIcon from './icons/GithubIcon.vue';
import KofiIcon from './icons/KofiIcon.vue';
import AfDianIcon from './icons/AfDianIcon.vue';
import ActiveDownloads from './ActiveDownloads.vue';

import { computed, ref, watch, onUnmounted } from 'vue';
import { refThrottled } from '@vueuse/core';
import { useI18n } from 'vue-i18n';

import { UnlistenFn } from '@tauri-apps/api/event';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { openUrl } from '@tauri-apps/plugin-opener';

import { SyncStatus, useSyncStateStore } from '../stores/syncState';
import { useNotificationStore } from '../stores/notification';
import { useLoggingStore } from '../stores/logging';

import { AppUpdateAvailable, UpdateStatus, useUpdater } from '../composables/useUpdater.ts';
import { getSyncErrorMessage, SyncType } from '../composables/useModSyncEvents.ts';
import { globalModals } from '../composables/useGlobalModals.ts';
import { useAppVersion } from '../composables/useAppVersion.ts';
import { usePortable } from '../composables/usePortable';
import { useLocale } from '../composables/useLocale.ts';
import { getErrorMessage } from '../utils/errors';

const unlistenFunctions = ref<UnlistenFn[]>([])

const { appVersion } = useAppVersion()
const { isChineseLanguage } = useLocale()
const { t } = useI18n()

const { isPortable } = usePortable()

const notificationStore = useNotificationStore()
const loggingStore = useLoggingStore()

const {
    appUpdate,
    downloadAppUpdate,
    installAppUpdate
} = useUpdater()

const appWindow = getCurrentWindow()
const isMaximized = ref(false)
const isUpdating = ref(false)

const syncStateStore = useSyncStateStore()
const showSyncBar = ref(false)

function closeWindow() { appWindow.close() }
function minimizeWindow() { appWindow.minimize() }
function toggleMaximizeWindow() { isMaximized.value ? appWindow.unmaximize() : appWindow.maximize() }

async function handleAppUpdateClick() {
    if (isUpdating.value) return
    if (isPortable.value) {
        // open modal
        if (appUpdate.value?.status === UpdateStatus.UpdateAvailable) {
            globalModals.updateAvailable.showModal(appUpdate.value.update as AppUpdateAvailable)
        }
        return
    }

    const isInstalling = appUpdate.value?.status === UpdateStatus.Downloaded
    isUpdating.value = true

    try {
        if (appUpdate.value?.status === UpdateStatus.UpdateAvailable) {
            await downloadAppUpdate()
        } else if (appUpdate.value?.status === UpdateStatus.Downloaded) {
            await installAppUpdate()
        }
    } catch (error) {
        loggingStore.logError(isInstalling ? "Failed to install app update" : "Failed to download app update", error)
        notificationStore.add({
            type: 'error',
            title: t(isInstalling ? 'app.notifications.appUpdate.installFailed.title' : 'app.notifications.appUpdate.downloadFailed.title'),
            message: getErrorMessage(t, error),
            duration: 5000
        })
    } finally {
        isUpdating.value = false
    }
}

function handleSyncClick() { globalModals.sync.showModal() }
function handleGithubClick() { openUrl("https://github.com/bruhnn/BD2ModManager") }
function handleLogsClick() { globalModals.logs.showModal() }
function handleAfdianClick() { openUrl("https://afdian.com/a/Bruhnn") }
function handleKofiClick() { openUrl("https://ko-fi.com/bruhnn") }
function handleOpenGithubUser() { openUrl("https://github.com/bruhnn") }

const rawSyncProgress = computed(() =>
    syncStateStore.progress.total > 0
        ? Math.round((syncStateStore.progress.current / syncStateStore.progress.total) * 100)
        : 0
)
const syncProgress = refThrottled(rawSyncProgress, 50, false, true)

watch(() => syncStateStore.status, () => {
    if (!showSyncBar.value) showSyncBar.value = true
})

onUnmounted(() => {
    unlistenFunctions.value.forEach(fn => fn())
})
</script>

<template>
    <div class="grid min-h-10 h-10 shrink-0 sticky grid-cols-[minmax(0,1fr)_auto] select-none overflow-hidden transition-[max-height] duration-300 ease-out bg-surface-app border-b border-border-subtle"
        data-tauri-drag-region>
        <div class="flex min-w-0 items-center gap-2.5 overflow-hidden px-2 py-1" data-tauri-drag-region>
            <span class="truncate font-bold text-lg select-none" data-tauri-drag-region>
                Mod Manager
            </span>
            <span class="text-xs font-semibold flex gap-2 items-center justify-center whitespace-nowrap">
                <Heart class="inline w-3.5 h-3.5 text-accent" />
                v{{ appVersion }} by
                <span class="cursor-pointer
                    bg-linear-to-r from-accent via-accent/60 to-accent
                    bg-size-[200%_100%] bg-clip-text text-transparent
                    animate-sweep hover:via-accent/80 transition-colors" @click="handleOpenGithubUser">
                    @bruhnn
                </span>
            </span>
            <transition name="slide-fade">
                <div v-if="appUpdate?.status && appUpdate.status !== UpdateStatus.Downloading"
                    class="flex min-w-0 items-center gap-1.5 text-xs font-medium"
                    :aria-disabled="isUpdating" :style="{ pointerEvents: isUpdating ? 'none' : undefined }" :class="appUpdate?.status === UpdateStatus.UpdateAvailable || appUpdate?.status === UpdateStatus.Downloaded
                        ? 'cursor-pointer text-accent'
                        : 'text-text-secondary'" @click="handleAppUpdateClick">
                    <RotateCw
                        v-if="appUpdate?.status === UpdateStatus.CheckingForUpdates || appUpdate?.status === UpdateStatus.Installing"
                        class="w-3.5 h-3.5 shrink-0 animate-spin" />
                    <Sparkles v-else class="w-3.5 h-3.5 shrink-0" />

                    <span v-if="appUpdate?.status === UpdateStatus.CheckingForUpdates" class="truncate">
                        {{ $t('titlebar.appUpdate.checking') }}
                    </span>
                    <span v-else-if="appUpdate?.status === UpdateStatus.UpdateAvailable" class="truncate">
                        {{ $t('titlebar.appUpdate.available', { version: appUpdate?.update?.versionAvailable }) }}
                    </span>
                    <span v-else-if="appUpdate?.status === UpdateStatus.Downloaded" class="truncate">
                        {{ $t('titlebar.appUpdate.downloaded', { version: appUpdate?.update?.versionAvailable }) }}
                    </span>
                    <span v-else-if="appUpdate?.status === UpdateStatus.Installing" class="truncate">
                        {{ $t('titlebar.appUpdate.updating', { version: appUpdate?.update?.versionAvailable }) }}
                    </span>
                </div>
            </transition>
        </div>

        <div class="flex min-w-0 items-stretch justify-end overflow-hidden">
            <div v-show="showSyncBar"
                class="group relative flex min-w-0 items-center justify-between gap-2 md:gap-3 mr-1 md:mr-2 py-0 px-2 my-1.5 transition-all rounded-md cursor-pointer"
                @click="handleSyncClick">
                <div
                    class="w-full h-full absolute inset-0 z-10 rounded-md group-hover:bg-state-hover transition-colors pointer-events-none" />

                <div class="flex items-center gap-2 relative z-10 flex-1 min-w-0">
                    <RotateCw v-if="syncStateStore.status === SyncStatus.SYNCING"
                        class="w-4 h-4 shrink-0 animate-spin text-accent" />
                    <Check v-else-if="syncStateStore.status === SyncStatus.COMPLETED"
                        class="w-4 h-4 shrink-0 text-success" />
                    <AlertTriangle v-else-if="syncStateStore.status === SyncStatus.COMPLETED_WITH_ERRORS"
                        class="w-4 h-4 shrink-0 text-warning" />
                    <AlertTriangle v-else-if="syncStateStore.status === SyncStatus.FAILED"
                        class="w-4 h-4 shrink-0 text-error" />

                    <span v-if="syncStateStore.status === SyncStatus.FAILED"
                        class="flex-1 min-w-0 text-sm text-error truncate">
                        {{ getSyncErrorMessage(t, syncStateStore.error) }}
                    </span>
                    <span v-else-if="syncStateStore.status === SyncStatus.COMPLETED_WITH_ERRORS"
                        class="text-sm text-warning truncate max-w-30 md:max-w-50">
                        {{ $t('modsTab.notifications.syncMods.completedWithErrors.title') }}
                    </span>
                    <span v-else-if="syncStateStore.status === SyncStatus.SYNCING"
                        class="text-sm truncate max-w-30 md:max-w-50">
                        {{ $t('titlebar.sync.applying', { modName: syncStateStore.lastSyncedMod?.modName }) }}
                    </span>
                    <span v-else class="text-sm truncate max-w-25 md:max-w-50">
                        <span v-if="syncStateStore.type === SyncType.Sync">
                            {{ $t('titlebar.sync.syncSuccess') }}
                        </span>
                        <span v-else>
                            {{ $t('titlebar.sync.unsyncSuccess') }}
                        </span>
                    </span>
                </div>

                <div v-if="syncStateStore.status == SyncStatus.SYNCING"
                    class="hidden sm:block w-16 md:w-24 h-2.5 bg-surface-input rounded-full overflow-hidden relative z-10 shrink-0">
                    <div class="h-full bg-accent rounded-full"
                        :class="syncProgress === 0 ? 'transition-none' : 'transition-all duration-150 ease-out'"
                        :style="{ width: `${syncProgress}%` }" />
                </div>

                <button
                    v-if="syncStateStore.status === SyncStatus.COMPLETED || syncStateStore.status === SyncStatus.COMPLETED_WITH_ERRORS || syncStateStore.status === SyncStatus.FAILED"
                    @click.stop="showSyncBar = false"
                    class="text-text-primary hover:text-accent relative z-20 transition-all flex items-center justify-center shrink-0">
                    <X class="w-[1.25em] h-[1.25em] cursor-pointer" />
                </button>
            </div>

            <div class="flex items-center shrink-0 gap-1">
                <ActiveDownloads />
                <button
                    class="flex items-center gap-1 md:gap-2 cursor-pointer hover:bg-accent-hover hover:text-text-on-accent rounded-sm px-2.5 py-1 transition-colors duration-200"
                    @click="handleLogsClick">
                    <ScrollText class="w-[1.25em] h-[1.25em]" />
                    <span class="hidden min-[1152px]:inline font-semibold text-sm">
                        {{ $t('titlebar.actions.logs') }}
                    </span>
                </button>
                <button v-if="isChineseLanguage"
                    class="flex items-center gap-1 md:gap-2 cursor-pointer hover:bg-accent-hover hover:text-text-on-accent rounded-sm px-2 py-1 transition-colors duration-200"
                    @click="handleAfdianClick">
                    <AfDianIcon class="w-[1.5em] h-[1.5em]" />
                    <span class="hidden min-[1152px]:inline font-semibold text-sm">
                        {{ $t('titlebar.actions.afdian') }}
                    </span>
                </button>
                <button v-else
                    class="flex items-center gap-1 md:gap-2 cursor-pointer hover:bg-accent-hover hover:text-text-on-accent rounded-sm px-2.5 py-1 transition-colors duration-200"
                    @click="handleKofiClick">
                    <KofiIcon class="w-[1.25em] h-[1.25em]" />
                    <span class="hidden min-[1152px]:inline font-semibold text-sm">
                        {{ $t('titlebar.actions.kofi') }}
                    </span>
                </button>
                <button
                    class="flex items-center gap-1 md:gap-2 cursor-pointer hover:bg-accent-hover hover:text-text-on-accent rounded-sm px-2.5 py-1 transition-colors duration-200"
                    @click="handleGithubClick">
                    <GithubIcon class="w-[1.25em] h-[1.25em]" />
                    <span class="hidden min-[1152px]:inline font-semibold text-sm">
                        {{ $t('titlebar.actions.github') }}
                    </span>
                </button>
            </div>

            <div class="flex shrink-0 ml-1 md:ml-1">
                <button @click="minimizeWindow" class="flex items-center justify-center px-3 md:px-4 hover:bg-state-hover transition-colors">
                    <Minus class="w-[1.25em] h-[1.25em] font-bold" />
                </button>
                <button @click="toggleMaximizeWindow" class="flex items-center justify-center px-3 md:px-4 hover:bg-state-hover transition-colors">
                    <SquareStop v-if="isMaximized" class="w-[1.25em] h-[1.25em]" />
                    <Square v-else class="w-[1.25em] h-[1.25em]" />
                </button>
                <button @click="closeWindow" class="flex items-center justify-center px-3 md:px-4 hover:bg-error transition-colors group">
                    <X class="w-[1.5em] h-[1.5em] group-hover:text-text-on-accent" />
                </button>
            </div>
        </div>
    </div>
</template>

<style scoped>
.slide-fade-enter-active {
    transition: all 0.2s ease-out;
}

.slide-fade-leave-active {
    transition: all 0.15s ease-in;
}

.slide-fade-enter-from,
.slide-fade-leave-to {
    opacity: 0;
    transform: translateY(-4px);
}
</style>
