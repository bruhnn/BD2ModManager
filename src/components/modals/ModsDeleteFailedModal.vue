<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RefreshCcw } from '@lucide/vue'
import { globalModals } from '../../composables/useGlobalModals'
import Button from '../common/Button.vue'
import Modal from '../common/Modal.vue'
import { getErrorMessage } from '../../utils/errors'

const { t } = useI18n()

const {
    isOpen,
    params,
    closeModal
} = globalModals.modsDeleteFailed

const failedEntries = computed(() => Object.entries(params.value?.failed ?? {}))
const retrying = ref(false)

async function handleRetry() {
    const retry = params.value?.onRetry
    if (!retry || retrying.value) return

    retrying.value = true
    try {
        const completed = await retry()
        if (completed) closeModal()
    } finally {
        retrying.value = false
    }
}
</script>

<template>
    <Modal :show="isOpen" size="md" :title="t('modals.modsDeleteFailed.title')"
        :subtitle="t('modals.modsDeleteFailed.subtitle', { count: failedEntries.length })" @close="closeModal">
        <div class="flex flex-col bg-surface-dialog px-4 py-4">
            <div class="flex flex-col gap-3">
                <div v-for="([modName, error]) in failedEntries" :key="modName"
                    class="flex min-w-0 flex-col gap-1.5 rounded-lg bg-surface-popover px-4 py-3">
                    <span class="wrap-anywhere text-[13px] font-semibold leading-5 text-text-primary">{{ modName }}</span>
                    <span class="wrap-anywhere text-sm leading-5 text-error">{{ getErrorMessage(t, {
                        ...error,
                        parent: 'ModDeleteError'
                    }) }}</span>
                </div>
            </div>
        </div>

        <template #footer>
            <div class="flex justify-end gap-2 p-4">
                <Button @click="closeModal">
                    {{ t('common.actions.close') }}
                </Button>
                <Button v-if="params?.onRetry" variant="primary" :icon="RefreshCcw"
                    :icon-class="{ 'animate-spin': retrying }" :disabled="retrying"
                    @click="handleRetry">
                    {{ t('modals.modsDeleteFailed.actions.retry') }}
                </Button>
            </div>
        </template>
    </Modal>
</template>
