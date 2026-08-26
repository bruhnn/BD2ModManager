
import { useLocalStorage } from '@vueuse/core'
import { useLoggingStore } from '../stores/logging'
import { useModsStore } from '../stores/mods'
import { useNotificationStore } from '../stores/notification'
import { useI18n } from 'vue-i18n'
import { useConfirm } from '../plugins/ConfirmService'
import { getErrorMessage } from '../utils/errors'
// import { globalModals } from './useGlobalModals'

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

    async function syncMods() {
        loggingStore.logDebug(`Syncing mods [confirmation skipped: ${skipSyncConfirmation.value}]`);

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
                message: t('modsTab.confirmations.syncMods.descriptionWithConflicts'),
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

        if (!skipSyncConfirmation.value) {
            const { confirmed, rememberChoice } = await confirm.confirm({
                title: t('modsTab.confirmations.syncMods.title'),
                message: t('modsTab.confirmations.syncMods.description'),
                acceptButton: {
                    label: t('modsTab.confirmations.syncMods.actions.sync'),
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
                skipSyncConfirmation.value = true
            }
        }

        try {
            await modsStore.syncMods()
        } catch (error: any) {
            loggingStore.logError("An error occurred during mod sync:", JSON.stringify(error, null, 2));

            let errorMessage = getErrorMessage(t, error)

            notificationStore.add({
                closable: true,
                title: t('modsTab.errors.syncFailed.title'),
                message: errorMessage,
                duration: 5000,
                type: 'error'
            });

            return
        }

        loggingStore.logDebug(`Syncing mods completed successfully.`);

        notificationStore.add({
            type: 'success',
            closable: true,
            title: t('modsTab.notifications.syncMods.success.title'),
            message: t('modsTab.notifications.syncMods.success.description'),
            duration: 5000,
        })
    }

    async function unsyncMods() {
        loggingStore.logDebug(`Unsyncing mods [confirmation skipped: ${skipUnsyncConfirmation.value}]`);

        if (!skipUnsyncConfirmation.value) {
            const { confirmed, rememberChoice } = await confirm.confirm({
                title: t('modsTab.confirmations.unsyncMods.title'),
                message: t('modsTab.confirmations.unsyncMods.description'),
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
            await modsStore.unsyncMods();
        } catch (error: any) {
            loggingStore.logError("An error occurred during mod unsync:", JSON.stringify(error, null, 2));

            let errorMessage = getErrorMessage(t, error)

            notificationStore.add({
                closable: true,
                title: t('errors.unsyncFailed'),
                message: errorMessage,
                duration: 5000,
                type: 'error'
            });

            return
        }

        loggingStore.logDebug(`Unsyncing mods completed successfully.`);

        notificationStore.add({
            closable: true,
            title: t('modsTab.notifications.unsyncMods.success.title'),
            message: t('modsTab.notifications.unsyncMods.success.description'),
            duration: 3000,
            type: 'success'
        });
    }

    // should issyncneeded be here?

    return {
        // isSyncing: readonly(isSyncing),
        syncMods,
        unsyncMods,
    }
}
