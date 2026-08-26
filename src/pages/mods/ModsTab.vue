<script setup lang="ts">
import { Folder, FolderMinus, FolderPlus, FolderSync, RefreshCcw } from "@lucide/vue";

import { computed, defineComponent, h, onActivated, onDeactivated, reactive, ref, useTemplateRef, watch } from "vue";
import { watchDebounced } from "@vueuse/core";
import { useI18n } from "vue-i18n";

import { listen } from "@tauri-apps/api/event";
import { join } from "@tauri-apps/api/path";
import { openPath } from "@tauri-apps/plugin-opener";
import { invoke } from "@tauri-apps/api/core";

import { useModsStore, BD2Mod } from "../../stores/mods";
import { useSettingsStore } from "../../stores/settings";
import { useLoggingStore } from "../../stores/logging";
import { useNotificationStore } from '../../stores/notification';

import { useHeader } from "../../composables/useHeader";

import Button from "../../components/common/Button.vue";
import MultiButton from "../../components/common/MultiButton.vue";
import Popover from "../../components/common/Popover.vue";

import UpdateAuthorModal from "./modals/UpdateAuthorModal.vue";
import RenameModModal from "./modals/RenameModModal.vue";

import ModsHeader from "./ModsHeader.vue";
import Modlist from "./Modlist.vue";

import { useGameStore } from "../../stores/game.ts";
import { useModActions } from "../../composables/useModActions.ts";
import { useModDelete } from "../../composables/useModDelete.ts";
import { useModInstall } from "../../composables/useModInstall.ts";
import { useModSync } from "../../composables/useModSync.ts";

let unlistenFns: Array<() => void> = []

const updateAuthorModal = useTemplateRef("updateAuthorModal")
const renameModModal = useTemplateRef("renameModModal")

const { t } = useI18n();
const loggingStore = useLoggingStore()
const notificationStore = useNotificationStore()
const modsStore = useModsStore()
const settingsStore = useSettingsStore()
const gameStore = useGameStore()

const {
  enableMods,
  disableMods,
  renameMod,
  previewMod
} = useModActions()

const {
  deleteMods
} = useModDelete()

const {
  installMod,
  installFromZip,
  installFromFolder
} = useModInstall()

const {
  syncMods,
  unsyncMods
} = useModSync()

const isRefreshing = ref(false)
// [TODO] reactive is sync needed
const isSyncNeeded = ref(0)

const debouncedSearchQuery = ref('');

let filters = reactive({
  searchQuery: '',
  modTypes: [] as ("Standing" | "Cutscene" | "Scene" | "NPC" | "Dating" | "Minigame")[],
  onlyEnabled: false,
  onlyDisabled: false,
  onlyConflicts: false,
  onlyErrors: false,
  hideErrors: false,
});

const totalModsCount = computed(() => modsStore.extendedMods.length)
const enabledModsCount = computed(() => modsStore.extendedMods.filter(mod => mod.enabled && !mod.errors.length).length)

const filteredMods = computed(() => {
  return modsStore.extendedMods.filter((mod) => {
    const conflictMatch = debouncedSearchQuery.value.match(/conflictsWith:"([^"]+)"/i)
    const conflictFilter = conflictMatch ? conflictMatch[1].toLowerCase() : null

    const cleanedQuery = debouncedSearchQuery.value.replace(/conflictsWith:"[^"]*"/i, '').trim()

    if (cleanedQuery) {
      const queries = [...cleanedQuery.toLowerCase().matchAll(/"([^"]+)"|([^,]+)/g)]
        .map(match => {
          const raw = match[0].trim()
          const isExact = raw.startsWith('"') && raw.endsWith('"')
          return {
            value: isExact ? raw.slice(1, -1) : raw,
            exact: isExact
          }
        })
        .filter(q => q.value.length > 0)

      const matchesAnyQuery = queries.some(({ value, exact }) => {
        if (exact) {
          return mod.name.toLowerCase() === value
        }
        return mod.name.toLowerCase().includes(value) ||
          (mod.author && mod.author.toLowerCase().includes(value)) ||
          (mod.character && `${mod.character.character.toLowerCase()} - ${mod.character.costume.toLowerCase()}`.includes(value))
      })

      if (!matchesAnyQuery) return false
    }

    if (conflictFilter) {
      if (
        mod.name.toLowerCase() !== conflictFilter &&
        !mod.conflictsWith.map(c => c.toLowerCase()).includes(conflictFilter)
      ) {
        return false
      }
    }

    if (filters.modTypes.length > 0) {
      if (!mod.modType) return false
      if (!filters.modTypes.includes(mod.modType.type)) return false
    }

    if (filters.onlyEnabled && !mod.enabled) return false
    if (filters.onlyDisabled && mod.enabled) return false
    if (filters.onlyErrors && mod.errors.length === 0) return false
    if (filters.hideErrors && mod.errors.length > 0) return false
    // mods with conflicts, a conflict is when the mod has at least one mod in its conflictsWith array that is also enabled
    // if (filters.onlyConflicts && mod.conflictsWith.length === 0) return false
    if (filters.onlyConflicts && mod.conflictingMods.length === 0) return false

    return true
  })
})

async function handleRefreshMods() {
  if (isRefreshing.value) {
    loggingStore.logDebug("Refresh already in progress, skipping.");
    return;
  }

  isRefreshing.value = true
  await modsStore.discoverMods()
  isRefreshing.value = false
}

function handleUpdateModAuthor(mods: BD2Mod[]) {
  loggingStore.logDebug("Changing author for mods:", mods.map(m => m.name), "Current authors:", mods.map(m => m.author));
  updateAuthorModal.value?.open({
    mods: mods.map(m => ({ name: m.name, author: m.author || '' })),
    onSave: (newAuthor: string) => {
      loggingStore.logDebug(`Changing author for ${mods.length} mod(s) to "${newAuthor}"`);
      modsStore.setModAuthor(mods.map(m => m.name), newAuthor);
    }
  });
}

function handleRenameMod(mod: BD2Mod) {
  loggingStore.logDebug("Renaming mod:", mod.name);
  renameModModal.value?.open({
    modName: mod.name,
    onSave: (newName: string) => {
      if (newName === mod.name) {
        return;
      }
      loggingStore.logDebug(`Change name  of mod "${mod.name}" to "${newName}" ${typeof newName}`);
      renameMod(mod, newName);
    }
  });
}

function handleShowModConflicts(mod: BD2Mod) {
  // filters.searchQuery = `"${mod.name}", "${mod.conflictsWith.join(', ')}"`;
  // const names = [mod.name, ...mod.conflictsWith]
  // filters.searchQuery = names.map(n => `"${n}"`).join(', ')
  filters.searchQuery = `conflictsWith:"${mod.name}"`;
  // searhc by id?
  // show modal?
}

async function handleOpenModFolder(mod: BD2Mod) {
  loggingStore.logDebug("Opening mod folder:", mod.name);

  const folderExists = await invoke("path_exists", { path: mod.path }).catch((error) => {
    loggingStore.logError(`An error occurred while checking if mod folder exists for "${mod.name}":`, error);
    return false;
  });

  if (!folderExists) {
    notificationStore.add({
      type: 'error',
      closable: true,
      title: t('modsTab.errors.modFolderNotFound.title'),
      message: t('modsTab.errors.modFolderNotFound.message', { modName: mod.name }),
      duration: 5000
    })
    return
  }

  // check if is a folder
  const isFolder = await invoke("is_folder", { path: mod.path }).catch((error) => {
    loggingStore.logError(`An error occurred while checking if mod path is a folder for "${mod.name}":`, error);
    return false;
  });

  if (!isFolder) {
    notificationStore.add({
      type: 'error',
      closable: true,
      title: t('modsTab.errors.modNotDirectory.title'),
      message: t('modsTab.errors.modNotDirectory.message', { modName: mod.name }),
      duration: 5000
    })
    return
  }

  await openPath(mod.path)
}

async function handleOpenStagingModsFolder() {
  let stagingDir = settingsStore.settings.stagingDirectory

  loggingStore.logDebug("Opening staging mods folder: ", stagingDir);

  if (!stagingDir) {
    loggingStore.logError("Staging directory is not set.");

    return notificationStore.add({
      type: "error",
      closable: true,
      title: t('modsTab.errors.stagingDirectoryNotSet.title'),
      message: t('modsTab.errors.stagingDirectoryNotSet.message'),
      duration: 5000
    });
  }

  const directoryExists = await invoke("path_exists", { path: stagingDir }).catch((error) => {
    loggingStore.logError(`An error occurred while checking if staging directory exists:`, error);
    return false;
  });

  if (!directoryExists) {
    return notificationStore.add({
      type: 'error',
      closable: true,
      title: t('modsTab.errors.stagingDirectoryNotFound.title'),
      message: t('modsTab.errors.stagingDirectoryNotFound.message', { stagingDir }),
      duration: 5000
    })
  }

  await openPath(stagingDir);
}

async function openGameFolder() {
  const { gameDirectory } = settingsStore.settings

  loggingStore.logDebug("Opening game folder:", gameDirectory);

  if (!gameDirectory) {
    loggingStore.logError("Game directory is not set.");

    notificationStore.add({
      type: 'error',
      closable: true,
      title: t('modsTab.errors.gameDirectoryNotSet.title'),
      message: t('modsTab.errors.gameDirectoryNotSet.message'),
      duration: 5000
    })
    return
  }

  const directoryExists = await invoke<boolean>("path_exists", { path: gameDirectory }).catch((error) => {
    loggingStore.logError("An error occurred while checking if game directory exists:", error);
    return false;
  });

  if (!directoryExists) {
    notificationStore.add({
      type: 'error',
      closable: true,
      title: t('modsTab.errors.gameDirectoryNotFound.title'),
      message: t('modsTab.errors.gameDirectoryNotFound.message', { gameDirectory }),
      duration: 5000
    })
    return
  }

  const isFolder = await invoke<boolean>("is_folder", { path: gameDirectory }).catch((error) => {
    loggingStore.logError("An error occurred while checking if game path is a folder:", error);
    return false;
  });

  if (!isFolder) {
    notificationStore.add({
      type: 'error',
      closable: true,
      title: t('modsTab.errors.gameDirectoryNotDirectory.title'),
      message: t('modsTab.errors.gameDirectoryNotDirectory.message', { gameDirectory }),
      duration: 5000
    })
    return
  }

  await openPath(gameDirectory)
}

async function openGameModsFolder() {
  const { gameDirectory } = settingsStore.settings

  if (!gameDirectory) {
    loggingStore.logError("Game directory is not set.");

    notificationStore.add({
      type: 'error',
      closable: true,
      title: t('modsTab.errors.gameDirectoryNotSet.title'),
      message: t('modsTab.errors.gameDirectoryNotSet.message'),
      duration: 5000
    })
    return
  }

  const gameModsDirectory = await join(gameDirectory, 'BepInEx', 'plugins', 'BrownDustX', 'mods')

  loggingStore.logDebug("Opening game mods folder:", gameModsDirectory);

  const directoryExists = await invoke<boolean>("path_exists", { path: gameModsDirectory }).catch((error) => {
    loggingStore.logError("An error occurred while checking if game mods directory exists:", error);
    return false;
  });

  if (!directoryExists) {
    notificationStore.add({
      type: 'error',
      closable: true,
      title: t('modsTab.errors.gameModsDirectoryNotFound.title'),
      message: t('modsTab.errors.gameModsDirectoryNotFound.message', { gameModsDirectory }),
      duration: 5000
    })
    return
  }

  const isFolder = await invoke<boolean>("is_folder", { path: gameModsDirectory }).catch((error) => {
    loggingStore.logError("An error occurred while checking if game mods path is a folder:", error);
    return false;
  });

  if (!isFolder) {
    notificationStore.add({
      type: 'error',
      closable: true,
      title: t('modsTab.errors.gameModsDirectoryNotDirectory.title'),
      message: t('modsTab.errors.gameModsDirectoryNotDirectory.message', { gameModsDirectory }),
      duration: 5000
    })
    return
  }

  await openPath(gameModsDirectory)
}

async function setupEventListeners() {
  // remove existing listeners if any
  unlistenFns.forEach((unlisten) => unlisten())
  unlistenFns = []

  console.log("Setting up event listeners for ModsTab");

  const unlistenDragDrop = await listen("tauri://drag-drop", async (event: any) => {
    const paths = event.payload?.paths as string[]

    for (const path of paths) {
      await installMod(path)
    }
  })

  unlistenFns = [unlistenDragDrop]
}

onActivated(async () => {
  loggingStore.logDebug("Mounting ModsTab, setting up event listeners");
  await setupEventListeners()
})

onDeactivated(() => {
  loggingStore.logDebug("Unmounting ModsTab, removing event listeners");
  unlistenFns.forEach((unlisten) => unlisten())
  unlistenFns = []
})

watchDebounced(
  () => filters.searchQuery,
  (newValue) => {
    debouncedSearchQuery.value = newValue;
  },
  { debounce: 50 }
);


// [TODO] should these watchers be in here?
watch(() => settingsStore.settings.stagingDirectory, (newDir, oldDir) => {
  loggingStore.logDebug("Staging directory changed from", oldDir, "to", newDir);

  if (oldDir === null || oldDir === undefined) {
    loggingStore.logDebug("Skipping initial settings load");
    return;
  }

  if (newDir && newDir !== oldDir) {
    loggingStore.logDebug("Staging directory changed, discovering mods...");
    modsStore.discoverMods();
  }
});

watch(() => settingsStore.settings.searchModsRecursively, (newValue, oldValue) => {
  if (oldValue === null || oldValue === undefined) {
    loggingStore.logDebug("Skipping initial searchModsRecursively load");
    return;
  }

  if (newValue !== oldValue) {
    loggingStore.logDebug("Search recursively changed:", oldValue, "→", newValue);
    modsStore.discoverMods();
  }
});


const addModMenuItems = computed(() => [
  { label: t('modsTab.actions.installFromZip'), clicked: installFromZip },
  { label: t('modsTab.actions.installFromFolder'), clicked: installFromFolder }
])

const AddModMenu = defineComponent({
  setup() {
    return () =>
      h(Popover, {}, {
        trigger: ({ toggle }: any) =>
          h(Button, {
            label: t('modsTab.actions.addMod'),
            icon: FolderPlus,
            variant: 'text',
            onClick: toggle
          }),
        default: ({ close }: any) =>
          h('ul', { class: 'bg-surface-popover border-border-default border rounded-md' }, addModMenuItems.value.map(item =>
            h('li', { key: item.label },
              h('button', {
                class: 'w-full cursor-pointer text-left px-4 py-2 hover:bg-state-hover text-sm font-medium',
                onClick: () => { item.clicked(); close() }
              }, item.label)
            )
          ))
      })
  }
})

useHeader({
  title: t('modsTab.title'),
  subtitle: computed(() =>
    t('modsTab.subtitle', {
      enabledModsCount: enabledModsCount.value,
      totalModsCount: totalModsCount.value
    })
  ),
  buttons: [
    {
      icon: RefreshCcw,
      label: t('common.actions.refreshMods'),
      action: async () => {
        await handleRefreshMods()
      }
    },
    { render: () => h(AddModMenu) }
  ]
})
</script>
<template>
  <div class="flex flex-col h-full gap-0 select-none p-4 py-0 pb-2">
    <UpdateAuthorModal ref="updateAuthorModal" />
    <RenameModModal ref="renameModModal" />

    <div class="shrink-0 mb-2">
      <ModsHeader v-model:filters="filters" />
    </div>

    <div class="flex-1 overflow-hidden min-h-0 mb-2">
      <Modlist :mods="filteredMods" :isSyncing="modsStore.isSyncing" @refresh-mods="handleRefreshMods" @enable-mods="enableMods"
        @disable-mods="disableMods" @change-mod-author="handleUpdateModAuthor" @delete-mods="deleteMods"
        @open-mod-folder="handleOpenModFolder" @preview-mod="previewMod" @rename-mod="handleRenameMod" @show-mod-conflicts="handleShowModConflicts" />
    </div>

    <div class="flex justify-between items-center shrink-0">
      <div class="flex flex-col">
        <span class="font-semibold">
          <template v-if="gameStore.browndustxVersion?.status == 'Installed'">
            {{ $t("modsTab.browndustx.status.installed", { version: gameStore.browndustxVersion.version }) }}
          </template>
          <template v-else-if="gameStore.browndustxVersion?.status == 'InstalledButOutdated'">
            {{ $t("modsTab.browndustx.status.installedButOutdated", { version: gameStore.browndustxVersion.version }) }}
          </template>
          <template v-else-if="!gameStore.browndustxVersion">
            {{ $t("modsTab.browndustx.status.gameNotFound") }}
          </template>
          <template v-else>
            {{ $t("modsTab.browndustx.status.notInstalled") }}
          </template>
        </span>
        <RouterLink to="bdx" class="text-text-secondary text-xs hover:underline">
          {{ $t("modsTab.browndustx.navigation") }}
        </RouterLink>
      </div>

      <div class="flex gap-2 text-primary">
        <MultiButton :label="$t('modsTab.actions.openModsFolder')" :icon="Folder" @click="handleOpenStagingModsFolder"
          :actions="[
            { label: t('modsTab.actions.openGameFolder'), clicked: openGameFolder },
            { label: t('modsTab.actions.openGameModsFolder'), clicked: openGameModsFolder }
          ]" />
        <Button variant="default" :disabled="modsStore.isSyncing" :label="$t('modsTab.actions.unsyncMods')" :icon="FolderMinus" @click="unsyncMods" />
        <Button :variant="isSyncNeeded ? 'primary' : 'default'" :disabled="modsStore.isSyncing" :label="$t('modsTab.actions.syncMods')" :icon="FolderSync" @click="syncMods" :class="{'animate-pulse hover:animate-none': isSyncNeeded}" />
      </div>
    </div>
  </div>
</template>
<style scoped></style>
