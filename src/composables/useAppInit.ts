import { useSettingsStore } from "../stores/settings";
import { useCharactersStore } from "../stores/characters";
import { useProfilesStore } from "../stores/profiles";
import { useModsStore } from "../stores/mods";
import { useLoggingStore } from "../stores/logging";
import { AppUpdateAvailable, useUpdater } from "./useUpdater";
import { globalModals } from "./useGlobalModals";
import { useNotificationStore } from "../stores/notification";
import { useI18n } from "vue-i18n";
import { useGameStore } from "../stores/game";
import { useLocalStorage } from "@vueuse/core";

export function useAppInitializer() {
  const { t } = useI18n()
  const notificationStore = useNotificationStore()
  const loggingStore = useLoggingStore();
  const settingsStore = useSettingsStore();
  const modsStore = useModsStore();
  const gameStore = useGameStore()
  const skipUpdateVersion = useLocalStorage('skipUpdateVersion', '')

  const {
    checkForModPreviewUpdate,
    checkForAppUpdate,
    updateGameData,
  } = useUpdater()

  async function initializeGamePath() {
    // validate saved game dir, if is not valid show the game dir selection
    // [TODO] move to rust backend, there it can set the game dir
    // [TODO] what to do if the saved game directory is not valid? show the select game directory modal? or just show an error and let the user open the select game directory modal from settings?


    if (!settingsStore.settings.gameDirectory) {
      loggingStore.logDebug("No saved game directory found.");
      return;
    }

    try {
      loggingStore.logDebug("Checking current game directory:", settingsStore.settings.gameDirectory);
      const isValid = await settingsStore.validateGamePath(settingsStore.settings.gameDirectory);
      loggingStore.logDebug("Is game directory valid:", isValid);

      if (!isValid) {
        loggingStore.logDebug("Game directory is invalid.");
      }
    } catch (error) {
      loggingStore.logError("Error during game directory initialization:", error);
    }
  }

  async function initialize(): Promise<{ isFirstLaunch: boolean, isBrownDustXOutdated: boolean, isUpdateAvailable: boolean }> {
    loggingStore.logDebug("Starting BD2ModManager");

    await Promise.all([
      useCharactersStore().loadCharacters(),
      useProfilesStore().loadProfiles(),
    ]);

    await modsStore.discoverMods()
    await gameStore.refresh()

    const isFirstLaunch = settingsStore.settings.isFirstLaunch

    if (isFirstLaunch) {
      settingsStore.saveSettings({ isFirstLaunch: false })
    }

    await initializeGamePath()
    updateGameData()

    if (settingsStore.settings.autoUpdateModPreview) {
      checkForModPreviewUpdate(true)
    }

    let updateAvailable: AppUpdateAvailable | null = null

    if (import.meta.env.DEV || settingsStore.settings.checkForAppUpdates) {
      updateAvailable = await checkForAppUpdate()
    }
    
    if (isFirstLaunch) {
      globalModals.welcome.showModal()
    }

    if (updateAvailable && updateAvailable.versionAvailable !== skipUpdateVersion.value) {
      globalModals.updateAvailable.showModal(updateAvailable)
    }

    if (gameStore.browndustxVersion?.status === "InstalledButOutdated") {
      notificationStore.add({
        type: "warn",
        title: t('app.notifications.brownDustXOutdated.title'),
        message: t('app.notifications.brownDustXOutdated.message'),
        duration: 10000,
      })
    }

    return {
      isFirstLaunch,
      isBrownDustXOutdated: gameStore.browndustxVersion?.status === "InstalledButOutdated",
      isUpdateAvailable: updateAvailable !== null
    }
  }

  return { initialize };
}
