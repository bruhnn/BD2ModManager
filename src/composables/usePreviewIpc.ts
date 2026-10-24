import { onMounted, onUnmounted, watch } from "vue"
import { invoke } from "@tauri-apps/api/core"
import { listen, type UnlistenFn } from "@tauri-apps/api/event"
import { type BD2Mod, useModsStore } from "../stores/mods"
import { useLoggingStore } from "../stores/logging"

export function usePreviewIpc() {
    const modsStore = useModsStore()
    const loggingStore = useLoggingStore()
    let unlisten: UnlistenFn | undefined
    let disposed = false

    onMounted(async () => {
        unlisten = await listen<BD2Mod[]>("preview-mods-changed", ({ payload }) => {
            modsStore.applyPreviewModChanges(payload)
        })
        if (disposed) { unlisten(); return }
        try {
            await invoke("start_preview_ipc")
        } catch (error) {
            loggingStore.logError("Could not start Preview IPC:", error)
        }
    })

    watch(() => modsStore.mods, () => {
        invoke("publish_preview_mods").catch(error => loggingStore.logError("Could not update Preview:", error))
    }, { deep: true })

    onUnmounted(() => { disposed = true; unlisten?.() })
}
