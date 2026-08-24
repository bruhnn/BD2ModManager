import { useI18n } from "vue-i18n"
import { useConfirm } from "../plugins/ConfirmService"
import { useLoggingStore } from "../stores/logging"
import { BD2Mod, DeleteModsProgress, DeleteModsResult, useModsStore } from "../stores/mods"
import { useNotificationStore } from "../stores/notification"
import { globalModals } from "./useGlobalModals"
import { getErrorMessage } from "../utils/errors"

export function useModDelete() {
    const { t } = useI18n()
    const confirm = useConfirm()
    const loggingStore = useLoggingStore()
    const notificationStore = useNotificationStore()
    const modsStore = useModsStore()

    async function deleteConfirmedMods(
        modNames: string[],
        progressCallback?: (progress: DeleteModsProgress) => void,
        isRetry = false
    ): Promise<boolean> {
        try {
            const result: DeleteModsResult = await modsStore.deleteMods(modNames, (progress) => {
                loggingStore.logDebug(`Deleting mod ${progress.current} of ${progress.total}: ${progress.modName}`)
                if (progressCallback) progressCallback(progress)
            })

            const failedEntries = Object.entries(result.failed)
            const deletedCount = result.deleted.length
            const failedCount = failedEntries.length
            const totalCount = deletedCount + failedCount

            if (failedCount === 0) {
                notificationStore.add({
                    type: 'success',
                    title: t('modsTab.notifications.deleteMod.success.title', { count: deletedCount }),
                    message: t('modsTab.notifications.deleteMod.success.description', {
                        count: deletedCount,
                        modName: result.deleted[0]
                    })
                })
                return true
            }

            if (isRetry) {
                globalModals.modsDeleteFailed.showModal({
                    failed: result.failed,
                    onRetry: () => deleteConfirmedMods(Object.keys(result.failed), progressCallback, true)
                })
                return false
            }

            const error = getErrorMessage(t, {
                ...failedEntries[0][1],
                parent: "ModDeleteError"
            })

            notificationStore.add({
                type: 'error',
                title: t('modsTab.notifications.deleteMod.error.title', { count: totalCount }),
                message: t('modsTab.notifications.deleteMod.error.description', {
                    count: totalCount,
                    deletedCount,
                    totalCount,
                    modName: failedEntries[0][0],
                    error
                }),
                action: {
                    label: t('modsTab.notifications.deleteMod.error.actions.viewDetails'),
                    onClick: () => {
                        globalModals.modsDeleteFailed.showModal({
                            failed: result.failed,
                            onRetry: () => deleteConfirmedMods(Object.keys(result.failed), progressCallback, true)
                        })
                    }
                }
            })
            return false
        } catch (error) {
            loggingStore.logError("Error deleting mods:", error)

            notificationStore.add({
                type: 'error',
                title: t('modsTab.notifications.deleteMod.error.title', { count: modNames.length }),
                message: t('modsTab.notifications.deleteMod.error.unexpectedMessage')
            })
            return false
        }
    }

    async function deleteMods(mods: BD2Mod | BD2Mod[], progressCallback?: (progress: DeleteModsProgress) => void) {
        const modNames = mods instanceof Array ? mods.map(mod => mod.name) : [mods.name]

        if (modNames.length === 0) {
            loggingStore.logDebug("No mods selected for deletion, skipping.")
            return
        }

        const resultConfirm = await confirm.confirm({
            title: t('modsTab.confirmations.deleteMod.title', { count: modNames.length }),
            message: t('modsTab.confirmations.deleteMod.description', { count: modNames.length, modName: modNames[0] }),
            acceptButton: {
                variant: 'danger',
                label: t('modsTab.confirmations.deleteMod.actions.delete'),
            },
            rejectButton: {
                label: t('common.actions.cancel'),
            },
        })

        if (!resultConfirm.confirmed) {
            loggingStore.logDebug("Mod deletion cancelled by user.")
            return
        }

        await deleteConfirmedMods(modNames, progressCallback)
    }

    return {
        deleteMods
    }
}
