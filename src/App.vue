<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from "vue"
import { storeToRefs } from "pinia"
import { useI18n } from "vue-i18n"

import { useSettingsStore } from "./stores/settings"
import { provideHeader } from "./composables/useHeader"

import Titlebar from "./components/Titlebar.vue"
import Header from "./components/Header.vue"
import ConfirmationDialog from "./components/common/ConfirmationDialog.vue"
import WelcomeModal from "./components/modals/WelcomeModal.vue"
import { useAppInitializer } from "./composables/useAppInit"
import { useConfirm } from "./plugins/ConfirmService"
import { useModsStore } from "./stores/mods"
import { getCurrentWindow } from "@tauri-apps/api/window"
import Sidebar from "./components/sidebar/Sidebar.vue"
import { useNotificationStore } from './stores/notification';
import UpdateAvailableModal from "./components/modals/UpdateAvailableModal.vue"
import { usePortable } from "./composables/usePortable"
import NotificationContainer from "./components/notification/NotificationContainer.vue"
import SyncModal from "./components/modals/SyncModal.vue"
import LogsModal from "./components/modals/LogsModal.vue"

const { t, locale } = useI18n()

const settingsStore = useSettingsStore()
const { settings } = storeToRefs(settingsStore)

const { initialize } = useAppInitializer()

const confirm = useConfirm()
const modsStore = useModsStore()
const notificationStore = useNotificationStore()

const { isPortable } = usePortable()

let unlistenClose: (() => void) | null = null

provideHeader()

const modalQueue = ref<string[]>([])
const currentModalVisible = ref('')

function openModal(modalName: string) {
  if (!modalQueue.value.includes(modalName)) {
    modalQueue.value.push(modalName)
  }
  if (!currentModalVisible.value) {
    currentModalVisible.value = modalQueue.value[0]
  }
}

function closeModal(modalName: string) {
  const index = modalQueue.value.indexOf(modalName)
  if (index !== -1) modalQueue.value.splice(index, 1)
  currentModalVisible.value = modalQueue.value[0] ?? ''
}

watch(
  () => settings.value.language,
  (newLanguage) => (locale.value = newLanguage || "en_US"),
  { immediate: true }
)

watch(
  () => settings.value.theme,
  (newTheme) => {
    const theme = newTheme ?? "dark-1"
    const validTheme = settingsStore.availableThemes.map(t => t.value).includes(theme)
    document.documentElement.setAttribute("data-theme", validTheme ? theme : "dark-1")
  },
  { immediate: true }
)

watch(() => settingsStore.appUpdateStatus, (newStatus) => {
  const skipVersion = localStorage.getItem('skipUpdateVersion')
  
  // update available will only show on portable
  if (newStatus?.version && newStatus.version !== skipVersion && isPortable.value) {
    openModal('updateAvailableModal')
  }
})
onMounted(async () => {
  if (!import.meta.env.DEV) {
    document.addEventListener("contextmenu", (event) => event.preventDefault())
  }

  const { isFirstLaunch, isBrownDustXOutdated } = await initialize()

  if (isFirstLaunch) {
    openModal('welcomeModal')
  }

  if (isBrownDustXOutdated) {
    notificationStore.add({
      severity: "warn",
      title: t('app.notifications.brownDustXOutdated.title'),
      message: t('app.notifications.brownDustXOutdated.message'),
      duration: 10000,
    })
  }

  watch(
    () => settings.value.language,
    (newLanguage) => (locale.value = newLanguage || "en_US"),
    { immediate: true }
  )

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
})

onUnmounted(() => {
  unlistenClose?.()
})
</script>

<template>
  <main class="w-full h-full overflow-hidden text-sm select-none flex flex-col bg-surface-app text-text-primary">
    <div class="absolute bg-[image:var(--bg-image-app)] inset-0 bg-cover bg-center opacity-25 pointer-events-none"></div>
    <Titlebar />

    <div class="flex-1 flex overflow-hidden min-h-0">
      <Sidebar />

      <div class="flex-1 flex flex-col overflow-hidden min-h-0">
        <Header />
        <div class="flex-1 overflow-hidden min-h-0">
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in" >
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
    <NotificationContainer position="bottom-center"/>

    <WelcomeModal :visible="currentModalVisible === 'welcomeModal'" @close="closeModal('welcomeModal')" />
    <UpdateAvailableModal :visible="currentModalVisible === 'updateAvailableModal'" @close="closeModal('updateAvailableModal')" />
    <SyncModal />
    <LogsModal />
  </main>
</template>
<style>

</style>