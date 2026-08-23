<script setup lang="ts">
import { useLoggingStore } from '../../stores/logging';
import Modal from '../common/Modal.vue';
import { useI18n } from 'vue-i18n';
import Select from '../common/Select.vue';
import { computed, ref } from 'vue';
import Button from '../common/Button.vue';
import { globalModals } from '../../composables/useGlobalModals.ts';

const { t } = useI18n()

const {
    isOpen,
    closeModal
} = globalModals.logs

const loggingStore = useLoggingStore()

const logLevels = [
    { label: 'All', value: 'All' },
    { label: 'Success', value: 'Success' },
    { label: 'Info', value: 'Info' },
    { label: 'Warning', value: 'Warning' },
    { label: 'Error', value: 'Error' },
    { label: 'Debug', value: 'Debug' }
]
const selectedLogLevel = ref('All')

const filteredLogs = computed(() => {
    if (selectedLogLevel.value === 'All') {
        return loggingStore.logs
    }
    return loggingStore.logs.filter(log => log.level === selectedLogLevel.value)
})
</script>

<template>
    <Modal :show="isOpen" size="lg" @close="closeModal" :title="t('modals.logs.title')">
        <div class="flex flex-col h-full min-h-0 p-4">
            <Select v-model="selectedLogLevel" :options="logLevels" class="w-40 mb-4 shrink-0" />
            <div class="flex-1 min-h-0 bg-surface-card overflow-y-auto p-4 rounded border border-border-default">
                <p v-if="filteredLogs.length === 0" class="text-sm text-text-secondary whitespace-pre-wrap flex-1 h-full flex">{{
                    t('modals.logs.noLogs') }}
                </p>
                <div v-else class="flex flex-col">
                    <div v-for="log in filteredLogs" :key="log.timestamp.getTime()" class="flex flex-col ">
                        <div class="flex gap-2">
                            <span :class="{
                                'text-success': log.level === 'Success',
                                'text-info': log.level === 'Info',
                                'text-warning': log.level === 'Warning',
                                'text-error': log.level === 'Error',
                                'text-text-secondary': log.level === 'Debug',
                            }" class="font-mono font-semibold uppercase">
                                {{ log.level }}
                            </span>
                            <span class="text-text-secondary font-mono">
                                {{ log.timestamp.toLocaleString() }}
                            </span>
                        </div>
                        <span class="flex-1 text-text-primary break-all" :class="{
                            'text-error': log.level === 'Error'
                        }">
                            {{ log.message }}
                        </span>
                    </div>
                </div>
            </div>
            <div class="mt-4 flex justify-end gap-2 shrink-0">
                <Button @click="closeModal">{{ t('common.actions.close') }}</Button>
            </div>
        </div>
    </Modal>
</template>

<style scoped></style>
