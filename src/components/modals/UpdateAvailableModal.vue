<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useNotificationStore } from '../../stores/notification';
import { useLoggingStore } from '../../stores/logging';
import { getErrorMessage } from '../../utils/errors';
import { useLocalStorage } from '@vueuse/core';

import { openUrl } from '@tauri-apps/plugin-opener';

import { globalModals } from '../../composables/useGlobalModals.ts';
import { usePortable } from '../../composables/usePortable.ts';
import { UpdateStatus, useUpdater } from '../../composables/useUpdater.ts';

import Modal from '../common/Modal.vue';
import Button from '../common/Button.vue';
import Checkbox from '../common/Checkbox.vue';

const {
    isOpen,
    params,
    closeModal
} = globalModals.updateAvailable

const {
    isPortable
} = usePortable()

const {
    appUpdate,
    downloadAppUpdate
} = useUpdater()

const skipUpdateVersion = useLocalStorage('skipUpdateVersion', '') // version
const checkboxSkipVersion = ref(false)
const isUpdating = ref(false)
const { t } = useI18n()
const notificationStore = useNotificationStore()
const loggingStore = useLoggingStore()

watch(isOpen, (value) => {
    if (value) {
        checkboxSkipVersion.value = skipUpdateVersion.value === params.value?.versionAvailable
    }
})

const typeColors = {
    added: 'bg-changelog-added-bg text-changelog-added',
    improved: 'bg-changelog-improved-bg text-changelog-improved',
    fixed: 'bg-changelog-fixed-bg text-changelog-fixed',
    removed: 'bg-changelog-removed-bg text-changelog-removed'
}

const typeOrder = {
    added: 0,
    improved: 1,
    fixed: 2,
    removed: 3
}

const changelog = computed(() => params.value?.changelog?.map((item) => {
    const [type, ...description] = item.split(' ')
    const typeKey = type.toLowerCase() as keyof typeof typeColors

    return {
        type,
        description: description.join(' '),
        color: typeColors[typeKey],
        order: typeOrder[typeKey]
    }
}).sort((a, b) => a.order - b.order) ?? [])

const canSkipVersion = computed(() => {
    return !params.value?.isUpdateRecommended
})

async function handleAction() {
    if (isUpdating.value) return
    isUpdating.value = true

    try {
        if (isPortable.value) {
            await openUrl(params.value?.downloadUrl ?? '')
        } else {
            await downloadAppUpdate()
        }
        closeModal()
    } catch (error) {
        loggingStore.logError("Failed to download app update", error)
        notificationStore.add({
            type: 'error',
            title: t('app.notifications.appUpdate.downloadFailed.title'),
            message: getErrorMessage(t, error),
        })
    } finally {
        isUpdating.value = false
    }
}
</script>

<template>
    <!-- [TODO] add a download icon next to the icon -->
    <Modal :show="isOpen" size="sm" @close="closeModal"
        :title="$t('app.modals.updateAvailable.title')"
        :subtitle="$t('app.modals.updateAvailable.subtitle', { version: params?.versionAvailable })">
        <div class="flex flex-col gap-1 p-4">
            <p class="text-normal font-medium flex items-center gap-2 text-text-primary mb-2">
                {{ $t("app.modals.updateAvailable.changelogLabel") }}
            </p>
            <div class="flex flex-col gap-1">
                <div v-for="(item, index) in changelog" :key="index"
                    class="flex items-center gap-2 px-1.5 py-1.5 text-sm">
                    <span :class="item.color"
                        class="rounded-md px-2 py-0.5 text-xs font-semibold shrink-0">
                        {{ item.type }}
                    </span>
                    <span class="text-text-primary py-0.5">{{ item.description }}</span>
                </div>
            </div>
        </div>


        <template #footer>
            <div class="flex items-center gap-2 p-3">
                <div class="flex-1" v-if="canSkipVersion">
                    <Checkbox v-model="checkboxSkipVersion" @update:model-value="(value) => {
                        if (value) {
                            skipUpdateVersion = params?.versionAvailable ?? ''
                        } else {
                            skipUpdateVersion = ''
                        }
                    }"
                        :label="$t('app.modals.updateAvailable.skipLabel')" />
                </div>
                <span v-else class="flex-1"></span>
                <Button variant="default" @click="closeModal">
                    {{ $t('app.modals.updateAvailable.actions.later') }}
                </Button>
                <Button v-if="isPortable" variant="primary" @click="handleAction"
                    :disabled="isUpdating || appUpdate?.status === UpdateStatus.Downloading || appUpdate?.status === UpdateStatus.Installing">
                    {{ $t('app.modals.updateAvailable.actions.goToReleases') }}
                </Button>
                <Button v-else variant="primary" @click="handleAction"
                    :disabled="isUpdating || appUpdate?.status === UpdateStatus.Downloading || appUpdate?.status === UpdateStatus.Installing">
                    {{ $t("app.modals.updateAvailable.actions.downloadUpdate") }}
                </Button>
            </div>
        </template>
    </Modal>
</template>
