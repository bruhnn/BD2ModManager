import { open } from '@tauri-apps/plugin-dialog'
import { getErrorMessage } from '../utils/errors'
import { useI18n } from 'vue-i18n'
import { useLoggingStore } from '../stores/logging'
import { BD2Mod, useModsStore } from '../stores/mods'
import { useNotificationStore } from '../stores/notification'

const ARCHIVE_FORMATS = ['rar', 'zip', '7z']

// composable because modstab and cahracters tab will both need to install mods, and we want to keep the logic in one place
export function useModInstall() {
  const modsStore = useModsStore()
  const loggingStore = useLoggingStore()
  const notificationStore = useNotificationStore()
  const { t } = useI18n()

  async function installMod(path: string) {
    if (ARCHIVE_FORMATS.includes(path.split('.').pop()?.toLowerCase() || '')) {
      await installFromZip(path)
    } else {
      await installFromFolder(path)
    }
  }

  async function installFromZip(path?: string): Promise<BD2Mod | undefined> {
    let filePath: string | undefined | null = path
    if (!filePath) {
      filePath = await open({
        multiple: false,
        filters: [{ name: 'Archive Files', extensions: ARCHIVE_FORMATS }]
      })
    }

    loggingStore.logDebug("Selected file for mod installation from zip:", filePath)
    const modName = filePath?.replace(/[\\/]+$/, '').split(/[\\/]/).pop() ?? 'UNKNOWN'

    if (filePath && typeof filePath === 'string') {
      try {
        const mod = await modsStore.installModFromZip(filePath)

        notificationStore.add({
          type: 'success',
          closable: true,
          title: t('modsTab.notifications.installMod.success.title'),
          message: t('modsTab.notifications.installMod.success.description', { modName: mod.name })
        })

        return mod
      } catch (error) {
        loggingStore.logError("Error installing mod from zip:", JSON.stringify(error))

        const errorMsg = getErrorMessage(
          t,
          error
        )

        notificationStore.add({
          closable: true,
          title: t('modsTab.notifications.installMod.error.title', { modName }),
          message: errorMsg,
          type: 'error'
        })
      }
    }
  }

  async function installFromFolder(path?: string): Promise<BD2Mod | undefined> {
    let folderPath: string | undefined | null = path

    if (!folderPath) {
      folderPath = await open({
        directory: true,
        multiple: false
      })
    }

    if (!folderPath) {
      loggingStore.logWarning("Folder path is empty.")
      return
    }

    loggingStore.logDebug("Selected folder for mod installation:", folderPath)

    const modName = folderPath.replace(/[\\/]+$/, '').split(/[\\/]/).pop() ?? 'UNKNOWN'

    if (folderPath && typeof folderPath === 'string') {
      try {
        const mod = await modsStore.installModFromFolder(folderPath)

        notificationStore.add({
          type: 'success',
          closable: true,
          title: t('modsTab.notifications.installMod.success.title'),
          message: t('modsTab.notifications.installMod.success.description', { modName: mod.name })
        })

        return mod
      } catch (error) {
        loggingStore.logError("Error installing mod from folder:", JSON.stringify(error))

        const errorMsg = getErrorMessage(
          t,
          error
        )

        notificationStore.add({
          closable: true,
          title: t('modsTab.notifications.installMod.error.title', { modName }),
          message: errorMsg,
          type: 'error'
        })
      }
    }
  }

  return {
    installMod,
    installFromZip,
    installFromFolder
  }
}
