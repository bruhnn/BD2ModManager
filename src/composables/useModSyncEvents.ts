import { listen, UnlistenFn } from "@tauri-apps/api/event"
import { ref, Ref } from "vue"
import { useLoggingStore } from "../stores/logging"

export enum SyncType {
    Sync = "Sync",
    Unsync = "Unsync"
}

export enum SyncProgressStatus {
    Synced = "Synced",
    UpToDate = "UpToDate",
    Removed = "Removed",
    Failed = "Failed"
}


export interface SyncStartEvent {
    type: SyncType
}

export interface SyncProgressEvent {
    type: SyncType
    status: SyncProgressStatus
    modName: string
    current: number
    total: number
    error: SyncError | null
}

export interface SyncEndEvent {
    type: SyncType
    success: boolean
    synced: number
    total: number
    error: SyncError | null
}

export interface SyncError {
    type:
        | "SymlinkAdminRequired"
        | "PathNotFound"
        | "CopyFailed"
        | "SymlinkFailed"
        | "HardlinkFailed"
        | "RemovalFailed"
        | "DirectoryCreationFailed"
        | "GameModsDirectoryNotFound"
        | "Io"
    details: {
        kind?: string
        mod_name?: string
        path?: string
    } | null
    message: string
}

export function getSyncErrorMessage(
    t: (key: string, params?: any) => string,
    error: SyncError | null | undefined
): string {
    if (!error) return t("errors.AppError.Unknown")

    if (error.type === "Io") {
        return t(`errors.Io.${error.details!.kind}`)
    }

    const details = error.details ?? {}
    const reason = error.details?.kind
        ? t(`errors.Io.${error.details.kind}`)
        : ""

    return t(`errors.ModSyncError.${error.type}`, {
        ...details,
        reason
    })
}

interface SyncEventHandlers {
    onStart: (callback: (event: SyncStartEvent) => void) => void
    onProgress: (callback: (event: SyncProgressEvent) => void) => void
    onEnd: (callback: (event: SyncEndEvent) => void) => void
    clearEvents: () => void
}

export function useModSyncEvents(): SyncEventHandlers {
    const loggingStore = useLoggingStore()

    const unlistenFns: Ref<UnlistenFn[]> = ref([])

    const createListener = <T>(eventName: string) => {
        return async (callback: (payload: T) => void) => {
            try {
                const unlisten = await listen(eventName, (event) => {
                    callback(event.payload as T)
                })
                unlistenFns.value.push(unlisten)
            } catch (error) {
                loggingStore.logError(`Failed to listen to ${eventName}:`, error)
            }
        }
    }

    function clearEvents() {
        unlistenFns.value.forEach(unlisten => {
            try {
                unlisten()
            } catch (error) {
                loggingStore.logError('Error during unlisten:', error)
            }
        })
        unlistenFns.value = []
    }

    return {
        onStart: createListener<SyncStartEvent>('sync-start'),
        onProgress: createListener<SyncProgressEvent>('sync-progress'),
        onEnd: createListener<SyncEndEvent>('sync-end'),
        clearEvents
    }
}
