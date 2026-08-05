<script setup lang="ts">
import {
  ArrowLeftFromLine,
  ArrowRightFromLine,
  ArrowRightLeft,
  RefreshCcw,
  TriangleAlert,
  X
} from '@lucide/vue'
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { refThrottled, useVirtualList } from '@vueuse/core'
import Button from '../common/Button.vue'
import Modal from '../common/Modal.vue'
import { SyncStatus, useSyncStateStore } from '../../stores/syncState'
import { SyncError, SyncProgressStatus, SyncType } from '../../composables/useSyncEvents'
import { useModsStore } from '../../stores/mods'
import { useDev } from '../../composables/useDev'

const { t } = useI18n()
const syncStateStore = useSyncStateStore()

const emit = defineEmits([
  'close',
  'cancel',
])

const props = defineProps({
  visible: Boolean
})

function handleClose() {
  emit('close')
}

const getModStatusIcon = (status: SyncProgressStatus) => {
  switch (status) {
    case SyncProgressStatus.Synced: return ArrowRightFromLine
    case SyncProgressStatus.UpToDate: return ArrowRightLeft
    case SyncProgressStatus.Removed: return ArrowLeftFromLine
    case SyncProgressStatus.Failed: return TriangleAlert
  }
}

const getModStatusColor = (status: SyncProgressStatus) => {
  switch (status) {
    case SyncProgressStatus.Synced: return 'text-success'
    case SyncProgressStatus.UpToDate: return 'text-info'
    case SyncProgressStatus.Removed: return 'text-warning'
    case SyncProgressStatus.Failed: return 'text-error'
    default: return 'text-text-secondary'
  }
}

function getErrorMessage(t: (key: string, params?: any) => string, error: SyncError | null | undefined): string {
  if (!error) return t('errors.unknownError')

  switch (error.type) {
    case 'SymlinkAdminRequired': return t('errors.symlinkAdminRequired')
    case 'PermissionDenied': return t('errors.permissionDenied')
    case 'DiskFull': return t('errors.diskFull')
    case 'ModPathNotFound': return t('errors.modPathNotFound', { path: error.details })
    case 'CopyFailed': return t('errors.copyFailed', { error: error.details })
    case 'SymlinkFailed': return t('errors.symlinkFailed', { error: error.details })
    case 'HardlinkFailed': return t('errors.hardlinkFailed', { error: error.details })
    case 'DirectoryCreationFailed': return t('errors.directoryCreationFailed', { error: error.details })
    case 'RemovalFailed': return t('errors.removalFailed', { error: error.details })
    default: return t('errors.unknownError', { error: JSON.stringify(error) })
  }
}

const formatTimestamp = (timestamp: string) => {
  return new Date(timestamp).toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

const title = computed(() => {
  if (syncStateStore.type === SyncType.Sync) {
    switch (syncStateStore.status) {
      case SyncStatus.SYNCING: return t('modals.sync.titles.syncing')
      case SyncStatus.COMPLETED: return t('modals.sync.titles.completed')
      case SyncStatus.FAILED: return t('modals.sync.titles.failed')
      case SyncStatus.IDLE: return t('modals.sync.titles.idle')
    }
  } else if (syncStateStore.type === SyncType.Unsync) {
    switch (syncStateStore.status) {
      case SyncStatus.SYNCING: return t('modals.sync.titles.removing')
      case SyncStatus.COMPLETED: return t('modals.sync.titles.removed')
      case SyncStatus.FAILED: return t('modals.sync.titles.failedToRemove')
      case SyncStatus.IDLE: return t('modals.sync.titles.idleToRemove')
    }
  } else {
    return t('modals.sync.titles.waitingForAction')
    }
})

const errorMessage = computed(() => {
  if (syncStateStore?.status === SyncStatus.FAILED && syncStateStore.error) {
    return getErrorMessage(t, syncStateStore.error)
  }
  return ''
})

const realProgress = computed(() => {
  if (!syncStateStore?.progress.total) return 100
  return Math.round(
    (syncStateStore.progress.current / syncStateStore.progress.total) * 100
  )
})

const progress = refThrottled(realProgress, 250)

const syncedMods = computed(() => syncStateStore.syncedMods || [])

const {
  list,
  containerProps,
  wrapperProps,
  scrollTo
} = useVirtualList(
  syncedMods,
  {
    itemHeight: 36,
    overscan: 10,
  }
)

const lastSyncedMod = refThrottled(ref(syncStateStore.lastSyncedMod), 250)

watch(
  () => syncStateStore.lastSyncedMod,
  (newVal) => {
    lastSyncedMod.value = newVal
  }
)

watch(
  () => syncedMods.value.length,
  (length) => {
    if (length > 0)
      scrollTo(length - 1)
  }
)

const modsStore = useModsStore()

function sM() {
  modsStore.syncMods()
}

const {isDev} = useDev()
</script>

<template>
  <Modal :show="visible" @close="handleClose" class="w-full min-w-xl max-w-2xl min-h-[80vh]">
    <template #header>
      <div class="flex items-center justify-between gap-3 min-w-0 p-4">
        <div class="min-w-0 flex-1" data-tauri-drag-region>
          <span class="text-sm font-semibold font-mono text-text-primary">
            {{ title }}
          </span>

          <div v-if="lastSyncedMod" class="mt-0.5 text-xs text-text-secondary font-mono truncate">
            <component :is="getModStatusIcon(lastSyncedMod.status)"
              :class="getModStatusColor(lastSyncedMod.status) + ' w-3.5 h-3.5 inline-block mr-1'" />
            {{ lastSyncedMod.modName }}
          </div>

          <div v-if="errorMessage" class="mt-1 text-xs text-error font-mono">
            {{ errorMessage }}
          </div>
        </div>

        <button v-if="isDev" class="shrink-0 flex items-center justify-center p-1 rounded-full
                 text-text-secondary hover:text-text-primary hover:bg-state-hover transition-colors cursor-pointer"
          @click="sM()">
          <RefreshCcw class="w-4 h-4" />
        </button>
        <button class="shrink-0 flex items-center justify-center p-1 rounded-full
                 text-text-secondary hover:text-text-primary hover:bg-state-hover transition-colors cursor-pointer"
          @click="handleClose">
          <X class="w-4 h-4" />
        </button>
      </div>
    </template>

    <template #footer>
      <div class="flex justify-end shrink-0 p-2 px-4">
        <Button :label="t('modals.sync.actions.close')" variant="default" @click="handleClose" />
      </div>
    </template>

    <div class="flex flex-col gap-2 flex-1 min-h-0 px-4">

      <div class="space-y-2 shrink-0">
        <div class="flex justify-between items-center">
          <span class="text-sm text-text-secondary font-mono">
            {{ progress }}%
          </span>

          <span v-if="syncStateStore.progress.current" class="text-sm text-text-secondary font-mono opacity-50">
            {{ syncStateStore.progress.current }} /
            {{ syncStateStore.progress.total }}
            {{ t('modals.sync.log.mods') }}
          </span>
        </div>

        <div class="h-2 bg-surface-input rounded-full overflow-hidden">
          <div class="h-full bg-accent rounded-full"
            :class="progress === 0 ? 'transition-none' : 'transition-all duration-150 ease-out'"
            :style="{ width: `${progress}%` }" />
        </div>
      </div>

      <div class="rounded-lg overflow-hidden font-mono flex flex-col flex-1 min-h-0">

        <div class="py-1.5 flex justify-between items-center shrink-0">
          <span class="text-xs text-text-secondary">
            {{ t('modals.sync.log.title') }}
          </span>

          <span v-if="syncedMods.length" class="text-xs py-0.5 px-1 rounded-xl text-text-secondary">
            {{ syncedMods.length }}
            {{ t('modals.sync.log.mods') }}
          </span>
        </div>

        <div v-if="!syncedMods.length" class="flex-1 flex items-center justify-center text-xs text-text-secondary">
          {{ t('modals.sync.log.waitingToStart') }}
        </div>

        <div v-else v-bind="containerProps" class="flex-1 min-h-0" style="height: 100%">
          <div v-bind="wrapperProps">
            <div v-for="item in list" :key="item.index"
              class="flex items-center gap-1 py-1 px-2 rounded text-xs transition-colors hover:bg-state-hover"
              style="height: 36px">
              <span class="text-text-secondary opacity-50 shrink-0 w-14 tabular-nums">
                {{ formatTimestamp(item.data.timestamp) }}
              </span>

              <span class="shrink-0 text-xs font-medium px-1.5 py-0.5 rounded-full"
                :class="getModStatusColor(item.data.status)">
                <component :is="getModStatusIcon(item.data.status)" class="w-4 h-4" />
              </span>

              <div class="flex-1 min-w-0 gap-2 flex">
                <span class="text-text-primary truncate block" :title="item.data.modName">
                  {{ item.data.modName }}
                </span>

                <span v-if="item.data.error" class="text-error text-xs mr-2"
                  :title="'details' in item.data.error ? item.data.error.details : ''">
                  {{ getErrorMessage(t, item.data.error) }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div class="flex flex-wrap items-center py-2 gap-3 border-t border-border-default shrink-0">
          <div class="flex items-center gap-1.5 text-xs text-text-secondary">
            <ArrowRightFromLine class="w-3.5 h-3.5 text-success" />
            <span>{{ t('modals.sync.status.synced') }}</span>
          </div>

          <div class="flex items-center gap-1.5 text-xs text-text-secondary">
            <ArrowLeftFromLine class="w-3.5 h-3.5 text-warning" />
            <span>{{ t('modals.sync.status.removed') }}</span>
          </div>

          <div class="flex items-center gap-1.5 text-xs text-text-secondary">
            <ArrowRightLeft class="w-3.5 h-3.5 text-info" />
            <span>{{ t('modals.sync.status.upToDate') }}</span>
          </div>

          <div class="flex items-center gap-1.5 text-xs text-text-secondary">
            <TriangleAlert class="w-3.5 h-3.5 text-error" />
            <span>{{ t('modals.sync.status.failed') }}</span>
          </div>
        </div>

      </div>

    </div>
  </Modal>
</template>