
import { useLocalStorage } from '@vueuse/core'
import { useLoggingStore } from '../stores/logging'
import { useModsStore } from '../stores/mods'
import { useNotificationStore } from '../stores/notification'
import { useI18n } from 'vue-i18n'
import { useConfirm } from '../plugins/ConfirmService'
import { getErrorMessage } from '../utils/errors'
import { globalModals } from './useGlobalModals'

export function useModSync() {
    const { t } = useI18n()
    const loggingStore = useLoggingStore()
    const notificationStore = useNotificationStore()
    const confirm = useConfirm()

    const modsStore = useModsStore()

    const skipSyncConfirmation = useLocalStorage('skipSyncModsConfirmation', false)
    const skipUnsyncConfirmation = useLocalStorage('skipUnsyncModsConfirmation', false)
    const skipSyncConflictsModal = useLocalStorage('skipSyncConflictsModal', false)

    // const isSyncing = computed(() => modsStore.isSyncing)

    async function syncMods(removeUnmanagedMods: boolean = false) {
        loggingStore.logDebug(`Syncing mods [confirmation skipped = ${skipSyncConfirmation.value}, remove unmanaged mods = ${removeUnmanagedMods}]`);

        if (modsStore.isSyncing) {
            loggingStore.logDebug("Mod sync already in progress.");
            return
        }

        const hasConflicts = modsStore.extendedMods.some(mod => mod.conflictingMods.length > 0)

        if (hasConflicts && !skipSyncConflictsModal.value) {
            // loggingStore.logDebug("Mod conflicts detected. Showing conflict modal.");
            // globalModals.conflict.showModal()
            // return

            const { confirmed } = await confirm.confirm({
                title: t('modsTab.confirmations.syncMods.titleWithConflicts'),
                message: t('modsTab.confirmations.syncMods.messageWithConflicts'),
                acceptButton: {
                label: t('modsTab.confirmations.syncMods.actions.syncAnyway'),
                },
                rejectButton: {
                label: t('common.actions.cancel'),
                },
            })

            if (!confirmed) {
                loggingStore.logDebug("User cancelled sync due to conflicts.");
                return
            }
        }

        // because we dont remove the other mods like before we dont need to ask for confirmation anymore

        // if (!skipSyncConfirmation.value) {
        //     const { confirmed, rememberChoice } = await confirm.confirm({
        //         title: t('modsTab.confirmations.syncMods.title'),
        //         message: t('modsTab.confirmations.syncMods.message'),
        //         acceptButton: {
        //             label: t('modsTab.confirmations.syncMods.actions.sync'),
        //         },
        //         rejectButton: {
        //             label: t('common.actions.cancel'),
        //         },
        //         showRememberChoice: true
        //     })

        //     if (!confirmed) {
        //         return
        //     }

        //     if (rememberChoice) {
        //         skipSyncConfirmation.value = true
        //     }
        // }

        if (removeUnmanagedMods) {
            const { confirmed } = await confirm.confirm({
                title: t('modsTab.confirmations.syncMods.title'),
                message: t('modsTab.confirmations.syncMods.messageWithRemoveUnmanaged'),
                acceptButton: { 
                    label: t('modsTab.confirmations.syncMods.actions.syncAndRemoveUnmanaged'),
                },
                rejectButton: {
                    label: t('common.actions.cancel'),
                }
            })


            if (!confirmed) {
                loggingStore.logDebug("User cancelled sync with remove unmanaged mods.");
                return
            }
        }

        try {
            const result = await modsStore.syncMods(removeUnmanagedMods)
            if (!result) return

            if (result.skipped_unmanaged > 0) {
                notificationStore.add({
                    type: 'warn',
                    closable: true,
                    title: t('modsTab.notifications.syncMods.skippedUnmanaged.title'),
                    message: t('modsTab.notifications.syncMods.skippedUnmanaged.message', {
                        count: result.skipped_unmanaged,
                        action: t('modsTab.confirmations.syncMods.actions.syncAndRemoveUnmanaged'),
                    }, result.skipped_unmanaged),
                })
            }

            if (result.synced < result.total) {
                loggingStore.logDebug(`Syncing mods completed with errors: ${result.synced} of ${result.total}.`);
                notificationStore.add({
                    type: 'warn',
                    closable: true,
                    title: t('modsTab.notifications.syncMods.completedWithErrors.title'),
                    message: t('modsTab.notifications.syncMods.completedWithErrors.message', { synced: result.synced, total: result.total }),
                    action: {
                        label: t('modsTab.notifications.syncMods.completedWithErrors.details'),
                        onClick: () => globalModals.sync.showModal()
                    }
                })
                return
            }

            if (result.skipped_unmanaged > 0 && result.total === 0) return

            if (result.success && result.synced === result.total && result.total === 0) {
                // no sync needed, no changes
                loggingStore.logDebug(`Syncing mods completed successfully. No changes were made.`);
                notificationStore.add({
                    type: 'info',
                    closable: true,
                    title: t('modsTab.notifications.syncMods.noChanges.title', 'Sync Mods'),
                    message: t('modsTab.notifications.syncMods.noChanges.message', 'No changes were made during the sync process.'),
                    duration: 3000,
                })
                return
            }

            
            loggingStore.logDebug(`Syncing mods completed successfully.`);

            notificationStore.add({
                type: 'success',
                closable: true,
                title: t('modsTab.notifications.syncMods.success.title'),
                message: t('modsTab.notifications.syncMods.success.message'),
                action: {
                    label: t('modsTab.notifications.syncMods.success.details'),
                    onClick: () => globalModals.sync.showModal()
                },
                duration: 5000,
            })
        } catch (error: any) {
            loggingStore.logError("An error occurred during mod sync:", JSON.stringify(error, null, 2));

            let errorMessage = getErrorMessage(t, error)

            notificationStore.add({
                closable: true,
                title: t('modsTab.notifications.syncMods.error.title'),
                message: errorMessage,
                duration: 5000,
                type: 'error'
            });

            return
        }

    }

    async function unsyncMods(removeUnmanagedMods: boolean = false) {
        loggingStore.logDebug(`Unsyncing mods [confirmation skipped: ${skipUnsyncConfirmation.value}]`);

        if (!skipUnsyncConfirmation.value) {
            const { confirmed, rememberChoice } = await confirm.confirm({
                title: t('modsTab.confirmations.unsyncMods.title'),
                message: t('modsTab.confirmations.unsyncMods.message'),
                acceptButton: {
                    label: t('modsTab.confirmations.unsyncMods.actions.unsync'),
                },
                rejectButton: {
                    label: t('common.actions.cancel'),
                },
                showRememberChoice: true
            })

            if (!confirmed) {
                return
            }

            if (rememberChoice) {
                skipUnsyncConfirmation.value = true
            }
        }

        try {
            const result = await modsStore.unsyncMods(removeUnmanagedMods)
            if (!result) return

            if (result.skipped_unmanaged > 0) {
                notificationStore.add({
                    type: 'warn',
                    closable: true,
                    title: t('modsTab.notifications.unsyncMods.skippedUnmanaged.title'),
                    message: t('modsTab.notifications.unsyncMods.skippedUnmanaged.message', {
                        count: result.skipped_unmanaged,
                        action: t('modsTab.notifications.unsyncMods.skippedUnmanaged.action'),
                    }, result.skipped_unmanaged),
                })
            }

            if (result.synced < result.total) {
                notificationStore.add({
                    type: 'warn',
                    closable: true,
                    title: t('modsTab.notifications.unsyncMods.completedWithErrors.title'),
                    message: t('modsTab.notifications.unsyncMods.completedWithErrors.message', { synced: result.synced, total: result.total }),
                    action: {
                        label: t('modsTab.notifications.unsyncMods.completedWithErrors.details'),
                        onClick: () => globalModals.sync.showModal()
                    }
                })
                return
            }

            if (result.skipped_unmanaged > 0 && result.total === 0) return

            if (result.total === 0) {
                notificationStore.add({
                    type: 'info',
                    closable: true,
                    title: t('modsTab.notifications.unsyncMods.noChanges.title'),
                    message: t('modsTab.notifications.unsyncMods.noChanges.message'),
                    duration: 3000,
                })
                return
            }
            loggingStore.logDebug(`Unsyncing mods completed successfully.`);
            notificationStore.add({
                closable: true,
                title: t('modsTab.notifications.unsyncMods.success.title'),
                message: t('modsTab.notifications.unsyncMods.success.message'),
                duration: 3000,
                type: 'success'
            });
        } catch (error: any) {
            loggingStore.logError("An error occurred during mod unsync:", JSON.stringify(error, null, 2));

            let errorMessage = getErrorMessage(t, error)

            notificationStore.add({
                closable: true,
                title: t('modsTab.notifications.unsyncMods.error.title'),
                message: errorMessage,
                duration: 5000,
                type: 'error'
            });

            return
        }
    }

    // should issyncneeded be here?

    return {
        // isSyncing: readonly(isSyncing),
        syncMods,
        unsyncMods,
    }
}
