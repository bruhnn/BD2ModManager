<script setup lang="ts">
import { ref } from 'vue'
import Input from '../../../components/common/Input.vue'
import Button from '../../../components/common/Button.vue'
import Modal from '../../../components/common/Modal.vue'

interface EditProfileOptions {
  id: string
  name: string
  description: string | null
}

const visible = ref(false)
const profileSelected = ref<EditProfileOptions | null>(null)

defineExpose({
  show: (opts: EditProfileOptions) => {
    profileSelected.value = { ...opts }
    visible.value = true
  }
})

const emit = defineEmits<{
  (e: 'on-profile-edit', id: string, name: string, description: string | null): void
}>()

function save() {
  if (!profileSelected.value) return

  const { id, name, description } = profileSelected.value
  if (!name.trim()) return

  emit(
    'on-profile-edit',
    id,
    name.trim(),
    description?.trim() || null
  )

  visible.value = false
}
</script>

<template>
  <Modal
    v-model:show="visible"
    class="min-w-120 max-w-200 max-h-[80%]"
    :title="$t('profilesTab.modals.editProfile.title')"
    :subtitle="$t('profilesTab.modals.editProfile.description')"
    @close="visible = false"
  >
    <div
      v-if="profileSelected"
      class="text-text-primary flex flex-col gap-4 p-4"
    >

      <div class="flex flex-col gap-1">
        <label for="edit-name" class="font-semibold">
          {{ $t('profilesTab.modals.editProfile.nameField.label') }}
        </label>
        <div class="h-10">
          <Input
            id="edit-name"
            class="flex-auto"
            :placeholder="$t('profilesTab.modals.editProfile.nameField.placeholder')"
            :model-value="profileSelected.name ?? ''"
            :disabled="profileSelected.id === 'default'"
            @update:model-value="val => { if (profileSelected) profileSelected.name = val }"
          />
        </div>
        <p v-if="profileSelected.id === 'default'" class="text-xs text-red-500">
          {{ $t('profilesTab.modals.editProfile.nameField.defaultWarning') }}
        </p>
      </div>

      <div class="flex flex-col gap-1">
        <label for="edit-description" class="font-semibold">
          {{ $t('profilesTab.modals.editProfile.descriptionField.label') }}
        </label>
        <div class="h-10">
          <Input
            id="edit-description"
            autocomplete="off"
            :placeholder="$t('profilesTab.modals.editProfile.descriptionField.placeholder')"
            :model-value="profileSelected.description ?? ''"
            @update:model-value="val => { if (profileSelected) profileSelected.description = val }"
          />
        </div>
      </div>

    </div>

    <template #footer>
      <div class="flex justify-end gap-2 p-2">
        <Button
          type="button"
          :label="$t('common.actions.cancel')"
          @click="visible = false"
          variant="default"
        />
        <Button
          type="button"
          :label="$t('profilesTab.modals.editProfile.actions.saveChanges')"
          @click="save"
          variant="primary"
        />
      </div>
    </template>
  </Modal>
</template>