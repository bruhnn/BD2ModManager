<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { open } from '@tauri-apps/plugin-dialog'
import { ArrowRight } from '@lucide/vue'
import { globalModals } from '../../composables/useGlobalModals'
import { useModsStore } from '../../stores/mods'
import { useLoggingStore } from '../../stores/logging'
import { useNotificationStore } from '../../stores/notification'
import { getErrorMessage } from '../../utils/errors'
import Button from '../common/Button.vue'
import Checkbox from '../common/Checkbox.vue'
import Modal from '../common/Modal.vue'

const { t } = useI18n()
const modsStore = useModsStore()
const loggingStore = useLoggingStore()
const notificationStore = useNotificationStore()

const { isOpen, params, closeModal } = globalModals.convertedMods

const mods = computed(() => params.value?.mods ?? [])
const createBackup = ref(true)
const backupDirectory = ref('')
const copying = ref(false)
const error = ref<string | null>(null)

watch(isOpen, (open) => {
    if (!open) return
    createBackup.value = true
    backupDirectory.value = params.value?.defaultBackupDirectory ?? ''
    error.value = null
})

function finish(proceed: boolean) {
    const resolve = params.value?.onResolve
    closeModal()
    resolve?.(proceed)
}

function cancel() {
    if (copying.value) return
    loggingStore.logDebug('User cancelled copying converted mods.')
    finish(false)
}

async function changeBackupDirectory() {
    const folder = await open({ multiple: false, directory: true, defaultPath: backupDirectory.value || undefined })
    if (typeof folder === 'string') backupDirectory.value = folder
}

async function copyMods() {
    if (copying.value) return
    copying.value = true
    error.value = null

    try {
        const result = await modsStore.copyConvertedMods(
            mods.value.map((mod) => mod.modName),
            createBackup.value ? backupDirectory.value : null,
        )

        if (result.failed.length) {
            for (const failure of result.failed) {
                loggingStore.logError(`Failed to copy converted mod ${failure.modName}: ${failure.error}`)
            }
            notificationStore.add({
                type: 'error',
                closable: true,
                title: t('modsTab.modals.convertedMods.notifications.failed.title'),
                message: t('modsTab.modals.convertedMods.notifications.failed.message', {
                    count: result.failed.length,
                    mods: result.failed.map((failure) => failure.modName).join(', '),
                }, result.failed.length),
            })
            // don't sync, it would overwrite the mods that weren't copied
            finish(false)
            return
        }

        if (result.copied.length) {
            notificationStore.add({
                type: 'success',
                closable: true,
                title: t('modsTab.modals.convertedMods.notifications.copied.title'),
                message: result.backupPath
                    ? t('modsTab.modals.convertedMods.notifications.copied.messageWithBackup', { count: result.copied.length, path: result.backupPath }, result.copied.length)
                    : t('modsTab.modals.convertedMods.notifications.copied.message', { count: result.copied.length }, result.copied.length),
            })
        }
        finish(true)
    } catch (err) {
        loggingStore.logError('Failed to copy converted mods:', JSON.stringify(err))
        // keep the modal open so another backup folder can be chosen
        error.value = getErrorMessage(t, err)
    } finally {
        copying.value = false
    }
}
</script>

<template>
    <Modal :show="isOpen" size="lg" :title="t('modsTab.modals.convertedMods.title')"
        :subtitle="t('modsTab.modals.convertedMods.subtitle')" :close-on-escape="!copying" @close="cancel">
        <div class="flex flex-col gap-4 bg-surface-dialog p-4">
            <div class="rounded-lg bg-surface-card overflow-hidden">
                <div class="grid grid-cols-[1fr_auto_1fr] gap-x-3 px-3 py-2 text-xs font-semibold text-text-secondary">
                    <span>{{ t('modsTab.modals.convertedMods.gameFolder') }}</span>
                    <span class="w-4"></span>
                    <span>{{ t('modsTab.modals.convertedMods.modsFolder') }}</span>
                </div>
                <div class="max-h-72 overflow-y-auto">
                    <div v-for="mod in mods" :key="mod.modName"
                        class="grid grid-cols-[1fr_auto_1fr] items-center gap-x-3 px-3 py-1.5 text-sm border-t border-border-default">
                        <span class="flex min-w-0 items-baseline justify-between gap-2">
                            <span class="truncate text-text-primary" :title="`BD2MM/${mod.gameFolder}`">BD2MM/{{ mod.gameFolder }}</span>
                            <span class="shrink-0 text-xs text-text-secondary">Spine {{ mod.gameVersion }}</span>
                        </span>
                        <ArrowRight class="w-4 h-4 text-text-secondary" />
                        <span class="flex min-w-0 items-baseline justify-between gap-2">
                            <span class="truncate text-text-primary" :title="mod.modName">{{ mod.modName }}</span>
                            <span class="shrink-0 text-xs text-text-secondary">Spine {{ mod.stagingVersion }}</span>
                        </span>
                    </div>
                </div>
            </div>

            <div class="flex flex-col gap-2">
                <Checkbox v-model="createBackup" :disabled="copying"
                    :label="t('modsTab.modals.convertedMods.createBackup')" />
                <div v-if="createBackup" class="flex items-center gap-2 pl-7">
                    <span class="flex-1 min-w-0 truncate text-sm text-text-secondary" :title="backupDirectory">
                        {{ backupDirectory }}
                    </span>
                    <Button size="sm" :disabled="copying" :label="t('modsTab.modals.convertedMods.changeBackupFolder')"
                        @click="changeBackupDirectory" />
                </div>
            </div>

            <p v-if="error" class="text-sm text-error wrap-anywhere">{{ error }}</p>
        </div>

        <template #footer>
            <div class="flex justify-end gap-2 p-3">
                <Button variant="text" :disabled="copying" :label="t('common.actions.cancel')" @click="cancel" />
                <Button variant="primary" :disabled="copying || (createBackup && !backupDirectory)"
                    :label="t('modsTab.modals.convertedMods.copy')" @click="copyMods" />
            </div>
        </template>
    </Modal>
</template>
