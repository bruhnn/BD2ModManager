<script setup lang="ts">
import { computed, ref } from 'vue'
import { Profile } from '../../../stores/profiles'
import Input from '../../../components/common/Input.vue'
import Button from '../../../components/common/Button.vue'
import Modal from '../../../components/common/Modal.vue'
import Select from '../../../components/common/Select.vue'

interface CreateProfileOptions {
    name: string
    description: string | null
    templateId: string | null
}

const visible = ref(false)

const profileSelected = ref<CreateProfileOptions>({
    name: '',
    description: null,
    templateId: null
})

const templateProfiles = ref<Profile[]>([])

defineExpose({
    show: (profiles: Profile[]) => {
        templateProfiles.value = [...profiles]
        profileSelected.value = { name: '', description: null, templateId: null }
        visible.value = true
    }
})

const emit = defineEmits<{
    (e: 'on-profile-create', name: string, description: string | null, profileTemplateId: string | null): void
}>()

function create() {
    const { name, description, templateId } = profileSelected.value
    if (!name.trim()) return

    emit(
        'on-profile-create',
        name.trim(),
        description?.trim() || null,
        templateId
    )

    visible.value = false
}

const canCreateProfile = computed(() => {
    return profileSelected.value.name.trim().length > 0 && !templateProfiles.value.some(p => p.name === profileSelected.value.name.trim())
})

function onClose() {
    profileSelected.value = { name: '', description: null, templateId: null }
    visible.value = false
}
</script>

<template>
    <Modal v-model:show="visible" size="md"
        :title="$t('profilesTab.modals.createProfile.title')" :subtitle="$t('profilesTab.modals.createProfile.description')" @close="onClose">
        <div class="text-text-primary flex flex-col gap-4 p-4">

            <div class="flex flex-col gap-1">
                <label for="name" class="font-semibold">
                    {{ $t('profilesTab.modals.createProfile.nameField.label') }}
                </label>
                <div class="h-10">
                    <Input id="name" class="flex-auto"
                        :placeholder="$t('profilesTab.modals.createProfile.nameField.placeholder')"
                        :model-value="profileSelected.name ?? ''"
                        @update:model-value="val => { if (profileSelected) profileSelected.name = val }" />
                </div>
            </div>

            <div class="flex flex-col gap-1">
                <label for="description" class="font-semibold">
                    {{ $t('profilesTab.modals.createProfile.descriptionField.label') }}
                </label>
                <div class="h-10">
                    <Input id="description" class="flex-auto"
                        :placeholder="$t('profilesTab.modals.createProfile.descriptionField.placeholder')"
                        :model-value="profileSelected.description ?? ''" />
                </div>
            </div>

            <div class="flex flex-col gap-1">
                <label for="template" class="font-semibold">
                    {{ $t('profilesTab.modals.createProfile.templateField.label') }}
                </label>

                <div class="relative flex">
                    <Select id="template" class="flex-auto"
                        :placeholder="$t('profilesTab.modals.createProfile.templateField.placeholder')"
                        :options="templateProfiles.map(p => ({ label: p.name, value: p.id }))"
                        :model-value="profileSelected.templateId ?? null"
                        @update:model-value="(val: string | null) => { if (profileSelected) profileSelected.templateId = val }" />
                </div>
            </div>

        </div>

        <template #footer>
            <div class="flex justify-end gap-2 p-2">
                <Button :label="$t('common.actions.cancel')"
                    @click="onClose" />
                <Button  variant="primary" :label="$t('profilesTab.modals.createProfile.actions.createProfile')" @click="create" :disabled="!canCreateProfile" />
            </div>
        </template>
    </Modal>
</template>
