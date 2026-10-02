<script setup lang="ts">
import { Minus, Square, SquareStop, X, Check, AlertTriangle, RotateCw, ScrollText, Heart, Sparkles } from '@lucide/vue';
import GithubIcon from './icons/GithubIcon.vue';
import KofiIcon from './icons/KofiIcon.vue';
import AfDianIcon from './icons/AfDianIcon.vue';
import ActiveDownloads from './ActiveDownloads.vue';

import { computed, ref, watch, onUnmounted, onMounted } from 'vue';
import { refThrottled } from '@vueuse/core';
import { useI18n } from 'vue-i18n';

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

import Tooltip from './common/Tooltip.vue';

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

let creditsInterval: ReturnType<typeof setInterval>
const credits = ref<any[]>([])
const creditIndex = ref(0)
const creditPosition = ref(1)
const creditsSinceZero = ref(0)

const allCredits = computed(() => [
    { type: "creator", name: "@bruhnn", platform: "github" },
    ...credits.value
])

function shuffle<T>(items: T[]) {
    const shuffled = [...items]

    for (let i = shuffled.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1))

            ;[shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]]
    }

    return shuffled
}

async function fetchCredits() {
    try {
        const response = await fetch(
            "https://shy-waterfall-2797.bruhnn.workers.dev/credits"
        )

        if (!response.ok) {
            throw new Error(`Failed to fetch credits: ${response.status}`)
        }

        const data = await response.json()

        const supporters = shuffle(
            data.sponsors.filter((item: any) => item.type === 'supporter')
        )

        const contributors = shuffle(
            data.sponsors.filter((item: any) => item.type === 'contributor')
        )

        const mixed: any[] = []

        while (supporters.length || contributors.length) {
            mixed.push(...supporters.splice(0, 2))

            if (contributors.length) {
                mixed.push(contributors.shift())
            }
        }

        credits.value = mixed

    } catch (error) {
        loggingStore.logError("Failed to fetch credits", error)
    }
}

function rotateCredits() {
    const delay = creditIndex.value === 0 ? 30000 : 5000

    creditsInterval = setTimeout(() => {
        if (creditsSinceZero.value === 3) {
            creditIndex.value = 0
            creditsSinceZero.value = 0
        } else {
            creditIndex.value = creditPosition.value
            creditPosition.value++
            creditsSinceZero.value++

            if (creditPosition.value >= allCredits.value.length) {
                creditPosition.value = 1
                creditsSinceZero.value = 3
            }
        }

        rotateCredits()
    }, delay)
}

onMounted(async () => {
    await fetchCredits()
    if (credits.value.length > 0) rotateCredits()
})

onUnmounted(() => {
    clearTimeout(creditsInterval)
})
</script>

<template>
    <div class="grid min-h-10 h-10 shrink-0 sticky grid-cols-[minmax(0,1fr)_auto] select-none overflow-hidden transition-[max-height] duration-300 ease-out bg-surface-app border-b border-border-subtle"
        data-tauri-drag-region>
        <div class="flex min-w-0 items-center gap-2.5 overflow-hidden px-2 py-1" data-tauri-drag-region>
            <span class="font-bold text-lg select-none whitespace-nowrap" data-tauri-drag-region>
                Mod Manager
            </span>
            <span class="text-xs font-semibold flex min-w-0 gap-1 items-center whitespace-nowrap">
                <Heart class="w-3.5 h-3.5 shrink-0 mr-1 text-accent" />
                <span class="shrink-0">v{{ appVersion }}</span>
                <transition name="credits" mode="out-in">
                    <span :key="creditIndex" class="inline-flex items-center min-w-0">
                        <Tooltip class="min-w-0" placement="bottom"
                            :text="allCredits[creditIndex]?.type === 'creator' ? $t('titlebar.credits.creator_tooltip') : allCredits[creditIndex]?.type === 'supporter' ? $t('titlebar.credits.supporter_tooltip', { platform: ({
                                afdian: 'AfDian',
                                kofi: 'Ko-Fi',
                                github: 'GitHub',
                            } as Record<string, string>)[allCredits[creditIndex]?.platform]}) : $t('titlebar.credits.bug_reports_tooltip')"
                            :background-color="allCredits[creditIndex]?.platform === 'afdian' ? '#946CE6' : '#24292f'"
                            text-color="#ffffff">
                            <template #icon>
                                <AfDianIcon v-if="allCredits[creditIndex]?.platform === 'afdian'"
                                    class="w-5 h-5 shrink-0" color="currentColor" />
                                <GithubIcon v-else class="w-4 h-4 shrink-0" />
                            </template>
                            <span tabindex="0" class="truncate max-w-64
                                bg-linear-to-r
                                bg-size-[200%_100%]
                                bg-clip-text text-transparent
                                animate-sweep
                                transition-colors" :class="[
                                    allCredits[creditIndex]?.platform === 'afdian'
                                        ? 'from-[#946CE6] via-[#B79AF5] to-[#946CE6] hover:via-[#C8B2F8]'
                                        : 'from-accent via-accent/60 to-accent hover:via-accent/80',

                                    { 'cursor-pointer': allCredits[creditIndex]?.type === 'creator' }
                                ]" @click="allCredits[creditIndex]?.type === 'creator' && handleOpenGithubUser()">
                                <span class="shrink-0 text-text-primary">
                                    {{ allCredits[creditIndex]?.type === 'creator' ? $t('titlebar.credits.creator') : $t('titlebar.credits.thanks') }}
                                </span>
                                {{ ' ' }}
                                <span class="shrink-0"> {{ allCredits[creditIndex]?.name }}</span>
                            </span>
                        </Tooltip>
                    </span>
                </transition>
            </span>
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
                <transition name="slide-fade">
                <button
                    v-if="appUpdate?.status && appUpdate.status !== UpdateStatus.Downloading && appUpdate.status !== UpdateStatus.Failed"
                    class="flex items-center gap-1 md:gap-2 cursor-pointer hover:bg-accent-hover hover:text-text-on-accent rounded-sm px-2.5 py-1 transition-colors duration-200"
                    :aria-disabled="isUpdating"
                    :style="{ pointerEvents: isUpdating ? 'none' : undefined }"
                    :class="{
                        'text-accent':
                            appUpdate?.status === UpdateStatus.UpdateAvailable ||
                            appUpdate?.status === UpdateStatus.Downloaded
                    }"
                    @click="handleAppUpdateClick">
                        <RotateCw v-if="
                            appUpdate?.status === UpdateStatus.CheckingForUpdates ||
                            appUpdate?.status === UpdateStatus.Installing" class="w-[1.25em] h-[1.25em] shrink-0 animate-spin" />

                        <Sparkles v-else class="w-[1.25em] h-[1.25em] shrink-0" />

                        <span class="hidden min-[1152px]:inline font-semibold text-sm">
                            <template v-if="appUpdate?.status === UpdateStatus.CheckingForUpdates">
                                {{ $t('titlebar.appUpdate.checking') }}
                            </template>

                            <template v-else-if="appUpdate?.status === UpdateStatus.UpdateAvailable">
                                {{ $t('titlebar.appUpdate.available', { version: appUpdate?.update?.versionAvailable }) }}
                            </template>

                            <template v-else-if="appUpdate?.status === UpdateStatus.Downloaded">
                                {{ $t('titlebar.appUpdate.downloaded', { version: appUpdate?.update?.versionAvailable }) }}
                            </template>

                            <template v-else-if="appUpdate?.status === UpdateStatus.Installing">
                                {{ $t('titlebar.appUpdate.updating', { version: appUpdate?.update?.versionAvailable }) }}
                            </template>
                        </span>
                    </button>
                </transition>

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
.credits-enter-active,
.credits-leave-active {
    transition: opacity 0.2s ease-out, transform 0.2s ease-out;
}

.credits-enter-from {
    opacity: 0;
    transform: translateY(4px);
}

.credits-leave-to {
    opacity: 0;
    transform: translateY(-4px);
}

@media (prefers-reduced-motion: reduce) {
    .credits-enter-active,
    .credits-leave-active {
        transition: none;
    }
}

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
