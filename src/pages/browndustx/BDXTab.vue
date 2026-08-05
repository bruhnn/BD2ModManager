<script setup lang="ts">
import { RefreshCcw, AlertTriangle, TriangleAlert } from '@lucide/vue';
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useTemplateRef, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { invoke } from '@tauri-apps/api/core';
import { open } from '@tauri-apps/plugin-dialog';
import { listen } from '@tauri-apps/api/event';

import { useSettingsStore } from '../../stores/settings';
import { LogMessage, useBdxLogsStore } from '../../stores/BDXLogs';
import { useHeader } from '../../composables/useHeader';
import { useConfirm } from '../../plugins/ConfirmService';
import { useLoggingStore } from '../../stores/logging';
import GithubInstallModal from './modals/GithubInstallModal.vue';
import ComponentRow from './ComponentRow.vue';
import { PluginState, Status } from './types';

const { t } = useI18n()
const confirm = useConfirm()
const settingsStore = useSettingsStore()
const { logs } = useBdxLogsStore()
const loggingStore = useLoggingStore()

const defaultState = (): PluginState => ({ status: Status.NotInstalled, version: null })

const bepInExState = ref<PluginState>(defaultState())
const brownDustXState = ref<PluginState>(defaultState())
const configurationManagerState = ref<PluginState>(defaultState())

const isBepInExDialogOpen = ref(false)
const isConfigManagerDialogOpen = ref(false)

const gameDirectorySet = computed(() => !!settingsStore.settings.gameDirectory)
const bepInExInstalled = computed(() => bepInExState.value.status === Status.Installed)

function pushLog(level: LogMessage['level'], scope: LogMessage['scope'], message: string) {
    logs.push({ level, scope, message, timestamp: new Date().toISOString() })
}

function mapInstallError(error: unknown): string {
    if (typeof error === 'string') {
        if (error === 'GamePathNotSet') return t('browndustxTab.errors.gamePathNotSet')
        if (error === 'BepInExNotInstalled') return t('browndustxTab.errors.bepinexNotInstalled')
        if (error === 'BepInExAlreadyInstalled' || error === 'PluginAlreadyInstalled') return t('browndustxTab.errors.alreadyInstalled')
    }

    if (typeof error === 'object' && error !== null) {
        const obj = error as Record<string, string>
        const msg = Object.values(obj)[0]
        if ('InvalidBepInExArchive' in obj || 'InvalidPluginArchive' in obj) return t('browndustxTab.errors.invalidArchive')
        if ('ArchiveNotFound' in obj) return t('browndustxTab.errors.archiveNotFound', { error: msg })
        if ('ExtractionFailed' in obj) return t('browndustxTab.errors.extractionFailed', { error: msg })
        if ('DownloadFailed' in obj) return t('browndustxTab.errors.downloadFailed', { error: msg })
        if ('Unknown' in obj) return t('browndustxTab.errors.unknown', { error: msg })
    }

    return t('browndustxTab.errors.unknown', { error: String(error) })
}

async function getComponentState(
    command: string,
    scope: LogMessage['scope'],
    installedStatuses: Status[],
    log: boolean
): Promise<PluginState> {
    try {
        const result = await invoke<PluginState>(command)
        if (log) {
            const installed = installedStatuses.includes(result.status)
            pushLog('info', scope,
                installed
                    ? t('browndustxTab.logs.versionInstalled', { scope, version: result.version })
                    : t('browndustxTab.logs.notInstalled', { scope })
            )
        }
        return result
    } catch (error) {
        loggingStore.logError(`Error fetching ${scope} status:`, error)
        pushLog('error', scope, t('browndustxTab.logs.fetchError', { scope, error }))
        return defaultState()
    }
}

async function initialize(log = true) {
    const [bdx, bepinex, configManager] = await Promise.all([
        getComponentState('get_browndustx_version', 'BrownDustX', [Status.Installed, Status.InstalledButOutdated], log),
        getComponentState('get_bepinex_version', 'BepInEx', [Status.Installed], log),
        getComponentState('get_configmanager_version', 'Configuration Manager', [Status.Installed], log),
    ])
    brownDustXState.value = bdx
    bepInExState.value = bepinex
    configurationManagerState.value = configManager
}

async function installFromArchive(command: string, scope: LogMessage['scope'], path: string) {
    try {
        pushLog('info', scope, t('browndustxTab.logs.installingFromArchive', { scope, path }))
        await invoke(command, { path })
        pushLog('success', scope, t('browndustxTab.logs.installedSuccess', { scope }))
        await initialize()
    } catch (error) {
        pushLog('error', scope, t('browndustxTab.logs.installError', { scope, error: mapInstallError(error) }))
    }
}

async function installFromUrl(command: string, scope: LogMessage['scope'], url: string) {
    try {
        pushLog('info', scope, t('browndustxTab.logs.installingFromUrl', { scope, url }))
        await invoke(command, {url})
        pushLog('success', scope, t('browndustxTab.logs.installedSuccess', { scope }))
        await initialize()
    } catch (error) {
        pushLog('error', scope, t('browndustxTab.logs.installError', { scope, error: mapInstallError(error) }))
    }
}

async function promptForArchive(title: string, command: string, scope: LogMessage['scope']) {
    const selected = await open({
        title,
        multiple: false,
        filters: [{ name: t('browndustxTab.fileDialog.archiveFilter'), extensions: ['zip', 'rar', '7z'] }]
    })
    if (selected && typeof selected === 'string') {
        await installFromArchive(command, scope, selected)
    }
}

async function uninstallComponent(command: string, confirmKey: string, scope: LogMessage['scope']) {
    const result = await confirm.confirm({
        title: t(`browndustxTab.confirmations.${confirmKey}.title`),
        message: t(`browndustxTab.confirmations.${confirmKey}.message`),
        acceptButton: { label: t(`browndustxTab.confirmations.${confirmKey}.actions.confirm`) },
        rejectButton: { label: t('common.actions.cancel') },
    })
    if (result.confirmed) {
        try {
            pushLog('info', scope, t('browndustxTab.logs.uninstalling', { scope }))
            await invoke(command)
            pushLog('success', scope, t('browndustxTab.logs.uninstalledSuccess', { scope }))
            await initialize()
        } catch (error) {
            pushLog('error', scope, t('browndustxTab.logs.uninstallError', { scope, error: mapInstallError(error) }))
        }
    }
}

const unlistenDragDrop = ref<(() => void) | null>(null)

async function setupDragAndDrop() {
    unlistenDragDrop.value = await listen<{ paths: string[] }>("tauri://drag-drop", async (event) => {
        for (const path of event.payload?.paths as string[]) {
            const lower = path.toLowerCase()
            if (!lower.endsWith('.zip') && !lower.endsWith('.rar') && !lower.endsWith('.7z')) {
                pushLog('warn', 'All', t('browndustxTab.logs.unsupportedFile', { path }))
                continue
            }

            let archiveType: 'BEPINEX' | 'BROWNDUSTX' | 'CONFIGMANAGER' | null = null

            if (lower.includes('browndustx') || lower.includes('bdx')) archiveType = 'BROWNDUSTX'
            else if (lower.includes('configurationmanager') || lower.includes('configmanager')) archiveType = 'CONFIGMANAGER'
            else if (lower.includes('bepinex')) archiveType = 'BEPINEX'
            else archiveType = await invoke<typeof archiveType>('determine_archive_type', { path })

            if (archiveType === 'BEPINEX') await installFromArchive('install_bepinex', 'BepInEx', path)
            else if (archiveType === 'BROWNDUSTX') await installFromArchive('install_browndustx', 'BrownDustX', path)
            else if (archiveType === 'CONFIGMANAGER') await installFromArchive('install_configmanager', 'Configuration Manager', path)
            else pushLog('warn', 'All', t('browndustxTab.logs.unknownArchiveType', { path }))
        }
    })
}

onMounted(async () => {
    if (settingsStore.settings.gameDirectory) await initialize(false)
    if (!unlistenDragDrop.value) await setupDragAndDrop()
})

onBeforeUnmount(() => {
    unlistenDragDrop.value?.()
    unlistenDragDrop.value = null
})

watch(() => settingsStore.settings.gameDirectory, async (newPath) => {
    if (newPath) {
        pushLog('info', 'All', t('browndustxTab.logs.gameDirectorySet', { path: newPath }))
        await initialize()
    } else {
        pushLog('warn', 'All', t('browndustxTab.logs.gameDirectoryUnset'))
        bepInExState.value = defaultState()
        brownDustXState.value = defaultState()
        configurationManagerState.value = defaultState()
    }
})

useHeader({
    title: computed(() => t('browndustxTab.title')),
    buttons: [{
        label: computed(() => t('common.actions.refresh')),
        icon: RefreshCcw,
        class: "flex justify-center items-center gap-1 mt-1 px-4 py-1 rounded-sm transition-colors duration-200 border border-border-default cursor-pointer",
        action: () => initialize(true)
    }]
})

const logsContainer = useTemplateRef<HTMLElement | null>('logsContainer')
watch(logs, async () => {
    await nextTick()
    if (logsContainer.value) logsContainer.value.scrollTop = logsContainer.value.scrollHeight
}, { deep: true, flush: 'post' })

const BEPINEX_RELEASES_URL = 'https://api.github.com/repos/BepInEx/BepInEx/releases'
const BEPINEX_RECOMMENDED_VERSION = 'v5.4.22'
const BEPINEX_ASSETS_FILTER_REGEX = /win[_-]x64|BepInEx_x64_|(?:Mono|IL2CPP)_x64_/i

const CONFIGMANAGER_RELEASES_URL = 'https://api.github.com/repos/bepinex/BepInEx.ConfigurationManager/releases'
const CONFIGMANAGER_RECOMMENDED_VERSION = 'v18.2'
const CONFIGMANAGER_ASSETS_FILTER_REGEX = /BepInEx/i
</script>

<template>
    <div class="h-full min-h-0 flex flex-col overflow-x-auto">
        <GithubInstallModal v-model:show="isBepInExDialogOpen"
            :title="$t('browndustxTab.modals.installFromGithub.bepinexTitle')" @close="isBepInExDialogOpen = false"
            @on-version-select="(downloadUrl) => installFromUrl('install_bepinex', 'BepInEx', downloadUrl)" :releases-url="BEPINEX_RELEASES_URL"
            :recommended-version="BEPINEX_RECOMMENDED_VERSION" :assets-filter-regex="BEPINEX_ASSETS_FILTER_REGEX" />

        <GithubInstallModal v-model:show="isConfigManagerDialogOpen"
            :title="$t('browndustxTab.modals.installFromGithub.configManagerTitle')"
            @close="isConfigManagerDialogOpen = false" @on-version-select="(downloadUrl) => installFromUrl('install_configmanager', 'Configuration Manager', downloadUrl)"
            :releases-url="CONFIGMANAGER_RELEASES_URL" :recommended-version="CONFIGMANAGER_RECOMMENDED_VERSION"
            :assets-filter-regex="CONFIGMANAGER_ASSETS_FILTER_REGEX" />

        <div class="flex flex-col flex-1 p-4 min-h-0 gap-2">

            <div class="flex gap-2.5 p-3 rounded bg-error-bg text-sm">
                <TriangleAlert class="w-4 h-4 shrink-0 mt-0.5 text-error" />
                <div class="flex flex-col gap-0.5">
                    <p class="font-medium text-error">{{ $t('browndustxTab.alerts.danger') }}</p>
                    <p class="text-text-secondary">{{ $t('browndustxTab.alerts.dangerMessage') }}</p>
                </div>
            </div>

            <div>
                <h3 class="text-text-secondary uppercase text-xs font-semibold tracking-wider mb-1">
                    {{ $t('browndustxTab.labels.frameworkAndPlugins') }}
                </h3>

                <section class="mb-2">
                    <p v-if="!gameDirectorySet" class="text-error text-sm">
                        {{ $t("browndustxTab.messages.gameDirectoryNotSet") }}
                    </p>
                    <p v-else class="text-text-secondary font-mono text-xs flex items-center gap-1.5">
                        <span>{{ $t("browndustxTab.labels.gameDirectory") }}</span>
                        <span class="text-text-primary font-mono">{{ settingsStore.settings.gameDirectory }}</span>
                    </p>
                </section>

                <div class="flex flex-col">
                    <ComponentRow label="BepInEx" :description="$t('browndustxTab.descriptions.bepinex')"
                        :state="bepInExState" :disabled="!gameDirectorySet" :show-github="true" 
                        @install-from-github="isBepInExDialogOpen = true"
                        @install="promptForArchive($t('browndustxTab.fileDialog.bepinexTitle'), 'install_bepinex', 'BepInEx')"
                        @remove="uninstallComponent('uninstall_bepinex', 'removeBepInEx', 'BepInEx')" />
                    <ComponentRow label="BrownDustX" :description="$t('browndustxTab.descriptions.browndustx')"
                        :state="brownDustXState" :disabled="!gameDirectorySet" :requires-bep-in-ex="true"
                        :bep-in-ex-installed="bepInExInstalled"
                        @install="promptForArchive($t('browndustxTab.fileDialog.browndustxTitle'), 'install_browndustx', 'BrownDustX')"
                        @remove="uninstallComponent('uninstall_browndustx', 'removeBrownDustX', 'BrownDustX')" />
                    <ComponentRow label="Configuration Manager"
                        :description="$t('browndustxTab.descriptions.configurationManager')"
                        :state="configurationManagerState" :disabled="!gameDirectorySet" :show-github="true"
                        :requires-bep-in-ex="true" :bep-in-ex-installed="bepInExInstalled"
                        @install-from-github="isConfigManagerDialogOpen = true"
                        @install="promptForArchive($t('browndustxTab.fileDialog.configManagerTitle'), 'install_configmanager', 'Configuration Manager')"
                        @remove="uninstallComponent('uninstall_configmanager', 'removeConfigManager', 'Configuration Manager')" />
                </div>
            </div>

            <div class="flex flex-col gap-1">
                <p v-if="bepInExState.status === Status.Installed && brownDustXState.status === Status.NotInstalled"
                    class="text-warning flex gap-1.5 items-center text-xs">
                    <AlertTriangle class="inline w-4 h-4 shrink-0" />
                    {{ $t("browndustxTab.messages.brownDustXMissing") }}
                </p>
                <p v-if="configurationManagerState.status === Status.NotInstalled && brownDustXState.status === Status.Installed"
                    class="text-warning flex gap-1.5 items-center text-xs">
                    <AlertTriangle class="inline w-4 h-4 shrink-0" />
                    {{ $t("browndustxTab.messages.configurationManagerMissing") }}
                </p>
                <p v-if="brownDustXState.status === Status.BepInExMissing"
                    class="text-warning flex gap-1.5 items-center text-xs">
                    <AlertTriangle class="inline w-4 h-4 shrink-0" />
                    {{ $t("browndustxTab.messages.bepinexMissing") }}
                </p>
            </div>

            <div v-if="gameDirectorySet"
                class="p-4 rounded border-2 border-dashed border-border-default text-center text-sm text-text-secondary">
                {{ $t("browndustxTab.messages.dragAndDrop") }}
            </div>

            <div class="flex-1 flex flex-col min-h-0">
                <h3 class="text-text-secondary uppercase text-xs tracking-wider mb-2">
                    {{ $t('browndustxTab.labels.logs') }}
                </h3>
                <div ref="logsContainer"
                    class="flex-1 flex flex-col text-text-secondary overflow-y-auto bg-bg-surface p-2 border border-border-default rounded min-h-0"
                    :class="{ 'items-center justify-center': logs.length === 0 }">
                    <template v-if="logs.length === 0">
                        <div class="text-xs font-mono text-text-secondary italic text-center py-2">
                            {{ $t('browndustxTab.messages.noLogsYet') }}
                        </div>
                    </template>
                    <template v-else>
                        <div v-for="(log, index) in logs" :key="index" class="text-xs font-mono flex gap-1.5">
                            <span class="text-text-secondary/60 shrink-0">{{ new Date(log.timestamp).toLocaleTimeString()
                            }}</span>
                            <span class="shrink-0" :class="{
                                'text-success': log.level === 'success',
                                'text-info': log.level === 'info',
                                'text-warning': log.level === 'warn',
                                'text-error': log.level === 'error',
                            }">{{ log.level.toUpperCase() }}</span>
                            <span class="text-text-secondary/80 shrink-0">[{{ log.scope }}]</span>
                            <span>{{ log.message }}</span>
                        </div>
                    </template>
                </div>
            </div>

        </div>
    </div>
</template>