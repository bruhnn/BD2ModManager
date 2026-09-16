<script setup lang="ts">
import { LoaderCircle } from '@lucide/vue'
import { computed, onMounted, ref, watch } from 'vue'
import { TabPanel } from '@headlessui/vue'
import { useI18n } from 'vue-i18n'

import { invoke } from '@tauri-apps/api/core'

import { useSettingsStore } from '../../../stores/settings'
import { useNotificationStore } from '../../../stores/notification.ts'
import { UpdateStatus, useUpdater } from '../../../composables/useUpdater.ts'

import Section from '../Section.vue'

import Checkbox from '../../../components/common/Checkbox.vue'
import Button from '../../../components/common/Button.vue'


const notificationStore = useNotificationStore()
const settingsStore = useSettingsStore()
const { t } = useI18n()

const {
  modPreviewUpdate,
  checkForAppUpdate,
  checkForModPreviewUpdate,
  downloadAndInstallModPreview,
} = useUpdater()

const settings = computed(() => settingsStore.settings)
const modPreviewVersion = ref<string | null>(null)

onMounted(async () => {
  modPreviewVersion.value = await invoke<string | null>('get_mod_preview_version')
})

function onCheckForAppUpdates(value: boolean) {
  settingsStore.saveSettings({ checkForAppUpdates: value })

  if (value) {
    checkForAppUpdate()
  }
}

function onAutoUpdateModPreview(value: boolean) {
  settingsStore.saveSettings({ autoUpdateModPreview: value })
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
    <div class="flex flex-col">
      <Section :title="$t('settingsTab.updates.sections.updates.title')">
        <div class="flex flex-col gap-3 mb-2">
          <Checkbox
            inputId="checkForAppUpdates"
            :model-value="settings.checkForAppUpdates"
            @update:model-value="onCheckForAppUpdates"
            :label="$t('settingsTab.updates.sections.updates.autoCheckForUpdates.label')"
            :description="$t('settingsTab.updates.sections.updates.autoCheckForUpdates.description')"
          />

          <Checkbox
            inputId="autoUpdateModPreview"
            :model-value="settings.autoUpdateModPreview"
            @update:model-value="onAutoUpdateModPreview"
            :label="$t('settingsTab.updates.sections.updates.autoUpdateModPreview.label')"
            :description="$t('settingsTab.updates.sections.updates.autoUpdateModPreview.description')"
          />
        </div>

        <div class="flex items-center justify-between">
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <LoaderCircle v-if="modPreviewUpdate?.status === UpdateStatus.CheckingForUpdates"
                class="size-4 shrink-0 animate-spin text-accent" />
              <div class="font-medium text-text-primary">
                BD2ModPreview
                <span class="font-normal text-text-secondary">
                  {{ modPreviewVersion ? `v${modPreviewVersion}` : 'Unknown' }}
                </span>
              </div>
            </div>
            <div v-if="modPreviewUpdate?.status === UpdateStatus.UpdateAvailable" class="mt-1 text-sm text-accent">
              {{ $t('settingsTab.updates.sections.updates.status.updateAvailable', { version: modPreviewUpdate.update.versionAvailable }) }}
            </div>
            <div v-else-if="modPreviewUpdate?.status === UpdateStatus.Failed" class="mt-1 text-sm text-error">
              {{ modPreviewUpdate.error }}
            </div>
          </div>
          <div class="shrink-0">
            <Button
              v-if="modPreviewUpdate?.status === UpdateStatus.UpdateAvailable"
              :label="$t('settingsTab.updates.sections.updates.actions.update')"
              @click="updateModPreview" />
            <Button
              v-else
              :label="modPreviewUpdate?.status === UpdateStatus.CheckingForUpdates
                ? $t('settingsTab.updates.sections.updates.actions.checkingForUpdates')
                : $t('settingsTab.updates.sections.updates.actions.checkForUpdates')"
              @click="checkModPreviewUpdates"
              :disabled="modPreviewUpdate?.status === UpdateStatus.CheckingForUpdates
                || modPreviewUpdate?.status === UpdateStatus.Downloading
                || modPreviewUpdate?.status === UpdateStatus.Updating" />
          </div>
        </div>
      </Section>
    </div>
  </TabPanel>
</template>
