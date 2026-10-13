<script
    setup
    lang="ts"
>
import { TabPanel } from '@headlessui/vue'
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Folder, SquareArrowOutUpRight } from '@lucide/vue'
import { openPath } from '@tauri-apps/plugin-opener'
import { open } from '@tauri-apps/plugin-dialog'

import Checkbox from '../../../components/common/Checkbox.vue'
import Section from '../Section.vue'
import Select from '../../../components/common/Select.vue'
import Slider from '../../../components/common/Slider.vue'
import Button from '../../../components/common/Button.vue'
import Input from '../../../components/common/Input.vue'

import { useLoggingStore } from '../../../stores/logging'
import { Language, useSettingsStore } from '../../../stores/settings'
import { useNotificationStore } from '../../../stores/notification.ts'
import { usePreferencesStore } from '../../../stores/preferences.ts'
import { useModsStore } from '../../../stores/mods'

const settingsStore = useSettingsStore()
const modsStore = useModsStore()
const preferencesStore = usePreferencesStore()
const notificationStore = useNotificationStore()

const { t, availableLocales } = useI18n()

const { logWarning, logError, logInfo } = useLoggingStore()

const pendingTheme = ref<string | null>(null)
const autoSyncModsDelay = ref((settingsStore.settings.autoSyncModsDelay ?? 3000) / 1000)
const autoSyncModsDelayInput = ref(String(autoSyncModsDelay.value))

watch(autoSyncModsDelay, (value) => {
    autoSyncModsDelayInput.value = String(value)
})

const mappedLanguages = [
    {
        // en
        label: 'English (United States)',
        value: 'en_US',
    },
    {
        // cn, maybe add zh_HK?
        label: '中文 (中国)',
        value: 'zh_CN',
    },
    {
        // zh-TW
        label: '中文 (台湾)',
        value: 'zh_TW',
    },
    {
        // ja
        label: '日本語 (日本)',
        value: 'ja_JP',
    },
    {
        // ko
        label: '한국어 (대한민국)',
        value: 'ko_KR',
    },
    {
        // ru
        label: 'Русский (Россия)',
        value: 'ru_RU',
    },
    {
        // pt
        label: 'Português (Brasil)',
        value: 'pt_BR',
    },
    {
        // es
        label: 'Español (España)',
        value: 'es_ES',
    },
]

const availableLanguages = computed(() => {
    return availableLocales.map((locale) => {
        return mappedLanguages.find((lang) => lang.value === locale)
    })
})

const availableSyncMethods = computed(() => [
    { value: 'copy', label: t('settingsTab.general.sections.modManagement.syncMethod.options.copy') },
    // { value: 'hardlink', label: t('settingsTab.general.sections.modManagement.syncMethod.options.hardlink') },
    { value: 'symlink', label: t('settingsTab.general.sections.modManagement.syncMethod.options.symlink') },
])

const settings = computed(() => {
    return settingsStore.settings
})

function onThemeSelected(theme: string) {
    if (!theme) return

    pendingTheme.value = theme
}

async function onThemeSelectClosed() {
    if (!pendingTheme.value) return

    const theme = pendingTheme.value
    pendingTheme.value = null

    // Wait until the Select dropdown has actually disappeared.
    await nextTick()

    await onThemeChanged(theme)
}

async function onThemeChanged(theme: string) {
    if (!theme) return

    const isValidTheme = settingsStore.availableThemes.some((availableTheme) => availableTheme.value === theme)

    if (!isValidTheme) {
        logWarning(`Theme ${theme} is not in the list of available themes.`)
        return
    }

    if (!document.startViewTransition) {
        await settingsStore.saveSettings({ theme })

        logInfo(`Theme changed to ${theme}`)
        return
    }

    const transition = document.startViewTransition(async () => {
        await settingsStore.saveSettings({ theme })
        await nextTick()
    })

    await transition.ready

    document.documentElement.animate(
        {
            clipPath: ['inset(49.9% round 7px)', 'inset(0% round 7px)'],
        },
        {
            duration: 300,
            easing: 'cubic-bezier(0.2, 0.7, 0.3, 1)',
            fill: 'both',
            pseudoElement: '::view-transition-new(root)',
        },
    )

    logInfo(`Theme changed to ${theme}`)
}

async function onLanguageChanged(language: Language) {
    if (!language) return

    if (!settingsStore || settingsStore == undefined) {
        return logError('Settings store is not available. Cannot change language.')
    }

    await settingsStore.saveSettings({ language })

    logInfo(`Language changed to ${language}`)
}

async function onSearchModsRecursivelyChanged(value: boolean) {
    if (!settingsStore) {
        logError('Settings store is not available. Cannot change searchModsRecursively setting.')
        return
    }

    await settingsStore.saveSettings({
        searchModsRecursively: value,
    })

    logInfo(`Search mods recursively changed to ${value}`)
}

async function onAutoSyncModsChanged(value: boolean) {
    if (!settingsStore) {
        logError('Settings store is not available. Cannot change autoSyncMods setting.')
        return
    }

    await settingsStore.saveSettings({ autoSyncMods: value })
    logInfo(`Auto sync mods changed to ${value}`)
}

async function onAutoSyncModsDelayChanged(value: number) {
    const seconds = Number.isFinite(value) ? Math.min(10, Math.max(1, value)) : autoSyncModsDelay.value
    autoSyncModsDelay.value = seconds
    autoSyncModsDelayInput.value = String(seconds)
    const milliseconds = Math.round(seconds * 1000)
    if (milliseconds === settingsStore.settings.autoSyncModsDelay) return

    await settingsStore.saveSettings({ autoSyncModsDelay: milliseconds })
    logInfo(`Auto sync delay changed to ${seconds} seconds`)
}

async function onSyncMethodChanged(value: string) {
    if (!settingsStore) {
        logError('Settings store is not available. Cannot change syncMethod setting.')
        return
    }

    await settingsStore.saveSettings({
        syncMethod: value,
    })
    await modsStore.checkIsSyncNeeded()

    logInfo(`Sync method changed to ${value}`)
}

async function handleOpenFolder(path: string | undefined | null) {
    if (!path || path.trim() === '') {
        logWarning('Cannot open folder: path is empty')
        return
    }

    try {
        await openPath(path)
    } catch (error) {
        logError('Failed to open folder:', error)
    }
}

async function handleStagingModsBrowse() {
    const folder = await open({
        multiple: false,
        directory: true,
    })

    if (folder && settingsStore) {
        // validate
        if (!(await settingsStore.validateStagingPath(folder))) {
            logWarning(`Selected staging mods directory ${folder} is not valid.`)

            return notificationStore.add({
                type: 'warn',
                title: t('settingsTab.general.notifications.invalidStagingDirectory.title'),
                message: t('settingsTab.general.notifications.invalidStagingDirectory.message', { path: folder }),
            })
        }

        await settingsStore.saveSettings({
            stagingDirectory: folder,
        })
        await modsStore.discoverMods()

        logInfo(`Staging mods directory changed to ${folder}`)

        notificationStore.add({
            type: 'success',
            title: t('settingsTab.general.notifications.stagingDirectoryUpdated.title'),
            message: t('settingsTab.general.notifications.stagingDirectoryUpdated.message', { path: folder }),
            duration: 3000,
        })
    }
}

async function handleGameDirectoryBrowse() {
    const folder = await open({
        multiple: false,
        directory: true,
    })

    if (folder && settingsStore) {
        const isValid = await settingsStore.validateGamePath(folder)

        if (!isValid) {
            logWarning(`Selected game directory ${folder} is not valid.`)

            notificationStore.add({
                type: 'warn',
                title: t('settingsTab.general.notifications.invalidGameDirectory.title'),
                message: t('settingsTab.general.notifications.invalidGameDirectory.message', { path: folder }),
                duration: 5000,
            })

            return
        }

        await settingsStore.saveSettings({
            gameDirectory: folder,
        })
        await modsStore.discoverMods()

        logInfo(`Game directory changed to ${folder}`)

        notificationStore.add({
            type: 'success',
            title: t('settingsTab.general.notifications.gameDirectoryUpdated.title'),
            message: t('settingsTab.general.notifications.gameDirectoryUpdated.message', { path: folder }),
            duration: 3000,
        })
    }
}


</script>

<template>
    <TabPanel>
        <div class="flex flex-col gap-8">
            <Section :title="$t('settingsTab.general.sections.application.title')">
                <div class="flex flex-col gap-4">
                    <div class="grid grid-cols-3 items-center gap-4">
                        <label class="text-sm font-medium">
                            {{ $t('settingsTab.general.sections.application.theme.label') }}
                        </label>

                        <Select :model-value="settings.theme" :options="settingsStore.availableThemes"
                            :placeholder="$t('settingsTab.general.sections.application.theme.placeholder')"
                            option-label="label" option-value="value" class="col-span-2"
                            @update:model-value="onThemeSelected" @close="onThemeSelectClosed" />
                    </div>

                    <div class="grid grid-cols-3 items-center gap-4">
                        <label class="text-sm font-medium">
                            {{ $t('settingsTab.general.sections.application.language.label') }}
                        </label>

                        <Select :model-value="settings.language" :options="availableLanguages"
                            :placeholder="$t('settingsTab.general.sections.application.language.placeholder')"
                            option-label="label" option-value="value" class="col-span-2"
                            @update:model-value="onLanguageChanged" />
                    </div>

                    <div class="flex items-start gap-3">
                        <Checkbox v-model="preferencesStore.forceEnglishNames"
                            :label="$t('settingsTab.general.sections.application.forceEnglishNames.label')"
                            :description="$t('settingsTab.general.sections.application.forceEnglishNames.description')" />
                    </div>
                </div>
            </Section>

            <Section :title="$t('settingsTab.general.sections.directories.title')">
                <div class="flex flex-col gap-4">
                    <div class="grid grid-cols-3 items-center gap-4">
                        <label class="text-sm font-medium">
                            {{ $t('settingsTab.general.sections.directories.gameDirectory.label') }}
                        </label>

                        <div class="flex w-full gap-2 items-center col-span-2">
                            <Input class="w-full min-w-32" :model-value="settings.gameDirectory ?? ''"
                                :placeholder="$t('settingsTab.general.sections.directories.gameDirectory.placeholder')"
                                readonly />

                            <Button :label="$t('common.actions.browse')" :icon="Folder"
                                class="whitespace-nowrap min-w-32" @click="handleGameDirectoryBrowse" />

                            <Button class="whitespace-nowrap" :icon="SquareArrowOutUpRight"
                                :disabled="!settings.gameDirectory" @click="handleOpenFolder(settings.gameDirectory)" />
                        </div>
                    </div>

                    <div class="grid grid-cols-3 items-center gap-4">
                        <label class="text-sm font-medium">
                            {{ $t('settingsTab.general.sections.directories.modsDirectory.label') }}
                        </label>

                        <div class="flex col-span-2 gap-2 items-center">
                            <Input class="w-full min-w-32" :model-value="settings.stagingDirectory ?? ''"
                                :placeholder="$t('settingsTab.general.sections.directories.modsDirectory.placeholder')"
                                readonly />

                            <Button :label="$t('common.actions.browse')" :icon="Folder" class="min-w-32"
                                @click="handleStagingModsBrowse" />

                            <Button :icon="SquareArrowOutUpRight" :disabled="!settings.stagingDirectory"
                                @click="handleOpenFolder(settings.stagingDirectory)" />
                        </div>
                    </div>
                </div>
            </Section>

            <Section :title="$t('settingsTab.general.sections.modManagement.title')">
                <div class="space-y-4">
                    <div class="flex flex-col items-start gap-3">
                        <Checkbox inputId="searchModsRecursively" :model-value="settings.searchModsRecursively"
                            :label="$t('settingsTab.general.sections.modManagement.searchRecursively.label')"
                            :description="$t('settingsTab.general.sections.modManagement.searchRecursively.description')"
                            @update:model-value="onSearchModsRecursivelyChanged" />
                        <Checkbox :model-value="settings.autoSyncMods"
                            :label="$t('settingsTab.general.sections.modManagement.autoSyncMods.label')"
                            :description="$t('settingsTab.general.sections.modManagement.autoSyncMods.description')"
                            @update:model-value="onAutoSyncModsChanged" />
                        <div class="grid w-full grid-cols-3 items-center gap-4">
                            <div class="flex flex-col">
                                <label for="autoSyncModsDelay" class="text-sm font-medium">
                                    {{ $t('settingsTab.general.sections.modManagement.autoSyncMods.delay.label') }}
                                </label>
                                <p id="autoSyncModsDelayDescription" class="text-xs text-text-secondary">
                                    {{ $t('settingsTab.general.sections.modManagement.autoSyncMods.delay.description')
                                    }}
                                </p>
                            </div>
                            <div class="col-span-2 flex min-w-0 items-center gap-2">
                                <Slider v-model="autoSyncModsDelay" suffix="s" :min="1" :max="10" :step="0.1"
                                    :disabled="!settings.autoSyncMods"
                                    :aria-label="$t('settingsTab.general.sections.modManagement.autoSyncMods.delay.label')"
                                    aria-describedby="autoSyncModsDelayDescription"
                                    @change="onAutoSyncModsDelayChanged" />
                                <div class="w-16 shrink-0">
                                    <Input id="autoSyncModsDelay" v-model="autoSyncModsDelayInput" type="text"
                                        inputmode="decimal" :disabled="!settings.autoSyncMods"
                                        aria-describedby="autoSyncModsDelayDescription"
                                        @change="onAutoSyncModsDelayChanged(Number(autoSyncModsDelayInput.replace(',', '.')))" />
                                </div>
                                <span class="text-sm text-text-secondary">s</span>
                            </div>
                        </div>
                    </div>

                    <div class="grid grid-cols-3 items-center gap-4">
                        <div class="flex flex-col">
                            <span class="text-sm font-medium">
                                {{ $t('settingsTab.general.sections.modManagement.syncMethod.label') }}
                            </span>

                            <p class="text-xs text-text-secondary">
                                {{ $t('settingsTab.general.sections.modManagement.syncMethod.description') }}
                            </p>
                        </div>

                        <Select :model-value="settings.syncMethod" :options="availableSyncMethods" class="col-span-2"
                            @update:model-value="onSyncMethodChanged" />
                    </div>
                </div>
            </Section>
        </div>
    </TabPanel>
</template>

<style scoped></style>
