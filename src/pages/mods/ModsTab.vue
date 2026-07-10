<script setup lang="ts">
import { Folder, FolderMinus, FolderPlus, FolderSync, RefreshCcw } from "lucide-vue-next";

import { computed, defineComponent, h, onActivated, onDeactivated, onMounted, reactive, ref, useTemplateRef, watch } from "vue";
import { useDebounceFn, useLocalStorage, watchDebounced } from "@vueuse/core";
import { useNotificationStore } from '../../stores/notification';;
import { useI18n } from "vue-i18n";

import { listen } from "@tauri-apps/api/event";
import { openPath } from "@tauri-apps/plugin-opener";

import { useConfirm } from "../../plugins/ConfirmService";

import { BD2Mod, useModsStore } from "../../stores/mods";
import { useSettingsStore } from "../../stores/settings";
import { useLoggingStore } from "../../stores/logging";

import { useHeader } from "../../composables/useHeader";

import UpdateAuthorModal from "./modals/UpdateAuthorModal.vue";
import RenameModModal from "./modals/RenameModModal.vue";
import ModsHeader from "./ModsHeader.vue";
import Modlist from "./Modlist.vue";
import Button from "../../components/common/Button.vue";
import { getErrorMessage } from "../../utils/errors";
import { invoke } from "@tauri-apps/api/core";
import { useModInstall } from "../../composables/useModInstall";
import MultiButton from "../../components/common/MultiButton.vue";
import Popover from "../../components/common/Popover.vue";


let unlistenFns: Array<() => void> = []

const updateAuthorModal = useTemplateRef("updateAuthorModal")
const renameModModal = useTemplateRef("renameModModal")

const loggingStore = useLoggingStore()

const notificationStore = useNotificationStore()
const confirm = useConfirm()

const { t } = useI18n();
const modsStore = useModsStore();
const settingsStore = useSettingsStore();

const isRefreshing = ref(false);
const isSyncing = ref(false);
const isUnsyncing = ref(false);

const bdxVersion = ref<{
  status: "Installed" | "InstalledButOutdated" | "NotInstalled" | null, // null = game path not set
  version: string
} | null>(null);

const debouncedSearchQuery = ref('');
const skipSyncConfirmation = useLocalStorage('skipSyncModsConfirmation', false)
const skipUnsyncConfirmation = useLocalStorage('skipUnsyncModsConfirmation', false)

const debouncedSync = useDebounceFn(async () => {
  if (!settingsStore.settings.autoSyncMods) return;
  if (isSyncing.value) {
    loggingStore.logDebug("Sync in progress, skipping auto-sync.");
    return;
  }

  isSyncing.value = true;
  try {
    await modsStore.syncMods();
  } catch (error) {
    let errorMessage = getErrorMessage(t, error);
    notificationStore.add({
      closable: true,
      title: t('modsTab.errors.syncFailed.title'),
      message: errorMessage,
      duration: 5000,
      severity: 'error'
    });
  } finally {
    isSyncing.value = false;
  }
}, 1500);

let filters = reactive({
  searchQuery: '',
  modTypes: [] as ("Standing" | "Cutscene" | "Scene" | "NPC" | "Dating" | "Minigame")[],
  onlyEnabled: false,
  onlyDisabled: false,
  onlyConflicts: false,
  onlyErrors: false,
  onlyOneModType: false,
});
const totalModsCount = computed(() => modsStore.mods.length)
const enabledModsCount = computed(() => modsStore.mods.filter(mod => mod.enabled && !mod.errors.length).length)

const filteredMods = computed(() => {
  return modsStore.mods.filter((mod) => {
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
          (mod.character &&
            `${mod.character.character.toLowerCase()} - ${mod.character.costume.toLowerCase()}`.includes(value))
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
    // mods with conflicts, a conflict is when the mod has at least one mod in its conflictsWith array that is also enabled
    // if (filters.onlyConflicts && mod.conflictsWith.length === 0) return false
    if (filters.onlyConflicts && mod.conflictingMods.length === 0) return false

    return true
  })
})

function handleEnableMods(mods: BD2Mod[]) {
  loggingStore.logDebug("Enabling mods:", JSON.stringify(mods.map(m => m.name)));
  modsStore.enableMods(mods.map(m => m.name))
    .then(() => debouncedSync())
    .catch((error) => loggingStore.logError("Error enabling mods:", error))
}

function handleDisableMods(mods: BD2Mod[]) {
  loggingStore.logDebug("Disabling mods:", JSON.stringify(mods.map(m => m.name)));
  modsStore.disableMods(mods.map(m => m.name))
    .then(() => debouncedSync())
    .catch((error) => loggingStore.logError("Error disabling mods:", error))
}

function handlePreviewMod(mod: BD2Mod) {
  loggingStore.logDebug("Previewing mod:", mod.name);

  if (mod.errors.length > 0) {
    notificationStore.add({
      severity: "error",
      closable: true,
      title: t("modsTab.errors.modPreview.title"),
      message: t("modsTab.errors.modPreview.modContainErrors", { modName: mod.name }),
      duration: 3000
    })
    return
  }

  modsStore.previewMod(mod.name).then(() => {
    loggingStore.logDebug("Mod previewed successfully:", mod.name);
  }).catch((error) => {
    // errors that can happen: just some errors like no permission to open the file, or the file doesn't exist anymore, or the file is not a valid mod file
    // no custom errors here
    let errorMsg = getErrorMessage(t, error);
    notificationStore.add({
      severity: "error",
      closable: true,
      title: t("modsTab.errors.modPreview.title"),
      message: errorMsg,
      duration: 5000
    })

    loggingStore.logError("Error previewing mod:", error);
  })
}

async function handleOpenModFolder(mod: BD2Mod) {
  loggingStore.logDebug("Opening mod folder:", mod.name);

  // [TODO] adds checks if folder exists
  const folderExists = await invoke("path_exists", { path: mod.path }).catch((error) => {
    loggingStore.logError(`An error occurred while checking if mod folder exists for "${mod.name}":`, error);
    return false;
  });

  if (!folderExists) {
    notificationStore.add({
      severity: 'error',
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
      severity: 'error',
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
      severity: "error",
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
      severity: 'error',
      closable: true,
      title: t('modsTab.errors.stagingDirectoryNotFound.title'),
      message: t('modsTab.errors.stagingDirectoryNotFound.message', { stagingDir }),
      duration: 5000
    })
  }

  await openPath(stagingDir);
}

async function handleSyncMods() {
  try {
    loggingStore.logDebug(`Syncing mods [confirmation skipped: ${skipSyncConfirmation.value}]`);

    const hasConflicts = modsStore.mods.some(mod => mod.conflictingMods.length > 0)

    if (hasConflicts) {
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

    if (!skipSyncConfirmation.value) {
      const { confirmed, rememberChoice } = await confirm.confirm({
        title: t('modsTab.confirmations.syncMods.title'),
        message: t('modsTab.confirmations.syncMods.message'),
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

    isSyncing.value = true

    // [TODO] syncmods return error
    let result = await modsStore.syncMods().then((res) => {
      loggingStore.logDebug("Mods sync result:", res);

      return res;
    }).catch((error) => {
      loggingStore.logError("Error during mods sync:", error);
      throw error;
    });

    loggingStore.logDebug(`Command mods sync called succesfully: ${result}.`);

    notificationStore.add({
      closable: true,
      title: t('modsTab.notifications.syncSuccess.title'),
      message: t('modsTab.notifications.syncSuccess.description'),
      duration: 5000,
      severity: 'success'
    })
    // if (result) {
    // }
  } catch (error: any) {
    loggingStore.logError("Error syncing mods:", JSON.stringify(error));

    console.log(typeof error, error instanceof Error, error.message);

    let errorMessage = getErrorMessage(t, error)

    notificationStore.add({
      closable: true,
      title: t('modsTab.errors.\.title'),
      message: errorMessage,
      duration: 5000,
      severity: 'error'
    });
  } finally {
    isSyncing.value = false
  }
}

async function handleUnsyncMods() {
  try {
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

    isUnsyncing.value = true

    const result = await modsStore.unsyncMods();

    isUnsyncing.value = false

    loggingStore.logDebug(`Command mods unsync called succesfully: ${result}.`);

    notificationStore.add({
      closable: true,
      title: t('modsTab.notifications.unsyncSuccess.title'),
      message: t('modsTab.notifications.unsyncSuccess.description'),
      duration: 3000,
      severity: 'success'
    });
  } catch (error: any) {
    loggingStore.logError("Error unsyncing mods:", error);

    let errorMessage = getErrorMessage(t, error)

    notificationStore.add({
      closable: true,
      title: t('errors.unsyncFailed'),
      message: errorMessage,
      duration: 5000,
      severity: 'error'
    });

    isUnsyncing.value = false
  }
}

function handleChangeModAuthor(mods: BD2Mod[]) {
  loggingStore.logDebug("Changing author for mods:", mods.map(m => m.name), "Current authors:", mods.map(m => m.author));
  updateAuthorModal.value?.open({
    mods: mods.map(m => ({ name: m.name, author: m.author || '' })),
    onSave: (newAuthor: string) => {
      loggingStore.logDebug(`Changing author for ${mods.length} mod(s) to "${newAuthor}"`);
      modsStore.setModAuthor(mods.map(m => m.name), newAuthor);
    }
  });
}

// function handleEditModfile(mod: BD2Mod) {
//   // [TODO]
// }

async function handleDeleteMods(mods: BD2Mod[]) {
  loggingStore.logDebug("Deleting mods:", JSON.stringify(mods.map(m => m.name)));

  if (mods.length === 0) {
    loggingStore.logDebug("No mods selected for deletion, skipping.");
    return;
  }

  const result = await confirm.confirm({
    title: mods.length === 1 ? t('modsTab.confirmations.deleteMod.title') : t('modsTab.confirmations.deleteMod.multipleTitle'),
    message: mods.length === 1 ? t('modsTab.confirmations.deleteMod.message', { modName: mods[0].name }) : t('modsTab.confirmations.deleteMod.multipleMessage', { count: mods.length }),
    acceptButton: {
      label: t('modsTab.confirmations.deleteMod.actions.delete'),
    },
    rejectButton: {
      label: t('common.actions.cancel'),
    },
  })

  if (result.confirmed) {
    modsStore.deleteMods(mods.map(m => m.name));

    debouncedSync()
  }
}

async function handleRefreshMods() {
  if (isRefreshing.value) {
    loggingStore.logDebug("Refresh already in progress, skipping.");
    return;
  }

  isRefreshing.value = true
  await modsStore.discoverMods()
  isRefreshing.value = false
}

async function updateBDXVersion() {
  try {
    const result = await settingsStore.getBrowndustxVersion();

    loggingStore.logDebug("BDX version:", JSON.stringify(result));

    if (result) {
      bdxVersion.value = {
        status: result.status,
        version: result.version
      };
    } else {
      bdxVersion.value = null;
    }

  } catch (error) {
    loggingStore.logError("Error getting BDX version:", error);
  }
}

// "7z" | "tar" | "gz" | "bz2" | "" | "tgz"
const SUPPORTED_FORMATS = [
  "rar",
  "zip",
  "7z"
]

async function setupEventListeners() {
  // remove existing listeners if any
  unlistenFns.forEach((unlisten) => unlisten())
  unlistenFns = []

  console.log("Setting up event listeners for ModsTab");

  const unlistenDragDrop = await listen("tauri://drag-drop", async (event: any) => {
    const paths = event.payload?.paths as string[]

    for (const path of paths) {
      try {
        let modName = null
        // [TODO] more support for others file types, .rar, 7z
        if (SUPPORTED_FORMATS.includes(`.${path.split('.').pop()?.toLowerCase() || ''}`)) {
          modName = await modsStore.installModFromZip(path)
        } else {
          modName = await modsStore.installModFromFolder(path)
        }

        notificationStore.add({
          closable: true,
          title: t('modsTab.notifications.modInstallSuccess.title'),
          message: t('modsTab.notifications.modInstallSuccess.description', { modName }),
          duration: 3000,
          severity: 'success'
        });

      } catch (error: any) {
        let errorMsg = getErrorMessage(t, error)

        notificationStore.add({
          closable: true,
          title: t('errors.modInstallFailed.title'),
          message: errorMsg,
          duration: 5000,
          severity: 'error'
        });
      }
    }
  })

  unlistenFns = [unlistenDragDrop]
}

onMounted(async () => {
  Promise.all([
    updateBDXVersion()
  ])
})

onActivated(async () => {
  loggingStore.logDebug("Mounting ModsTab, setting up event listeners");
  Promise.all([
    setupEventListeners()
  ])
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

watch(() => settingsStore.settings.gameDirectory, (newDir, oldDir) => {
  // if (oldDir === null || oldDir === undefined) {
  //   loggingStore.logDebug("Skipping initial game directory load");
  //   return;
  // }

  // [info] It triggers when the game directory is set from config.json to settings store

  loggingStore.logDebug(`Game directory changed from "${oldDir}" to "${newDir}"`);

  if (newDir && newDir !== oldDir) {
    updateBDXVersion();
  }
});

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

const { installFromZip, installFromFolder } = useModInstall()

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
          h('ul', {class: 'bg-surface-popover border-border-default border rounded-md'}, addModMenuItems.value.map(item =>
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
        await updateBDXVersion()
      }
    },
    { render: () => h(AddModMenu) }
  ]
})

function handleRenameMod(mod: BD2Mod) {
  loggingStore.logDebug("Renaming mod:", mod.name);
  renameModModal.value?.open({
    modName: mod.name,
    onSave: (newName: string) => {
      if (newName === mod.name) {
        return;
      }
      loggingStore.logDebug(`Change name  of mod "${mod.name}" to "${newName}" ${typeof newName}`);
      modsStore.renameMod(mod.name, newName);
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


// [TODO] reactive is sync needed
const isSyncNeeded = ref(0)

async function openGameFolder() {
  let { gameDirectory } = settingsStore.settings

  if (!gameDirectory) return

  await openPath(gameDirectory)
}
async function openGameModsFolder() {
  let { gameDirectory } = settingsStore.settings

  if (!gameDirectory) return

  // [TODO] find a better way to get this path
  await openPath(gameDirectory + '/BepInEx/plugins/BrownDustX/mods')
}
</script>
<template>
  <div class="flex flex-col h-full gap-0 select-none p-4 py-0 pb-2">
    <UpdateAuthorModal ref="updateAuthorModal" />
    <RenameModModal ref="renameModModal" />

    <div class="shrink-0 mb-2">
      <ModsHeader v-model:filters="filters" />
    </div>

    <div class="flex-1 overflow-hidden min-h-0 mb-2">
      <Modlist :mods="filteredMods" @refresh-mods="handleRefreshMods" @enable-mods="handleEnableMods"
        @disable-mods="handleDisableMods" @change-mod-author="handleChangeModAuthor" @delete-mods="handleDeleteMods"
        @open-mod-folder="handleOpenModFolder" @preview-mod="handlePreviewMod" @rename-mod="handleRenameMod"
        @show-mod-conflicts="handleShowModConflicts" />
    </div>

    <div class="flex justify-between items-center shrink-0">
      <div class="flex flex-col">
        <span class="font-semibold">
          <template v-if="bdxVersion?.status == 'Installed'">
            {{ $t("modsTab.browndustx.status.installed", { version: bdxVersion.version }) }}
          </template>
          <template v-else-if="bdxVersion?.status == 'InstalledButOutdated'">
            {{ $t("modsTab.browndustx.status.installedButOutdated", { version: bdxVersion.version }) }}
          </template>
          <template v-else-if="!bdxVersion">
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
        <Button variant="default" :disabled="isSyncing || isUnsyncing" :label="$t('modsTab.actions.unsyncMods')"
          :icon="FolderMinus" @click="handleUnsyncMods" />
        <Button :variant="isSyncNeeded ? 'primary' : 'default'" :disabled="isSyncing || isUnsyncing"
          :label="$t('modsTab.actions.syncMods')" :icon="FolderSync" @click="handleSyncMods" :class="{
            'animate-pulse hover:animate-none': isSyncNeeded
          }" />
      </div>
    </div>
  </div>
</template>
<style scoped></style>