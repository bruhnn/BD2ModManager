// composables/useModInstaller.ts
import { open } from '@tauri-apps/plugin-dialog'
import { getErrorMessage } from '../utils/errors'
import { useI18n } from 'vue-i18n'
import { useLoggingStore } from '../stores/logging'
import { useModsStore } from '../stores/mods'
import { useNotificationStore } from '../stores/notification'


// composable because modstab and cahracters tab will both need to install mods, and we want to keep the logic in one place
export function useModInstall() {
  const modsStore = useModsStore()
  const loggingStore = useLoggingStore()
  const notificationStore = useNotificationStore()
  const { t } = useI18n()

  async function installFromZip() {
    const file = await open({
      multiple: false,
      filters: [{ name: 'Archive Files', extensions: ['zip', 'rar', '7z', 'tar', 'gz'] }]
    })

    loggingStore.logDebug("Selected file for mod installation from zip:", file)

    if (file && typeof file === 'string') {
      try {
        const modName = await modsStore.installModFromZip(file)

        notificationStore.add({
          type: 'success',
          closable: true,
          title: t('modsTab.notifications.modInstallSuccess.title'),
          message: t('modsTab.notifications.modInstallSuccess.description', { modName }),
          duration: 3000
        })

        return modName
      } catch (error) {
        loggingStore.logError("Error installing mod from zip:", error)

        const errorMsg = getErrorMessage(
          t,
          error instanceof Error ? error.message : String(error)
        )

        notificationStore.add({
          closable: true,
          title: t('errors.modInstallFailed.title'),
          message: errorMsg,
          type: 'error'
        })
      }
    }
  }

  async function installFromFolder() {
    const folder = await open({
      directory: true,
      multiple: false
    })

    loggingStore.logDebug("Selected folder for mod installation:", folder)

    if (folder && typeof folder === 'string') {
      try {
        const modName = await modsStore.installModFromFolder(folder)

        notificationStore.add({
          type: 'success',
          closable: true,
          title: t('modsTab.notifications.modInstallSuccess.title'),
          message: t('modsTab.notifications.modInstallSuccess.description', { modName }),
          duration: 3000
        })

        return modName
      } catch (error) {
        loggingStore.logError("Error installing mod from folder:", error)

        const errorMsg = getErrorMessage(
          t,
          error instanceof Error ? error.message : String(error)
        )

        notificationStore.add({
          closable: true,
          title: t('errors.modInstallFailed.title'),
          message: errorMsg,
          type: 'error'
        })
      }
    }
  }

  return {
    installFromZip,
    installFromFolder
  }
}