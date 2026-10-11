export enum Status {
    Installed = "Installed",
    NotInstalled = "NotInstalled",
    InstalledButOutdated = "InstalledButOutdated",
    BepInExMissing = "BepInExMissing"
}

export type CanRemove = { type: "Yes" } | { type: "No"; reason: string }

export type PluginState = {
    status: Status
    version: string | null
    canConfigure?: boolean
    canRemove?: CanRemove
}

export type InstallBepInExError =
    | { type: "GamePathNotSet" }
    | { type: "BepInExAlreadyInstalled" }
    | { type: "InvalidBepInExArchive"; message: string }
    | { type: "DownloadFailed"; message: string }
    | { type: "ExtractionFailed"; message: string }
    | { type: "ArchiveNotFound"; message: string }
    | { type: "Unknown"; message: string }