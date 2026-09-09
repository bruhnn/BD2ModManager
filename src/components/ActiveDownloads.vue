<script setup lang="ts">
import { Download, X } from '@lucide/vue'

import { computed, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { UpdateStatus, useUpdater } from '../composables/useUpdater'

import Popover from './common/Popover.vue'

const { t } = useI18n()
const { appUpdate, modPreviewUpdate, gameDataUpdate } = useUpdater()

function getProgress(downloaded: number, total: number | null) {
  if (!total) return null
  return Math.min(downloaded / total * 100, 100)
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`

  const units = ['KB', 'MB', 'GB']
  let value = bytes / 1024
  let unit = units[0]

  for (let index = 1; value >= 1024 && index < units.length; index++) {
    value /= 1024
    unit = units[index]
  }

  return `${value.toFixed(0)} ${unit}`
}

const liveDownloads = computed(() => {
  const items: Array<{
    id: string
    name: string
    detail?: string
    progress: number | null
  }> = []

  if (appUpdate.value?.status === UpdateStatus.Downloading) {
    const { downloaded, total } = appUpdate.value.progress

    items.push({
      id: 'app-update',
      name: `BD2ModManager v${appUpdate.value.update.versionAvailable}`,
      detail: total
        ? `${formatBytes(downloaded)} / ${formatBytes(total)}`
        : formatBytes(downloaded),
      progress: getProgress(downloaded, total),
    })
  }

  if (modPreviewUpdate.value?.status === UpdateStatus.Downloading) {
    const { downloaded, total } = modPreviewUpdate.value.progress

    items.push({
      id: 'mod-preview',
      name: `BD2ModPreview v${modPreviewUpdate.value.update.versionAvailable}`,
      detail: total
        ? `${formatBytes(downloaded)} / ${formatBytes(total)}`
        : formatBytes(downloaded),
      progress: getProgress(downloaded, total),
    })
  }

  if (gameDataUpdate.value?.status === UpdateStatus.Updating) {
    for (const resource of gameDataUpdate.value.resources) {
      const download = resource.progress.download
      if (!download) continue

      if (resource.resource === 'characters') {
        items.push({
          id: 'game-data-characters',
          name: 'characters.json',
          progress: download.percentage,
        })
      }

      if (resource.resource === 'char_assets') {
        items.push({
          id: 'game-data-character-assets',
          name: t('titlebar.activeDownloads.characterAssets'),
          detail: download.current !== undefined && download.total !== undefined
            ? `${download.current} / ${download.total}`
            : undefined,
          progress: download.percentage,
        })
      }
    }
  }

  return items
})

const downloads = liveDownloads
const currentDownload = computed(() => downloads.value[0] ?? null)
const isVisible = ref(downloads.value.length > 0)

let hideTimeout: number | null = null

watch(() => downloads.value.length, (count, previousCount) => {
  if (hideTimeout !== null) {
    window.clearTimeout(hideTimeout)
    hideTimeout = null
  }

  if (count > 0) {
    isVisible.value = true
    return
  }

  if (previousCount > 0) {
    hideTimeout = window.setTimeout(() => {
      isVisible.value = false
      hideTimeout = null
    }, 30000)
  }

  console.log(count, previousCount)
})


onUnmounted(() => {
  if (hideTimeout !== null) window.clearTimeout(hideTimeout)
})
</script>

<template>
  <Transition name="downloads-trigger">
    <div v-if="isVisible" class="min-w-0 max-w-[40vw]">
      <Popover placement="bottom">
      <template #trigger="{ toggle, isOpen }">
        <button type="button"
          class="group flex items-center gap-1 md:gap-2 cursor-pointer hover:bg-accent-hover hover:text-text-on-accent rounded-sm px-2.5 py-1 transition-colors duration-200"
          :title="t('titlebar.activeDownloads.title')" :aria-expanded="isOpen"
          @click="toggle">
          <Download class="w-[1.25em] h-[1.25em]" />

          <template v-if="currentDownload">
            <span class="hidden min-[1152px]:inline font-semibold text-sm">
              {{ t('titlebar.activeDownloads.title') }}
            </span>
            <span
              class="inline-flex h-4.5 min-w-4.5 shrink-0 items-center justify-center rounded-sm bg-text-primary/10 px-1 text-[10px] font-semibold leading-none tabular-nums text-text-primary transition-colors group-hover:bg-text-on-accent/20 group-hover:text-text-on-accent">
              {{ downloads.length }}
            </span>
          </template>

          <span v-else class="hidden min-[1152px]:inline font-semibold text-sm">{{ t('titlebar.activeDownloads.empty') }}</span>
        </button>
      </template>

      <template #default="{ close }">
        <div
          class="w-96 max-w-[calc(100vw-1rem)] overflow-hidden rounded-md border border-border-default bg-surface-popover shadow-lg">
          <div class="flex items-center justify-between border-b border-border-default px-3 py-2">
            <h2 class="flex items-center gap-2 text-sm font-semibold text-text-primary">
              {{ t('titlebar.activeDownloads.title') }}
            </h2>
            <button type="button"
              class="rounded-sm p-0.5 text-text-secondary transition-colors hover:bg-state-hover hover:text-text-primary"
              :aria-label="t('common.actions.close')" @click="close">
              <X class="size-4 cursor-pointer" />
            </button>
          </div>

          <div v-if="downloads.length > 0" class="max-h-72 divide-y divide-border-subtle overflow-y-auto">
            <div v-for="download in downloads" :key="download.id" class="px-3 py-3">
              <div class="flex min-w-0 items-center justify-between gap-3">
                <p class="truncate text-sm font-medium text-text-primary" :title="download.name">
                  {{ download.name }}
                </p>
                <span v-if="download.progress !== null"
                  class="shrink-0 text-xs font-mono tabular-nums text-text-secondary">
                  {{ Math.round(download.progress) }}%
                </span>
              </div>

              <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-border-default">
                <div v-if="download.progress === null" class="h-full w-full animate-pulse rounded-full bg-accent" />
                <div v-else class="h-full rounded-full bg-accent transition-[width] duration-150"
                  :style="{ width: `${download.progress}%` }" />
              </div>

              <div v-if="download.detail" class="mt-1.5 min-w-0 text-xs text-text-secondary">
                <span class="truncate font-mono" :title="download.detail">
                  {{ download.detail }}
                </span>
              </div>
            </div>
          </div>
          <div v-else class="px-3 py-2 text-center">
            <span class="text-sm text-center font- text-text-secondary w-full">
              {{ t("titlebar.activeDownloads.empty") }}
            </span>
          </div>
        </div>
      </template>
      </Popover>
    </div>
  </Transition>
</template>

<style scoped>
.downloads-trigger-enter-active,
.downloads-trigger-leave-active {
  transition: opacity 160ms ease, transform 160ms ease;
}

.downloads-trigger-enter-from,
.downloads-trigger-leave-to {
  opacity: 0;
  transform: translateY(-3px) scale(0.97);
}

@media (prefers-reduced-motion: reduce) {
  .downloads-trigger-enter-active,
  .downloads-trigger-leave-active {
    transition: none;
  }
}
</style>
