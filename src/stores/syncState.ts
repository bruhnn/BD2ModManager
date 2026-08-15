import { defineStore } from "pinia";
import { reactive, readonly, ref } from "vue";
import { SyncError, SyncProgressStatus, SyncType, useModSyncEvents } from "../composables/useModSyncEvents";

export enum SyncStatus {
  IDLE = 'idle',
  SYNCING = 'syncing',
  COMPLETED = 'completed',
  FAILED = 'failed'
}

interface SyncedMod {
  status: SyncProgressStatus,
  modName: string,
  error?: SyncError,
  index: number,
  timestamp: string
}

export const useSyncStateStore = defineStore("syncState", () => {
  const syncEvents = useModSyncEvents()
  const status = ref<SyncStatus>(SyncStatus.IDLE);
  const progress = reactive({
    current: 0,
    total: 0,
  })
  const syncedMods = ref<SyncedMod[]>([])
  const lastSyncedMod = ref<SyncedMod | null>(null)
  const error = ref<SyncError | null>(null)
  const syncType = ref<SyncType | null>(null)

  function resetToDefault() {
    status.value = SyncStatus.IDLE
    progress.current = 0
    progress.total = 0
    syncedMods.value = []
    lastSyncedMod.value = null
    error.value = null
    syncType.value = null
  }

  function setupEvents() {
    syncEvents.clearEvents()

    syncEvents.onStart((event) => {
      resetToDefault()
      status.value = SyncStatus.SYNCING
      syncType.value = event.type

      console.log(event)
    })
    syncEvents.onProgress((event) => {
        const syncedMod: SyncedMod = {
          status: event.status,
          modName: event.modName,
          error: event.error ?? undefined,
          index: event.current,
          timestamp: new Date().toISOString() // event.timestamp
        }
        progress.current = event.current
        progress.total = event.total
        lastSyncedMod.value = syncedMod
        syncedMods.value.push(syncedMod)

    })
    syncEvents.onEnd((event) => {
      console.log("onEnd", event)
      if (event.success) {
        status.value = SyncStatus.COMPLETED
      } else {
        status.value = SyncStatus.FAILED
        if (event.error) {
          error.value = event.error
        }
      }

      lastSyncedMod.value = null

      console.log(status.value)
    })
  }

  setupEvents()

  return {
    type: readonly(syncType),
    lastSyncedMod: readonly(lastSyncedMod),
    status: readonly(status),
    progress: readonly(progress),
    syncedMods: readonly(syncedMods),
    error: readonly(error),
  }
})
