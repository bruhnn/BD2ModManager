<script setup lang="ts">
import { TabPanel } from '@headlessui/vue';
import Section from '../Section.vue';
import { useI18n } from 'vue-i18n';
import { computed } from 'vue';
import { Folder, SquareArrowOutUpRight } from 'lucide-vue-next';
import { openPath } from '@tauri-apps/plugin-opener';
import { open } from '@tauri-apps/plugin-dialog';
import Select from '../../../components/common/Select.vue';
import Input from '../../../components/common/Input.vue';
import Button from '../../../components/common/Button.vue';
import Checkbox from '../../../components/common/Checkbox.vue';
import { useLoggingStore } from '../../../stores/logging';
import { Language, useSettingsStore } from '../../../stores/settings';
import { useNotificationStore } from '../../../stores/notification.ts';
import { usePreferencesStore } from '../../../stores/preferences.ts';

const settingsStore = useSettingsStore()
const preferencesStore = usePreferencesStore()

const notificationStore = useNotificationStore()

const { t, availableLocales } = useI18n()

const {
    logWarning,
    logError,
    logInfo,
} = useLoggingStore()

const mappedLanguages = [
    { // en
        label: "English (United States)", value: "en_US",
    },
    { // cn, maybe add zh_HK?
        label: "中文 (中国)", value: "zh_CN",
    },
    { // zh-TW
        label: "中文 (台湾)", value: "zh_TW",
    },
    { // ja
        label: "日本語 (日本)", value: "ja_JP",
    },
    { // ko
        label: "한국어 (대한민국)", value: "ko_KR",
    },
    { // ru
        label: "Русский (Россия)", value: "ru_RU",
    },
    { // pt
        label: "Português (Brasil)", value: "pt_BR",
    },
    { // es
        label: "Español (España)", value: "es_ES",
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
    return settingsStore.settings;
})

async function onThemeChanged(theme: string) {
    if (!theme) return

    if (!settingsStore.availableThemes.find((t: any) => t.value === theme)) {
        logWarning(`Theme ${theme} is not in the list of available themes.`)
        return
    }

    await settingsStore.saveSettings({ theme })

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

    await settingsStore.saveSettings({ searchModsRecursively: value })
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

async function onModFilterChanged(field: string, value: boolean | string[]) {
    await settingsStore.saveSettings({ [field]: value })
    logInfo(`Mod filter ${field} changed to ${JSON.stringify(value)}`)
}

async function onSyncMethodChanged(value: string) {
    if (!settingsStore) {
        logError('Settings store is not available. Cannot change syncMethod setting.')
        return
    }

    await settingsStore.saveSettings({ syncMethod: value })
    logInfo(`Sync method changed to ${value}`)
}

async function handleOpenFolder(path: string | undefined | null) {
    if (!path || path.trim() === '') {
        logWarning('Cannot open folder: path is empty');
        return;
    }

    try {
        await openPath(path);
    } catch (error) {
        logError('Failed to open folder:', error);
    }
}

async function handleStagingModsBrowse() {
    const folder = await open({
        multiple: false,
        directory: true,
    })

    if (folder && settingsStore) {

        await settingsStore.saveSettings({ stagingDirectory: folder })

        logInfo(`Staging mods directory changed to ${folder}`)

        notificationStore.add({
            severity: 'success',
            title: 'Staging Mods Directory Updated',
            message: `Staging mods directory has been updated to ${folder}.`,
            duration: 3000
        })
    }
}


async function handleGameDirectoryBrowse() {
    const folder = await open({
        multiple: false,
        directory: true,
    })

    if (folder && settingsStore) {
        // [TODO] check on frontend for now, but should move to backend
        const isValid = await settingsStore.validateGamePath(folder)
        if (!isValid) {
            logWarning(`Selected game directory ${folder} is not valid.`)
            notificationStore.add({
                severity: 'warn',
                title: 'Invalid Game Directory',
                message: `The selected game directory ${folder} is not valid.`,
                duration: 5000
            })
            return
        }

        await settingsStore.saveSettings({ gameDirectory: folder })
        logInfo(`Game directory changed to ${folder}`)
        notificationStore.add({
            severity: 'success',
            title: 'Game Directory Updated',
            message: `Game directory has been updated to ${folder}.`,
            duration: 3000
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
                            :placeholder="$t('settingsTab.general.sections.application.theme.placeholder')" option-label="label"
                            option-value="value" @update:model-value="onThemeChanged" class="col-span-2" />
                    </div>

                    <div class="grid grid-cols-3 items-center gap-4">
                        <label class="text-sm font-medium">
                            {{ $t('settingsTab.general.sections.application.language.label') }}
                        </label>
                        <Select :model-value="settings.language" :options="availableLanguages"
                            :placeholder="$t('settingsTab.general.sections.application.language.placeholder')" option-label="label"
                            option-value="value" @update:model-value="onLanguageChanged" class="col-span-2" />
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
                                placeholder="Game Directory" readonly />
                            <Button :label="$t('common.actions.browse')" :icon="Folder"
                                @click="handleGameDirectoryBrowse" class="whitespace-nowrap min-w-32" />
                            <Button class="whitespace-nowrap" :icon="SquareArrowOutUpRight"
                                @click="handleOpenFolder(settings.gameDirectory)" :disabled="!settings.gameDirectory" />
                        </div>
                    </div>

                    <div class="grid grid-cols-3 items-center gap-4">
                        <label class="text-sm font-medium">
                            {{ $t('settingsTab.general.sections.directories.modsDirectory.label') }}
                        </label>
                        <div class="flex col-span-2 gap-2 items-center">
                            <Input class="w-full min-w-32" :model-value="settings.stagingDirectory ?? ''"
                                placeholder="Staging Mods Directory" readonly />
                            <Button :label="$t('common.actions.browse')" :icon="Folder" @click="handleStagingModsBrowse"
                                class="min-w-32" />
                            <Button @click="handleOpenFolder(settings.stagingDirectory)" :icon="SquareArrowOutUpRight"
                                :disabled="!settings.stagingDirectory" />
                        </div>
                    </div>
                </div>
            </Section>

            <Section :title="$t('settingsTab.general.sections.modManagement.title')">
                <div class="space-y-4">
                    <div class="flex items-center gap-3">
                        <Checkbox inputId="searchModsRecursively" :model-value="settings.searchModsRecursively" :label="$t('settingsTab.general.sections.modManagement.searchRecursively.label')"
                            :description="$t('settingsTab.general.sections.modManagement.searchRecursively.description')"
                            @update:model-value="onSearchModsRecursivelyChanged"  />
                    </div>

                    <div class="flex items-center gap-3">
                        <Checkbox :model-value="settings.autoSyncMods" :label="$t('settingsTab.general.sections.modManagement.autoSyncMods.label')"
                            :description="$t('settingsTab.general.sections.modManagement.autoSyncMods.description')"
                            @update:model-value="onAutoSyncModsChanged" />
                    </div>

                    <div class="grid grid-cols-3 items-center gap-4">
                        <div class="flex flex-col">
                            <span class="text-sm font-medium">{{ $t('settingsTab.general.sections.modManagement.syncMethod.label') }}</span>
                            <p class="text-xs text-text-secondary">{{ $t('settingsTab.general.sections.modManagement.syncMethod.description') }}</p>
                        </div>
                        <Select :model-value="settings.syncMethod" :options="availableSyncMethods"
                            @update:model-value="onSyncMethodChanged" class="col-span-2" />
                    </div>
                </div>
            </Section>

            <Section :title="$t('settingsTab.general.sections.modFilters.title')">
                <p class="text-xs text-text-secondary mb-3">{{ $t('settingsTab.general.sections.modFilters.description') }}</p>
                <div class="space-y-4">
                    <div class="flex items-center gap-3">
                        <Checkbox :model-value="settings.modFilterOnlyEnabled"
                            :label="$t('settingsTab.general.sections.modFilters.onlyEnabled.label')"
                            :description="$t('settingsTab.general.sections.modFilters.onlyEnabled.description')"
                            @update:model-value="(v: boolean) => onModFilterChanged('modFilterOnlyEnabled', v)" />
                    </div>
                    <div class="flex items-center gap-3">
                        <Checkbox :model-value="settings.modFilterOnlyDisabled"
                            :label="$t('settingsTab.general.sections.modFilters.onlyDisabled.label')"
                            :description="$t('settingsTab.general.sections.modFilters.onlyDisabled.description')"
                            @update:model-value="(v: boolean) => onModFilterChanged('modFilterOnlyDisabled', v)" />
                    </div>
                    <div class="flex items-center gap-3">
                        <Checkbox :model-value="settings.modFilterOnlyConflicts"
                            :label="$t('settingsTab.general.sections.modFilters.onlyConflicts.label')"
                            :description="$t('settingsTab.general.sections.modFilters.onlyConflicts.description')"
                            @update:model-value="(v: boolean) => onModFilterChanged('modFilterOnlyConflicts', v)" />
                    </div>
                    <div class="flex items-center gap-3">
                        <Checkbox :model-value="settings.modFilterOnlyErrors"
                            :label="$t('settingsTab.general.sections.modFilters.onlyErrors.label')"
                            :description="$t('settingsTab.general.sections.modFilters.onlyErrors.description')"
                            @update:model-value="(v: boolean) => onModFilterChanged('modFilterOnlyErrors', v)" />
                    </div>
                    <div class="flex items-center gap-3">
                        <Checkbox :model-value="settings.modFilterHideErrors"
                            :label="$t('settingsTab.general.sections.modFilters.hideErrors.label')"
                            :description="$t('settingsTab.general.sections.modFilters.hideErrors.description')"
                            @update:model-value="(v: boolean) => onModFilterChanged('modFilterHideErrors', v)" />
                    </div>
                </div>
            </Section>
        </div>
    </TabPanel>
</template>

<style scoped></style>