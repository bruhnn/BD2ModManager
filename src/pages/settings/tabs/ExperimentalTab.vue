<script setup lang="ts">
import { TabPanel } from '@headlessui/vue';
import Section from '../Section.vue';
import Button from '../../../components/common/Button.vue';
import Select from '../../../components/common/Select.vue';
import { ref } from 'vue';
import { invoke } from '@tauri-apps/api/core';
import { useProfilesStore } from '../../../stores/profiles';
import { useLoggingStore } from '../../../stores/logging';
import { useConfirm } from '../../../plugins/ConfirmService';
import { useI18n } from 'vue-i18n';
import { useNotificationStore } from '../../../stores/notification.ts';
import { getErrorMessage } from '../../../utils/errors.ts';

const profilesStore = useProfilesStore()

const notificationStore = useNotificationStore()
const confirmation = useConfirm()
const { t } = useI18n()

interface LegacyProfile {
    id: string,
    name: string
}

const profilesIdChoose = ref<string[]>([])
const legacyProfiles = ref<LegacyProfile[]>([])
const loggingStore = useLoggingStore()
const isImportingProfiles = ref(false)
const isImportingModAuthors = ref(false)

function handleMigrateError(error: unknown) {
    notificationStore.add({
        type: 'error',
        title: t('errors.MigrateError.title'),
        message: getErrorMessage(t, error),
        duration: 5000
    })
}

async function searchLegacyProfiles() {
    try {
        const profiles = await invoke('get_legacy_profiles') as LegacyProfile[]
        legacyProfiles.value = profiles
        if (!profiles.length) {
            notificationStore.add({ type: 'info', title: t('settingsTab.experimental.sections.migration.notifications.noProfilesToImport.title'), message: t('settingsTab.experimental.sections.migration.notifications.noProfilesToImport.message'), duration: 3000 })
        }
    } catch (err) {
        loggingStore.logError("Error fetching legacy profiles:", err)
        handleMigrateError(err)
    }
}

function importProfiles() {
    if (isImportingProfiles.value) return
    if (profilesIdChoose.value.length === 0) {
        notificationStore.add({ type: 'warn', title: t('settingsTab.experimental.sections.migration.notifications.noProfilesSelected.title'), message: t('settingsTab.experimental.sections.migration.notifications.noProfilesSelected.message'), duration: 3000 })
        return
    }

    isImportingProfiles.value = true
    invoke<boolean>('import_legacy_profiles', { profileIds: profilesIdChoose.value })
        .then(async (success) => {
            if (!success) {
                notificationStore.add({ type: 'info', title: t('settingsTab.experimental.sections.migration.notifications.noProfilesToImport.title'), message: t('settingsTab.experimental.sections.migration.notifications.noProfilesToImport.message'), duration: 3000 })
                return
            }

            notificationStore.add({ type: 'success', title: t('settingsTab.experimental.sections.migration.notifications.importProfilesSuccess.title'), message: t('settingsTab.experimental.sections.migration.notifications.importProfilesSuccess.message'), duration: 5000 })

            profilesIdChoose.value = []
            await profilesStore.loadProfiles()

            await searchLegacyProfiles()
        })
        .catch((err) => {
            loggingStore.logError("Error importing profiles:", err)
            handleMigrateError(err)
        })
        .finally(() => {
            isImportingProfiles.value = false
        })
}

async function importModAuthors() {
    if (isImportingModAuthors.value) return
    isImportingModAuthors.value = true
    try {
        const confirmationResult = await confirmation.confirm({
            title: t('settingsTab.experimental.sections.migration.confirmations.importModAuthors.title'),
            message: t('settingsTab.experimental.sections.migration.confirmations.importModAuthors.message'),
            acceptButton: {
                label: t('settingsTab.experimental.sections.migration.confirmations.importModAuthors.actions.importModAuthors'),
            },
            rejectButton: {
                label: t('settingsTab.experimental.sections.migration.confirmations.importModAuthors.actions.cancel'),
            },
        })

        if (!confirmationResult.confirmed) return

        await invoke<boolean>('import_legacy_mod_authors')
            .then((success) => {
                if (!success) {
                    return notificationStore.add({ type: 'info', title: t('settingsTab.experimental.sections.migration.notifications.noModAuthorsToImport.title'), message: t('settingsTab.experimental.sections.migration.notifications.noModAuthorsToImport.message'), duration: 3000 })
                }
                notificationStore.add({ type: 'success', title: t('settingsTab.experimental.sections.migration.notifications.importModAuthorsSuccess.title'), message: t('settingsTab.experimental.sections.migration.notifications.importModAuthorsSuccess.message'), duration: 5000 })
            })
            .catch((err) => {
                loggingStore.logError("Error importing mod authors:", err)
                handleMigrateError(err)
            })
    } finally {
        isImportingModAuthors.value = false
    }
}
</script>

<template>
    <TabPanel>
        <div class="flex flex-col">
            <Section :title="t('settingsTab.experimental.sections.migration.title')">
                <div class="flex flex-col gap-2">
                    <div class="flex justify-between gap-2">
                        <div class="flex flex-col min-w-0">
                            <p class="text-text-primary font-medium shrink-0">{{
                                t('settingsTab.experimental.sections.migration.profiles.title') }}</p>
                            <p class="text-text-secondary truncate"
                                :title="t('settingsTab.experimental.sections.migration.profiles.description')">
                                {{ t('settingsTab.experimental.sections.migration.profiles.description') }}
                            </p>
                        </div>
                        <div class="flex gap-2 items-center">
                            <Select class="w-64" :options="legacyProfiles.map(p => ({ label: p.name, value: p.id }))"
                                :placeholder="t('settingsTab.experimental.sections.migration.profiles.selectPlaceholder')"
                                :multiple="true" v-model="profilesIdChoose" />
                            <Button variant="default" :disabled="isImportingProfiles" @click="importProfiles">{{
                                t('settingsTab.experimental.sections.migration.actions.importProfiles') }}</Button>
                            <Button variant="default" @click="searchLegacyProfiles">{{
                                t('settingsTab.experimental.sections.migration.actions.searchProfiles') }}</Button>
                        </div>
                    </div>
                    <div class="flex justify-between gap-2">
                        <div class="flex flex-col min-w-0">
                            <p class="text-text-primary font-medium">{{
                                t('settingsTab.experimental.sections.migration.modAuthors.title') }}</p>
                            <p class="text-text-secondary truncate"
                                :title="t('settingsTab.experimental.sections.migration.modAuthors.description')">
                                {{ t('settingsTab.experimental.sections.migration.modAuthors.description') }}
                            </p>
                        </div>
                        <div>
                            <Button variant="default" :disabled="isImportingModAuthors" @click="importModAuthors">{{
                                t('settingsTab.experimental.sections.migration.actions.importModAuthors') }}</Button>
                        </div>
                    </div>
                </div>
            </Section>
        </div>
    </TabPanel>
</template>
