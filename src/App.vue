<script setup lang="ts">
import { watch, onMounted, onUnmounted } from "vue"
import { storeToRefs } from "pinia"
import { useI18n } from "vue-i18n"

import { getCurrentWindow } from "@tauri-apps/api/window"

import { useSettingsStore } from "./stores/settings"
import { useModsStore } from "./stores/mods"

import { useAppInitializer } from "./composables/useAppInit"
import { provideHeader } from "./composables/useHeader"
import { useDev } from "./composables/useDev.ts"
import { useConfirm } from "./plugins/ConfirmService"

import Titlebar from "./components/Titlebar.vue"
import Header from "./components/Header.vue"
import Sidebar from "./components/sidebar/Sidebar.vue"
import WelcomeModal from "./components/modals/WelcomeModal.vue"
import UpdateAvailableModal from "./components/modals/UpdateAvailableModal.vue"
import NotificationContainer from "./components/notification/NotificationContainer.vue"
import ModsDeleteFailedModal from "./components/modals/ModsDeleteFailedModal.vue"
import ConfirmationDialog from "./components/common/ConfirmationDialog.vue"
import SyncModal from "./components/modals/SyncModal.vue"
import LogsModal from "./components/modals/LogsModal.vue"

const { t, locale } = useI18n()

const settingsStore = useSettingsStore()
const { settings } = storeToRefs(settingsStore)

const { initialize } = useAppInitializer()

const confirm = useConfirm()
const modsStore = useModsStore()

const { isDev } = useDev()

let unlistenClose: (() => void) | null = null

provideHeader()

watch(
  () => settings.value.theme,
  (newTheme) => {
    const theme = newTheme ?? "dark-1"
    const validTheme = settingsStore.availableThemes.map(t => t.value).includes(theme)
    document.documentElement.setAttribute("data-theme", validTheme ? theme : "dark-1")
  },
  { immediate: true }
)

watch(
  () => settings.value.language,
  (newLanguage) => (locale.value = newLanguage || "en_US"),
  { immediate: true }
)

onMounted(async () => {
  if (!isDev.value) {
    document.addEventListener("contextmenu", (event) => event.preventDefault())
  }

  const currentWindow = getCurrentWindow()

  unlistenClose = await currentWindow.listen("tauri://close-requested", async () => {
    let isSyncNeeded = false
    try {
      isSyncNeeded = await modsStore.isSyncNeeded()
    } catch (error) {
      console.error("Error checking sync status:", error)
      currentWindow.destroy()
      return
    }

    if (!isSyncNeeded) {
      currentWindow.destroy()
      return
    }

    const result = await confirm.confirm({
      title: t('app.confirmations.exit.title'),
      message: t('app.confirmations.exit.message'),
      acceptButton: { label: t('app.confirmations.exit.actions.exit') },
      rejectButton: { label: t('common.actions.cancel') },
    })

    if (result.confirmed) currentWindow.destroy()
  })

  await initialize()
})

onUnmounted(() => {
  unlistenClose?.()
})
</script>

<template>
  <main  class="w-full h-full overflow-hidden text-sm select-none flex flex-col bg-surface-app text-text-primary">
    <div class="absolute bg-[image:var(--bg-image-app)] inset-0 bg-cover bg-center opacity-25 pointer-events-none">
    </div>
    <Titlebar />

    <div class="flex-1 flex overflow-hidden min-h-0">
      <Sidebar />

      <div class="flex-1 flex flex-col overflow-hidden min-h-0">
        <Header />
        <div class="flex-1 overflow-hidden min-h-0">
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <keep-alive :include="['ModsTab', 'CharactersTab']">
                <component :is="Component" class="h-full" />
              </keep-alive>
            </transition>
          </router-view>
        </div>
      </div>
    </div>

    <ConfirmationDialog />
    <!-- <NotificationContainer position="top-left" />
    <NotificationContainer position="top-right" />
    <NotificationContainer position="top-center"/>
    <NotificationContainer position="bottom-left" />
    <NotificationContainer position="bottom-right" /> -->
    <!-- <NotificationContainer position="top-right" /> -->
    <NotificationContainer position="bottom-center" />

    <!-- global modals -->
    <WelcomeModal />
    <UpdateAvailableModal />
    <SyncModal />
    <LogsModal />
    <ModsDeleteFailedModal />

  </main>
</template>
<style></style>
