<script setup lang="ts">
import {
    Bug,
    Info,
    TriangleAlert,
    OctagonX,
    Trash2,
    ChevronsDown,
    ChevronsUp,
    Copy,
    FolderOpen,
    Monitor,
    Server,
} from '@lucide/vue'

import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useVirtualizer } from '@tanstack/vue-virtual'

import { invoke } from '@tauri-apps/api/core'
import { openPath } from '@tauri-apps/plugin-opener'

import { useDev } from '../../composables/useDev.ts'
import { LogLevel, LogSource, useLoggingStore } from '../../stores/logging'
import { useNotificationStore } from '../../stores/notification.ts'
import { globalModals } from '../../composables/useGlobalModals.ts'

import Button from '../common/Button.vue'
import Modal from '../common/Modal.vue'

const { t } = useI18n()
const notificationStore = useNotificationStore()

const {
    isDev
} = useDev()

const {
    isOpen,
    closeModal
} = globalModals.logs

const loggingStore = useLoggingStore()

const selectedLevels = ref<LogLevel[]>([])
const selectedSources = ref<LogSource[]>([])

const filteredLogs = computed(() => {
    let logs = loggingStore.logs

    if (selectedLevels.value.length > 0) {
        logs = logs.filter(log => selectedLevels.value.includes(log.level))
    }

    if (selectedSources.value.length > 0) {
        logs = logs.filter(log => selectedSources.value.includes(log.source))
    }

    return logs
})

function toggleLevel(level: LogLevel) {
    if (selectedLevels.value.includes(level)) {
        return selectedLevels.value.splice(selectedLevels.value.indexOf(level), 1)
    }

    selectedLevels.value.push(level)
}

function toggleSource(source: LogSource) {
    if (selectedSources.value.includes(source)) {
        return selectedSources.value.splice(selectedSources.value.indexOf(source), 1)
    }

    selectedSources.value.push(source)
}

const scrollContainer = ref<HTMLElement | null>(null)

const virtualizer = useVirtualizer(computed(() => ({
    count: filteredLogs.value.length,
    getScrollElement: () => scrollContainer.value,
    estimateSize: () => 64,
    overscan: 20,
})))

const virtualRows = computed(() => virtualizer.value.getVirtualItems())

function scrollToFirst() {
    if (filteredLogs.value.length > 0) virtualizer.value.scrollToIndex(0)
}

function scrollToLast() {
    if (filteredLogs.value.length > 0) virtualizer.value.scrollToIndex(filteredLogs.value.length - 1)
}

function clearLogs() {
    loggingStore.clearLogs()

    notificationStore.add({
        type: "info",
        title: t('app.notifications.logs.cleared.title')
    })
}

function copyAll() {
    const text = filteredLogs.value
        .map(log => `[${log.level}] [${log.source}] ${log.timestamp.toLocaleString()} - ${log.message}`)
        .join('\n')
    navigator.clipboard.writeText(text)

    notificationStore.add({
        type: "info",
        title: t('app.notifications.logs.copied.title')
    })
}

async function openLogsFolder() {
    const logsDirectory = await invoke<string>('get_logs_directory')
    await openPath(logsDirectory)
}
</script>
<template>
    <Modal :show="isOpen" size="lg-lg" @close="closeModal" :title="t('app.modals.logs.title')">
        <div class="flex flex-col h-full min-h-0 p-2 px-4 gap-2">
            <!-- header -->
            <div class="flex flex-row justify-between items-center">
                <div class="flex flex-row gap-2 items-center">
                    <!-- level  -->
                    <div class="flex gap-1 p-1 bg-surface-input rounded-lg">
                        <Button :label="t('app.modals.logs.levels.debug')" :icon="Bug" size="sm" variant="text" :class="[
                            'rounded-md!',
                            selectedLevels.includes(LogLevel.Debug)
                                ? 'bg-debug-bg! text-debug!'
                                : 'hover:bg-debug-bg! hover:text-debug!'
                        ]" :aria-pressed="selectedLevels.includes(LogLevel.Debug)"
                            @click="toggleLevel(LogLevel.Debug)" />
                        <Button :label="t('app.modals.logs.levels.info')" :icon="Info" size="sm" variant="text" :class="[
                            'rounded-md!',
                            selectedLevels.includes(LogLevel.Info)
                                ? 'bg-info-bg! text-info!'
                                : 'hover:bg-info-bg! hover:text-info!'
                        ]" :aria-pressed="selectedLevels.includes(LogLevel.Info)"
                            @click="toggleLevel(LogLevel.Info)" />
                        <Button :label="t('app.modals.logs.levels.warning')" :icon="TriangleAlert" size="sm" variant="text" :class="[
                            'rounded-md!',
                            selectedLevels.includes(LogLevel.Warning)
                                ? 'bg-warning-bg! text-warning!'
                                : 'hover:bg-warning-bg! hover:text-warning!'
                        ]" :aria-pressed="selectedLevels.includes(LogLevel.Warning)"
                            @click="toggleLevel(LogLevel.Warning)" />
                        <Button :label="t('app.modals.logs.levels.error')" :icon="OctagonX" size="sm" variant="text" :class="[
                            'rounded-md!',
                            selectedLevels.includes(LogLevel.Error)
                                ? 'bg-error-bg! text-error!'
                                : 'hover:bg-error-bg! hover:text-error!'
                        ]" :aria-pressed="selectedLevels.includes(LogLevel.Error)"
                            @click="toggleLevel(LogLevel.Error)" />
                    </div>

                    <!-- actions -->
                    <div class="flex gap-1">
                        <Button :icon="Trash2" size="sm" variant="text" class="w-7 justify-center! rounded-md! px-0!"
                            :title="t('app.modals.logs.actions.clear')" :aria-label="t('app.modals.logs.actions.clear')"
                            :disabled="loggingStore.logs.length === 0" @click="clearLogs" />
                        <Button :icon="ChevronsUp" size="sm" variant="text"
                            class="w-7 justify-center! rounded-md! px-0!"
                            :title="t('app.modals.logs.actions.goToFirst')"
                            :aria-label="t('app.modals.logs.actions.goToFirst')" :disabled="filteredLogs.length === 0"
                            @click="scrollToFirst" />
                        <Button :icon="ChevronsDown" size="sm" variant="text"
                            class="w-7 justify-center! rounded-md! px-0!" :title="t('app.modals.logs.actions.goToLast')"
                            :aria-label="t('app.modals.logs.actions.goToLast')" :disabled="filteredLogs.length === 0"
                            @click="scrollToLast" />
                        <Button :icon="Copy" size="sm" variant="text" class="w-7 justify-center! rounded-md! px-0!"
                            :title="t('app.modals.logs.actions.copyAll')"
                            :aria-label="t('app.modals.logs.actions.copyAll')" :disabled="filteredLogs.length === 0"
                            @click="copyAll" />
                        <Button :icon="FolderOpen" size="sm" variant="text"
                            class="w-7 justify-center! rounded-md! px-0!"
                            :title="t('app.modals.logs.actions.openFolder')"
                            :aria-label="t('app.modals.logs.actions.openFolder')" @click="openLogsFolder" />
                    </div>
                </div>

                <!-- source
     -->
                <div class="flex gap-1 p-1 bg-surface-input rounded-lg">
                    <Button :label="t('app.modals.logs.sources.frontend')" :icon="Monitor" size="sm" variant="text" :class="[
                        'rounded-md!',
                        selectedSources.includes(LogSource.Frontend) ? 'bg-accent! text-text-on-accent!' : ''
                    ]" :aria-pressed="selectedSources.includes(LogSource.Frontend)"
                        @click="toggleSource(LogSource.Frontend)" />
                    <Button :label="t('app.modals.logs.sources.backend')" :icon="Server" size="sm" variant="text" :class="[
                        'rounded-md!',
                        selectedSources.includes(LogSource.Backend) ? 'bg-accent! text-text-on-accent!' : ''
                    ]" :aria-pressed="selectedSources.includes(LogSource.Backend)"
                        @click="toggleSource(LogSource.Backend)" />
                </div>
            </div>

            <!-- // logs -->
            <div class="flex-1 min-h-0 bg-surface-card rounded border border-border-default overflow-hidden">
                <p v-if="filteredLogs.length == 0"
                    class="text-sm text-text-secondary whitespace-pre-wrap flex-1 h-full flex p-2">{{
                        t('app.modals.logs.noLogs') }}
                </p>
                <div v-else ref="scrollContainer" class="h-full overflow-y-auto">
                    <div :style="{ height: `${virtualizer.getTotalSize()}px`, position: 'relative', width: '100%' }">
                        <div v-for="row in virtualRows" :key="String(row.key)" :data-index="row.index"
                            :ref="(el) => virtualizer.measureElement(el as HTMLElement)" :style="{
                                position: 'absolute',
                                top: 0,
                                left: 0,
                                width: '100%',
                                transform: `translateY(${row.start}px)`,
                            }" class="flex flex-col gap-1 px-2 py-2 border-b border-border-subtle">
                            <div class="flex gap-2">
                                <span :class="{
                                    'text-info': filteredLogs[row.index].level === 'Info',
                                    'text-warning': filteredLogs[row.index].level === 'Warning',
                                    'text-error': filteredLogs[row.index].level === 'Error',
                                    'text-debug': filteredLogs[row.index].level === 'Debug',
                                }" class="text-sm font-semibold uppercase">
                                    {{ t(`app.modals.logs.levels.${filteredLogs[row.index].level.toLowerCase()}`) }}
                                </span>
                                <span class="text-text-secondary text-sm font-medium">
                                    {{ t(`app.modals.logs.sources.${filteredLogs[row.index].source.toLowerCase()}`) }}
                                </span>
                                <span class="text-text-muted text-sm">
                                    {{ filteredLogs[row.index].timestamp.toLocaleString() }}
                                </span>
                                <span v-if="isDev && filteredLogs[row.index].caller"
                                    class="truncate text-text-secondary text-sm">
                                    {{ filteredLogs[row.index].caller }}
                                </span>
                            </div>
                            <span class="flex-1 text-text-primary break-all" :class="{
                                'text-error': filteredLogs[row.index].level === 'Error'
                            }">
                                {{ filteredLogs[row.index].message }}
                            </span>
                        </div>
                    </div>
                </div>
            </div>

        </div>
        <template #footer>
            <div class="flex justify-end gap-2 p-2">
                <Button @click="closeModal">{{ t('common.actions.close') }}</Button>
            </div>
        </template>
    </Modal>
</template>

<style scoped></style>
