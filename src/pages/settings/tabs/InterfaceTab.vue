<script lang="ts" setup>
import { TabPanel } from '@headlessui/vue';
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import Section from '../Section.vue';
import Select from '../../../components/common/Select.vue';
import Checkbox from '../../../components/common/Checkbox.vue';
import { usePreferencesStore } from '../../../stores/preferences';

const preferencesStore = usePreferencesStore()

const { t } = useI18n()

const columnsOptions = computed(() => [
    // { label: t('settingsTab.interface.sections.columns.visibleColumns.options.status', 'Status'), value: 'status'},
    { label: t('settingsTab.interface.sections.columns.visibleColumns.options.modName'), value: 'name' },
    { label: t('settingsTab.interface.sections.columns.visibleColumns.options.character'), value: 'character' },
    { label: t('settingsTab.interface.sections.columns.visibleColumns.options.modType'), value: 'modType' },
    { label: t('settingsTab.interface.sections.columns.visibleColumns.options.author'), value: 'author' },
])

const modNameDisplayOptions = computed(() => [
    { label: t('settingsTab.interface.sections.modNameColumn.options.short'), value: 'short' },
    { label: t('settingsTab.interface.sections.modNameColumn.options.full'), value: 'full' },
])

const characterDisplayOptions = computed(() => [
    { label: t('settingsTab.interface.sections.characterColumn.options.full'), value: 'full' },
    { label: t('settingsTab.interface.sections.characterColumn.options.iconOnly'), value: 'iconOnly' },
    { label: t('settingsTab.interface.sections.characterColumn.options.nameOnly'), value: 'nameOnly' },
])

const modTypeDisplayOptions = computed(() => [
    { label: t('settingsTab.interface.sections.modTypeColumn.options.full'), value: 'full' },
    { label: t('settingsTab.interface.sections.modTypeColumn.options.iconOnly'), value: 'iconOnly' },
    { label: t('settingsTab.interface.sections.modTypeColumn.options.labelOnly'), value: 'labelOnly' },
])
</script>

<template>
    <TabPanel>
        <div class="flex flex-col gap-4">
            <Section :title="$t('settingsTab.interface.sections.columns.title')">
                <div class="flex flex-col gap-4">
                    <div class="flex flex-col gap-1">
                        <label class="text-sm font-medium">
                            {{ $t('settingsTab.interface.sections.columns.visibleColumns.label') }}
                        </label>
                        <Select v-model="preferencesStore.visibleModListColumns" :options="columnsOptions"
                            option-label="label" option-value="value" class="w-full" multiple />
                        <p class="text-xs text-text-secondary">
                            {{ $t('settingsTab.interface.sections.columns.visibleColumns.description') }}
                        </p>
                    </div>

                    <div class="flex flex-col gap-4">
                        <div class="grid grid-cols-3">
                            <div class="flex flex-col">
                                <span class="text-sm font-medium">{{
                                    $t('settingsTab.interface.sections.modNameColumn.label') }}</span>
                                <p class="text-xs text-text-secondary">{{
                                    $t('settingsTab.interface.sections.modNameColumn.description') }}</p>
                            </div>
                            <Select :model-value="preferencesStore.modNameDisplay"
                                @update:model-value="preferencesStore.modNameDisplay = $event"
                                :options="modNameDisplayOptions" class="col-span-2" />
                        </div>
                    </div>

                    <div class="grid grid-cols-3">
                        <div class="flex flex-col">
                            <span class="text-sm font-medium">{{
                                $t('settingsTab.interface.sections.characterColumn.label')
                            }}</span>
                            <p class="text-xs text-text-secondary">{{
                                $t('settingsTab.interface.sections.characterColumn.description') }}
                            </p>
                        </div>
                        <Select :model-value="preferencesStore.characterDisplay"
                            @update:model-value="preferencesStore.characterDisplay = $event"
                            :options="characterDisplayOptions" class="col-span-2" />
                    </div>

                    <div class="flex flex-col gap-4">
                        <div class="grid grid-cols-3">
                            <div class="flex flex-col">
                                <span class="text-sm font-medium">{{
                                    $t('settingsTab.interface.sections.modTypeColumn.label')
                                    }}</span>
                                <p class="text-xs text-text-secondary">{{
                                    $t('settingsTab.interface.sections.modTypeColumn.description') }}
                                </p>
                            </div>
                            <Select :model-value="preferencesStore.modTypeDisplay"
                                @update:model-value="preferencesStore.modTypeDisplay = $event"
                                :options="modTypeDisplayOptions" class="col-span-2" />
                        </div>

                        <div class="flex items-start gap-3">
                            <Checkbox v-model="preferencesStore.enableModTypeColors"
                                :label="$t('settingsTab.interface.sections.modTypeColumn.enableColors.label')"
                                :description="$t('settingsTab.interface.sections.modTypeColumn.enableColors.description')" />
                        </div>
                    </div>
                </div>
            </Section>

            <Section :title="$t('settingsTab.interface.sections.profiles.title')">
                <div class="flex items-start gap-3">
                    <Checkbox v-model="preferencesStore.showEditModsButton"
                        :label="$t('settingsTab.interface.sections.profiles.showEditModsButton.label')"
                        :description="$t('settingsTab.interface.sections.profiles.showEditModsButton.description')" />
                </div>
            </Section>
        </div>
    </TabPanel>
</template>

<style scoped></style>