import { reactive, readonly, toRef } from "vue"
import { useI18n } from "vue-i18n"
import { Channel, invoke } from "@tauri-apps/api/core"
import { useNotificationStore } from "../stores/notification"
import { useLoggingStore } from "../stores/logging"
import { getErrorMessage } from "../utils/errors"
import { useCharactersStore } from "../stores/characters"

export interface AppUpdateAvailable {
    versionAvailable: string,
    currentVersion?: string,
    downloadUrl?: string,
    changelog?: string[],
    isUpdateRecommended?: boolean,
}

export interface ModPreviewUpdateAvailable {
    versionAvailable: string,
    currentVersion?: string,
    downloadUrl?: string
}

export type DownloadEvent =
    | {
        event: "Started"
        data: {
            totalSize: number | null
        }
    }
    | {
        event: "Progress"
        data: {
            chunkLength: number
        }
    }
    | {
        event: "Finished"
    }

// characters.json (for now), assets, etc.
type GameDataResources =
    | "characters" // cahracters database
    | "char_assets" // assets for these characters, if any character asset is missing bundled or in appdata

interface GameDataDownloadProgress {
    percentage: number | null
    current?: number
    total?: number
}

export type GameDataEvent =
    | {
        event: "Started"
    }
    | {
        event: "Updating"
        data: {
            resource: GameDataResources,
            percentage: number, // each resource has its own progress, characters (0-100%), assets (0-100%)
            label: string, // if assets
            download?: GameDataDownloadProgress
        }
    }
    | {
        event: "Updated",
        data: {
            resource: GameDataResources,
            label: string
        }
    }
    | {
        event: "Finished"
    }

export enum UpdateStatus {
    CheckingForUpdates = "checking for updates",
    UpdateAvailable = "new version available",
    Downloading = "downloading",
    Downloaded = "downloaded",
    Installing = "installing",
    Updating = "updating",
    Updated = "updated",
    Failed = "failed"
}

export interface DownloadProgress {
    total: number | null
    downloaded: number
}

interface GameDataProgress {
    resource: GameDataResources | null
    percentage: number
    label: string | null
    download?: GameDataDownloadProgress
}

interface GameDataResource {
    resource: GameDataResources
    progress: {
        percentage: number
        label: string | null
        download?: GameDataDownloadProgress
    }
}

type AppUpdateState = | null
    | { status: UpdateStatus.CheckingForUpdates }
    | { status: UpdateStatus.UpdateAvailable, update: AppUpdateAvailable }
    | { status: UpdateStatus.Downloading, update: AppUpdateAvailable, progress: DownloadProgress }
    | { status: UpdateStatus.Downloaded, update: AppUpdateAvailable }
    | { status: UpdateStatus.Installing, update: AppUpdateAvailable }
    | { status: UpdateStatus.Failed, error: string }

type ModPreviewState = | null
    | { status: UpdateStatus.CheckingForUpdates }
    | { status: UpdateStatus.UpdateAvailable, update: ModPreviewUpdateAvailable }
    | { status: UpdateStatus.Downloading, update: ModPreviewUpdateAvailable, progress: DownloadProgress }
    | { status: UpdateStatus.Downloaded, update: ModPreviewUpdateAvailable }
    | { status: UpdateStatus.Updating, update: ModPreviewUpdateAvailable }
    | { status: UpdateStatus.Updated, update: ModPreviewUpdateAvailable }
    | { status: UpdateStatus.Failed, error: string }

type GameDataState = | null
    | { status: UpdateStatus.CheckingForUpdates }
    // | { status: UpdateStatus.UpdateAvailable, resources: GameDataResource[] }
    | { status: UpdateStatus.Updating, resources: GameDataResource[], progress: GameDataProgress }
    | { status: UpdateStatus.Updated, resources: GameDataResource[] }
    | { status: UpdateStatus.Failed, error: string }

const state = reactive({
    app: null as AppUpdateState | null,
    modPreview: null as ModPreviewState | null,
    gameData: null as GameDataState | null
})
const appUpdate = toRef(state, "app")
const modPreviewUpdate = toRef(state, "modPreview")
const gameDataUpdate = toRef(state, "gameData")

export function useUpdater() {
    const { t } = useI18n()
    const loggingStore = useLoggingStore()
    const notificationStore = useNotificationStore()
    const charactersStore = useCharactersStore()


    // installer and portable
    async function checkForAppUpdate(): Promise<AppUpdateAvailable | null> {
        loggingStore.logDebug("Checking for app updates...")

        if (
            state.app?.status === UpdateStatus.CheckingForUpdates ||
            state.app?.status === UpdateStatus.Downloading ||
            state.app?.status === UpdateStatus.Downloaded ||
            state.app?.status === UpdateStatus.Installing
        ) {
            loggingStore.logDebug("Skipping update check while an update is in progress or ready to install.")
            return null
        }

        state.app = { status: UpdateStatus.CheckingForUpdates }

        try {
            const result = await invoke<AppUpdateAvailable | null>('check_for_app_update', {
            })

            loggingStore.logDebug("Update check result:", result)

            if (!result) {
                state.app = null
                loggingStore.logDebug("No mod manager update available.")
                return null
            }

            state.app = {
                status: UpdateStatus.UpdateAvailable,
                update: result
            }

            // auto updater is handled when user clicks on the update button in the titlebar, so no need to show a notification here
            loggingStore.logInfo(`Update available: ${result.versionAvailable} (current: ${result.currentVersion})`)
            return result
        } catch (error) {
            const errorMessage = getErrorMessage(t, error)

            state.app = {
                status: UpdateStatus.Failed,
                error: errorMessage
            }
            loggingStore.logError(`Failed to check for app updates: ${errorMessage}`)
            notificationStore.add({
                type: "error",
                title: t("app.notifications.appUpdate.checkFailed.title"),
                message: t("app.notifications.appUpdate.checkFailed.message", { error: errorMessage }),
            })
            return null
        }
    }

    // installer only
    async function downloadAppUpdate() {
        loggingStore.logDebug("Downloading app update...")

        if (!(state.app?.status === UpdateStatus.UpdateAvailable)) {
            notificationStore.add({
                type: "info",
                title: t("app.notifications.appUpdate.noUpdateAvailable.title"),
                message: t("app.notifications.appUpdate.noUpdateAvailable.message")
            })
            return
        }

        // if (state.app?.status === UpdateStatus.Downloading) return
        const update = state.app.update
        state.app = {
            status: UpdateStatus.Downloading,
            update,
            progress: { total: null, downloaded: 0 }
        }

        const onEvent = new Channel<DownloadEvent>()

        onEvent.onmessage = (event: DownloadEvent) => {
            switch (event.event) {
                case "Started":
                    state.app = {
                        status: UpdateStatus.Downloading,
                        update,
                        progress: {
                            total: event.data.totalSize,
                            downloaded: 0,
                        }
                    }
                    break
                case "Progress":
                    if (state.app?.status === UpdateStatus.Downloading) {
                        state.app.progress.downloaded += event.data.chunkLength
                    }
                    break

                case "Finished":
                    break
            }
        }

        try {
            await invoke("download_app_update", { onEvent })
            state.app = {
                status: UpdateStatus.Downloaded,
                update
            }
        } catch (error) {
            // revert back if any error occurr(no connection, etc)
            state.app = {
                status: UpdateStatus.UpdateAvailable,
                update
            }
            throw error
        }
    }

    // installer only
    async function installAppUpdate() {
        if (state.app?.status !== UpdateStatus.Downloaded) return

        let update = state.app.update

        state.app = {
            status: UpdateStatus.Installing,
            update
        }

        try {
            await invoke("install_app_update")
        } catch (error) {
            state.app = {
                status: UpdateStatus.Downloaded,
                update
            }
            throw error
        }
    }

    async function checkForModPreviewUpdate(downloadAndInstall?: boolean) {
        loggingStore.logDebug("Checking for mod preview update...")

        if (state.modPreview?.status === UpdateStatus.CheckingForUpdates) {
            loggingStore.logDebug("Update check for mod preview already in progress.")
            return null
        }

        state.modPreview = { status: UpdateStatus.CheckingForUpdates }

        // const onEvent = new Channel()

        try {
            const result = await invoke<ModPreviewUpdateAvailable | null>("check_for_mod_preview_update")

            if (!result) {
                // no update available
                state.modPreview = null
                loggingStore.logDebug("No update available for mod preview.")
                return
            }

            state.modPreview = {
                status: UpdateStatus.UpdateAvailable,
                update: result
            }

            // download and install
            if (downloadAndInstall) {
                await downloadAndInstallModPreview()
            }
        } catch (error) {
            const errorMessage = getErrorMessage(t, error)

            state.modPreview = {
                status: UpdateStatus.Failed,
                error: errorMessage
            }

            loggingStore.logError("Failed to check for Mod Preview updates", JSON.stringify(error))
            return null
        }

    }

    async function downloadAndInstallModPreview() {
        loggingStore.logDebug("Downloading and installing mod preview")
        if (state.modPreview?.status !== UpdateStatus.UpdateAvailable) {
            loggingStore.logDebug(`Update for mod preview is diff of update available ${JSON.stringify(state.modPreview?.status)}`)
            return
        }

        // state.modPreview = {
        //     status: UpdateStatus.
        // }
        const update = state.modPreview.update
        state.modPreview = {
            status: UpdateStatus.Downloading,
            update,
            progress: { total: null, downloaded: 0 }
        }

        const onEvent = new Channel((event: DownloadEvent) => {
            switch (event.event) {
                case "Started":
                    state.modPreview = {
                        status: UpdateStatus.Downloading,
                        update,
                        progress: {
                            total: event.data.totalSize,
                            downloaded: 0
                        }
                    }
                    break
                case "Progress":
                    if (state.modPreview?.status === UpdateStatus.Downloading) {
                        state.modPreview.progress.downloaded += event.data.chunkLength
                    }
                    break
                case "Finished":
                    break
            }
        })

        try {
            const result = await invoke<boolean>("download_mod_preview", { onEvent })

            if (!result) {
                state.modPreview = null
                loggingStore.logDebug("No update available for mod preview")
                return
            }

            state.modPreview = {
                status: UpdateStatus.Updated,
                update
            }

            notificationStore.add({
                type: "success",
                title: t("app.notifications.modPreviewUpdate.updated.title", {
                    version: update.versionAvailable
                }),
                duration: 5000,
                closable: true,
            })

            loggingStore.logInfo(`Mod Preview was updated successfully to version ${update.versionAvailable}`)
        } catch (error) {
            const errorMessage = getErrorMessage(t, error)

            state.modPreview = {
                status: UpdateStatus.Failed,
                error: errorMessage
            }

            notificationStore.add({
                type: "error",
                title: t("app.notifications.modPreviewUpdate.failed.title"),
                message: errorMessage,
                duration: 0,
                closable: true,
            })

            loggingStore.logError("Failed to download and install mod preview")
            throw error
        }
    }

    async function updateGameData() {
        if (
            state.gameData?.status === UpdateStatus.CheckingForUpdates ||
            state.gameData?.status === UpdateStatus.Updating
        ) return

        state.gameData = { status: UpdateStatus.CheckingForUpdates }

        const onEvent = new Channel((event: GameDataEvent) => {
            switch (event.event) {
                case "Started":
                    state.gameData = {
                        status: UpdateStatus.Updating,
                        resources: [],
                        progress: {
                            resource: null,
                            percentage: 0,
                            label: null,
                        },
                    }
                    break

                case "Updating": {
                    if (state.gameData?.status !== UpdateStatus.Updating) {
                        break
                    }

                    let resource = state.gameData.resources.find(
                        resource => resource.resource === event.data.resource
                    )

                    if (!resource) {
                        resource = {
                            resource: event.data.resource,
                            progress: {
                                percentage: event.data.percentage,
                                label: event.data.label,
                                download: event.data.download,
                            },
                        }

                        state.gameData.resources.push(resource)
                    } else {
                        resource.progress = {
                            percentage: event.data.percentage,
                            label: event.data.label,
                            download: event.data.download,
                        }
                    }

                    state.gameData.progress = {
                        resource: event.data.resource,
                        percentage: event.data.percentage,
                        label: event.data.label,
                        download: event.data.download,
                    }

                    break
                }

                case "Updated": {
                    if (state.gameData?.status !== UpdateStatus.Updating) {
                        break
                    }

                    let resource = state.gameData.resources.find(
                        resource => resource.resource === event.data.resource
                    )

                    // In case Updated arrives without an Updating event first
                    if (!resource) {
                        resource = {
                            resource: event.data.resource,
                            progress: {
                                percentage: 100,
                                label: null,
                            },
                        }

                        state.gameData.resources.push(resource)
                    } else {
                        // [INFO] should we set 100 or let the backend send the event with 100%?
                        resource.progress.percentage = 100
                        resource.progress.label = event.data.label
                        resource.progress.download = undefined
                    }

                    if (state.gameData.progress.resource === event.data.resource) {
                        state.gameData.progress.percentage = 100
                        state.gameData.progress.label = event.data.label
                        state.gameData.progress.download = undefined
                    }

                    break
                }

                case "Finished":
                    if (state.gameData?.status === UpdateStatus.Updating) {
                        state.gameData = {
                            status: UpdateStatus.Updated,
                            resources: state.gameData.resources,
                        }
                    }

                    break
            }
        })

        try {
            await invoke("update_game_data", { onEvent })

            await charactersStore.loadCharacters()

            notificationStore.add({
                type: "success",
                title: t("app.notifications.gameDataUpdate.updated.title"),
                duration: 4000,
                closable: true,
            })

        } catch (error) {
            const errorMessage = getErrorMessage(t, error)

            state.gameData = {
                status: UpdateStatus.Failed,
                error: errorMessage,
            }

            notificationStore.add({
                type: "error",
                title: t("app.notifications.gameDataUpdate.failed.title"),
                message: errorMessage,
                duration: 0,
                closable: true,
            })

            loggingStore.logError("Failed to update game data", error)
        }
    }

    return {
        appUpdate: readonly(appUpdate),
        modPreviewUpdate: readonly(modPreviewUpdate),
        gameDataUpdate: readonly(gameDataUpdate),
        checkForAppUpdate,
        downloadAppUpdate,
        installAppUpdate,
        checkForModPreviewUpdate,
        downloadAndInstallModPreview,
        updateGameData,
    }
}
