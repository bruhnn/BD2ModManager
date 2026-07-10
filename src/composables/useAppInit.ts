import { useSettingsStore } from "../stores/settings";
import { useCharactersStore } from "../stores/characters";
import { useProfilesStore } from "../stores/profiles";
import { useModsStore } from "../stores/mods";
import { useLoggingStore } from "../stores/logging";

export function useAppInitializer() {
  const loggingStore = useLoggingStore();
  const settingsStore = useSettingsStore();
  const modsStore = useModsStore();

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

  async function initialize(): Promise<{ isFirstLaunch: boolean, isBrownDustXOutdated: boolean }> {
    loggingStore.logDebug("Starting BD2ModManager");

    await Promise.all([
      settingsStore.loadSettings(),
      useCharactersStore().loadCharacters(),
      useCharactersStore().loadDating(),
      useProfilesStore().loadProfiles(),
    ]);

    await modsStore.discoverMods();

    if (settingsStore.settings.isFirstLaunch) {
      settingsStore.saveSettings({ isFirstLaunch: false });
    }

    await initializeGamePath();

    settingsStore.updateGameData();

    if (settingsStore.settings.autoUpdateModPreview) settingsStore.updateModPreview();
    
    if (settingsStore.settings.checkForAppUpdates) settingsStore.checkForAppUpdate();

    const brownDustXVersion = await settingsStore.getBrowndustxVersion();

    return {
      isFirstLaunch: settingsStore.settings.isFirstLaunch,
      isBrownDustXOutdated: brownDustXVersion?.status === "InstalledButOutdated"
    }
  }

  return { initialize };
}