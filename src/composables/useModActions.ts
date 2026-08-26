import { useI18n } from "vue-i18n"
import { useLoggingStore } from "../stores/logging"
import { BD2Mod, useModsStore } from "../stores/mods"
import { useNotificationStore } from "../stores/notification"
import { getErrorMessage } from "../utils/errors"

export function useModActions() {
    const { t } = useI18n()
    const loggingStore = useLoggingStore()
    const notificationStore = useNotificationStore()

    const modsStore = useModsStore()

    // [TODO] debounced sync should be in the store or in here????

    function enableMods(mods: BD2Mod | BD2Mod[]): Promise<BD2Mod[]> {
        return modsStore.enableMods(mods instanceof Array ? mods.map(mod => mod.name) : [mods.name])
    }

    function disableMods(mods: BD2Mod | BD2Mod[]): Promise<BD2Mod[]>  {
        return modsStore.disableMods(mods instanceof Array ? mods.map(mod => mod.name) : [mods.name])
    }

    function toggleMods(mods: BD2Mod | BD2Mod[]) {
        const modsArray = mods instanceof Array ? mods : [mods]
        const modsToEnable = modsArray.filter(mod => !mod.enabled)
        const modsToDisable = modsArray.filter(mod => mod.enabled)
        if (modsToEnable.length > 0) {
            enableMods(modsToEnable)
        }
        if (modsToDisable.length > 0) {
            disableMods(modsToDisable)
        }
    }

    function setModAuthor(mods: BD2Mod | BD2Mod[], author: string | null): Promise<BD2Mod[]> {
        const modsArray = mods instanceof Array ? mods : [mods]
        return modsStore.setModAuthor(modsArray.map(mod => mod.name), author)
    }

    async function renameMod(mod: BD2Mod, newName: string): Promise<BD2Mod | undefined> {
        loggingStore.logDebug(`Renaming mod "${mod.name}" to "${newName}"`)

        try {
            const renamedMod = await modsStore.renameMod(mod.name, newName)

            notificationStore.add({
                type: "success",
                closable: true,
                title: t("modsTab.notifications.renameMod.success.title"),
                message: t("modsTab.notifications.renameMod.success.message", {
                    oldName: mod.name,
                    newName: renamedMod.name
                }),
                duration: 3000
            })

            loggingStore.logDebug(`Mod "${mod.name}" renamed successfully to "${renamedMod.name}"`)
            return renamedMod
        } catch (error) {
            const errorMsg = getErrorMessage(t, error)

            notificationStore.add({
                type: "error",
                closable: true,
                title: t("modsTab.notifications.renameMod.error.title"),
                message: errorMsg,
                duration: 5000
            })

            loggingStore.logError(`Error renaming mod "${mod.name}" to "${newName}": ${error}`)
        }
    }

    function previewMod(mod: BD2Mod) {
        loggingStore.logDebug(`Previewing mod: ${mod.name}`);

        modsStore.previewMod(mod.name).then(() => {
            loggingStore.logDebug(`Mod previewed successfully: ${mod.name}`);
        }).catch((error) => {
            // errors that can happen: just some errors like no permission to open the file, or the file doesn't exist anymore, or the file is not a valid mod file
            // no custom errors here
            let errorMsg = getErrorMessage(t, error);

            notificationStore.add({
                type: "error",
                closable: true,
                title: t("modsTab.errors.previewFailed.title", {modName: mod.name}),
                message: errorMsg,
                duration: 5000
            })

            loggingStore.logError(`An error occured while previewing the mod ${mod.name}: ${error}`);
        })
    }

    return {
        enableMods,
        disableMods,
        toggleMods,
        renameMod,
        setModAuthor,
        previewMod
    }
}
