<script
  setup
  lang="ts"
>
import { computed, onMounted, ref, watch } from 'vue'
import { TabPanel } from '@headlessui/vue'
import { useI18n } from 'vue-i18n'

import { invoke } from '@tauri-apps/api/core'

import { useSettingsStore } from '../../../stores/settings'
import { useNotificationStore } from '../../../stores/notification.ts'
import { AppUpdateAvailable, UpdateStatus, useUpdater } from '../../../composables/useUpdater.ts'

import { version } from '../../../../package.json'
import { usePortable } from '../../../composables/usePortable'
import { globalModals } from '../../../composables/useGlobalModals'
import { getErrorMessage } from '../../../utils/errors'

import Checkbox from '../../../components/common/Checkbox.vue'
import Button from '../../../components/common/Button.vue'
import Select from '../../../components/common/Select.vue'


const notificationStore = useNotificationStore()
const settingsStore = useSettingsStore()
const { t } = useI18n()

const {
  appUpdate,
  modPreviewUpdate,
  checkForAppUpdate,
  downloadAppUpdate,
  installAppUpdate,
  checkForModPreviewUpdate,
  downloadAndInstallModPreview,
} = useUpdater()

const shouldDisable = computed(() => {
  return appUpdate.value?.status === UpdateStatus.CheckingForUpdates
    || appUpdate.value?.status === UpdateStatus.Downloading
    || appUpdate.value?.status === UpdateStatus.Downloaded
    || appUpdate.value?.status === UpdateStatus.Installing
})

const settings = computed(() => settingsStore.settings)
const modPreviewVersion = ref<string | null>(null)

const { isPortable } = usePortable()
const appUpdateError = ref<string | null>(null)
const appProgress = computed(() => appUpdate.value?.status === UpdateStatus.Downloading && appUpdate.value.progress.total
  ? Math.min(100, Math.round(appUpdate.value.progress.downloaded / appUpdate.value.progress.total * 100))
  : null)
const previewProgress = computed(() => modPreviewUpdate.value?.status === UpdateStatus.Downloading && modPreviewUpdate.value.progress.total
  ? Math.min(100, Math.round(modPreviewUpdate.value.progress.downloaded / modPreviewUpdate.value.progress.total * 100))
  : null)

const appStatus = computed(() => {
  if (appUpdateError.value) return appUpdateError.value
  switch (appUpdate.value?.status) {
    case UpdateStatus.CheckingForUpdates: return t('settingsTab.updates.status.checking')
    case UpdateStatus.UpdateAvailable: return t('settingsTab.updates.sections.updates.status.updateAvailable', { version: appUpdate.value.update.versionAvailable })
    case UpdateStatus.Downloading: return appProgress.value === null ? t('settingsTab.updates.status.downloading') : t('settingsTab.updates.status.downloadProgress', { percent: appProgress.value })
    case UpdateStatus.Downloaded:
    case UpdateStatus.Installing: return t('settingsTab.updates.status.installing')
    case UpdateStatus.Failed: return appUpdate.value.error
    default: return t('settingsTab.updates.status.upToDate')
  }
})
const previewStatus = computed(() => {
  switch (modPreviewUpdate.value?.status) {
    case UpdateStatus.CheckingForUpdates: return t('settingsTab.updates.status.checking')
    case UpdateStatus.UpdateAvailable: return t('settingsTab.updates.sections.updates.status.updateAvailable', { version: modPreviewUpdate.value.update.versionAvailable })
    case UpdateStatus.Downloading: return previewProgress.value === null ? t('settingsTab.updates.status.downloading') : t('settingsTab.updates.status.downloadProgress', { percent: previewProgress.value })
    case UpdateStatus.Downloaded:
    case UpdateStatus.Updating: return t('settingsTab.updates.status.installing')
    case UpdateStatus.Failed: return modPreviewUpdate.value.error
    default: return t('settingsTab.updates.status.upToDate')
  }
})

async function updateApp() {
  appUpdateError.value = null
  if (isPortable.value) {
    if (appUpdate.value?.status === UpdateStatus.UpdateAvailable) {
      globalModals.updateAvailable.showModal(appUpdate.value.update as AppUpdateAvailable)
    }
    return
  }
  let installing = appUpdate.value?.status === UpdateStatus.Downloaded
  try {
    if (!installing) await downloadAppUpdate()
    installing = true
    await installAppUpdate()
  } catch (error) {
    appUpdateError.value = getErrorMessage(t, error)
    notificationStore.add({
      type: 'error',
      title: t(installing ? 'app.notifications.appUpdate.installFailed.title' : 'app.notifications.appUpdate.downloadFailed.title'),
      message: appUpdateError.value,
      duration: 5000,
    })
  }
}

watch(appUpdate, () => { appUpdateError.value = null }, { flush: 'sync' })

onMounted(async () => {
  modPreviewVersion.value = await invoke<string | null>('get_mod_preview_version')
})

async function onCheckForAppUpdates(value: boolean) {
  await settingsStore.saveSettings({ checkForAppUpdates: value })

  if (value) {
    checkForAppUpdate()
  }
}

function onAutoUpdateModPreview(value: boolean) {
  settingsStore.saveSettings({ autoUpdateModPreview: value })
}

async function onUpdateChannelChanged(value: string) {
  await settingsStore.saveSettings({ updateChannel: value })

  checkForAppUpdate()
}

async function checkModPreviewUpdates() {
  await checkForModPreviewUpdate()

  if (modPreviewUpdate.value === null) {
    notificationStore.add({
      type: "info",
      title: t("app.notifications.modPreviewUpdate.noUpdateAvailable.title")
    })
  }
}

async function updateModPreview() {
  await downloadAndInstallModPreview()
}

watch(modPreviewUpdate, (update) => {
  if (update?.status === UpdateStatus.Updated) {
    modPreviewVersion.value = update.update.versionAvailable
  }
})
</script>

<template>
  <TabPanel>
    <div class="flex flex-col gap-7">
      <section>
        <div class="-mx-2 grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 rounded-md px-2 pt-0 pb-2">
          <div class="min-w-0">
            <h2 class="flex items-baseline gap-2 text-[15px] font-semibold text-text-primary">
              BD2ModManager
              <span class="text-xs font-normal text-text-secondary">v{{ version }}</span>
            </h2>
            <p class="mt-1 text-xs wrap-break-word"
              :class="appUpdateError || appUpdate?.status === UpdateStatus.Failed ? 'text-error' : appUpdate?.status === UpdateStatus.UpdateAvailable ? 'text-accent' : 'text-text-secondary'">
              {{ appStatus }}</p>
            <div v-if="appUpdate?.status === UpdateStatus.Downloading && appProgress !== null"
              class="mt-2 h-1.5 rounded-full max-w-65 bg-border-default" role="progressbar" :aria-label="appStatus"
              :aria-valuenow="appProgress" aria-valuemin="0" aria-valuemax="100">
              <div class="h-full bg-accent rounded-full" :style="{ width: `${appProgress}%` }" />
            </div>
          </div>
          <Button v-if="appUpdateError" variant="default" :label="$t('app.notifications.modPreviewUpdate.retry')"
            @click="updateApp" />
          <Button v-else-if="appUpdate?.status === UpdateStatus.UpdateAvailable" variant="primary"
            :label="$t('settingsTab.updates.downloadAndInstall')" @click="updateApp" />
          <Button v-else variant="default" :disabled="shouldDisable"
            :label="appUpdate?.status === UpdateStatus.CheckingForUpdates ? $t('settingsTab.updates.sections.updates.actions.checkingForUpdates') : appUpdate?.status === UpdateStatus.Downloading ? $t('settingsTab.updates.status.downloading') : appUpdate?.status === UpdateStatus.Downloaded || appUpdate?.status === UpdateStatus.Installing ? $t('settingsTab.updates.status.installing') : appUpdate?.status === UpdateStatus.Failed ? $t('app.notifications.modPreviewUpdate.retry') : $t('settingsTab.updates.sections.updates.actions.checkForUpdates')"
            @click="checkForAppUpdate" />
        </div>
        <div class="-mx-2 rounded-md p-2">
          <Checkbox inputId="checkForAppUpdates" :model-value="settings.checkForAppUpdates"
            @update:model-value="onCheckForAppUpdates"
            :label="$t('settingsTab.updates.sections.updates.autoCheckForUpdates.label')"
            :description="$t('settingsTab.updates.sections.updates.autoCheckForUpdates.description')" />
        </div>
        <div class="-mx-2 grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 rounded-md p-2">
          <label id="update-channel-label" class="min-w-0 text-sm text-text-primary">
            {{ $t('settingsTab.updates.sections.updates.updateChannel.label') }}
            <p class="mt-1 text-xs text-text-secondary">{{
              $t(`settingsTab.updates.sections.updates.updateChannel.options.${settings.updateChannel}.description`) }}
            </p>
          </label>
          <Select class="update-channel w-36" aria-labelledby="update-channel-label"
            :model-value="settings.updateChannel" :disabled="shouldDisable" :options="[
              { label: $t('settingsTab.updates.sections.updates.updateChannel.options.stable.label'), value: 'stable' },
              { label: $t('settingsTab.updates.sections.updates.updateChannel.options.beta.label'), value: 'beta' }
            ]" :placeholder="$t('settingsTab.updates.sections.updates.updateChannel.placeholder')" option-label="label"
            option-value="value" @update:model-value="onUpdateChannelChanged" />
        </div>
      </section>

      <section>
        <div class="-mx-2 grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 rounded-md px-2 pt-0 pb-2">
          <div class="min-w-0">
            <h2 class="flex items-baseline gap-2 text-[15px] font-semibold text-text-primary">
              BD2ModPreview
              <span class="text-xs font-normal text-text-secondary">{{ modPreviewVersion ? `v${modPreviewVersion}` : $t('settingsTab.updates.unknown') }}</span>
            </h2>
            <p class="mt-1 text-xs wrap-break-word"
              :class="modPreviewUpdate?.status === UpdateStatus.Failed ? 'text-error' : modPreviewUpdate?.status === UpdateStatus.UpdateAvailable ? 'text-accent' : 'text-text-secondary'">
              {{ previewStatus }}</p>
            <div v-if="modPreviewUpdate?.status === UpdateStatus.Downloading && previewProgress !== null"
              class="mt-2 h-1.5 rounded-full max-w-65 bg-border-default" role="progressbar" :aria-label="previewStatus"
              :aria-valuenow="previewProgress" aria-valuemin="0" aria-valuemax="100">
              <div class="h-full bg-accent rounded-full" :style="{ width: `${previewProgress}%` }" />
            </div>
          </div>
          <Button v-if="modPreviewUpdate?.status === UpdateStatus.UpdateAvailable" variant="primary"
            :label="$t('settingsTab.updates.sections.updates.actions.update')" @click="updateModPreview" />
          <Button v-else-if="modPreviewUpdate?.status === UpdateStatus.Failed" variant="default"
            :label="$t('app.notifications.modPreviewUpdate.retry')" @click="checkForModPreviewUpdate(true)" />
          <Button v-else variant="default"
            :label="modPreviewUpdate?.status === UpdateStatus.CheckingForUpdates ? $t('settingsTab.updates.sections.updates.actions.checkingForUpdates') : $t('settingsTab.updates.sections.updates.actions.checkForUpdates')"
            :disabled="modPreviewUpdate?.status === UpdateStatus.CheckingForUpdates || modPreviewUpdate?.status === UpdateStatus.Downloading || modPreviewUpdate?.status === UpdateStatus.Updating"
            @click="checkModPreviewUpdates" />
        </div>
        <div class="-mx-2 rounded-md p-2">
          <Checkbox inputId="autoUpdateModPreview" :model-value="settings.autoUpdateModPreview"
            @update:model-value="onAutoUpdateModPreview"
            :label="$t('settingsTab.updates.sections.updates.autoUpdateModPreview.label')"
            :description="$t('settingsTab.updates.sections.updates.autoUpdateModPreview.description')" />
        </div>
      </section>
    </div>
  </TabPanel>
</template>

<style scoped>
@reference '../../../styles/main.css';

.update-channel :deep(button) {
  @apply border-0 bg-surface-panel text-text-primary shadow-none
}

.update-channel :deep([role='listbox']) {
  @apply border-0 shadow-none;
}
</style>