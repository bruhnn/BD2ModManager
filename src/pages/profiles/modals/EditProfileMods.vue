<script setup lang="ts">
import { ref, computed } from 'vue'
import Button from '../../../components/common/Button.vue'
import Modal from '../../../components/common/Modal.vue'

interface EditProfileModsOptions {
  id: string
  name: string
  enabledMods: string[]
}

const visible = ref(false)
const profileSelected = ref<EditProfileModsOptions | null>(null)
// The editable text: one mod name per line.
const modsText = ref('')

defineExpose({
  show: (opts: EditProfileModsOptions) => {
    profileSelected.value = { ...opts }
    modsText.value = (opts.enabledMods ?? []).join('\n')
    visible.value = true
  }
})

const emit = defineEmits<{
  (e: 'on-profile-mods-edit', id: string, modNames: string[]): void
}>()

// Parse the textarea into a clean list: trim, normalize separators, drop blanks
// and duplicates while preserving order, then sort A-Z.
const parsedMods = computed(() => {
  const seen = new Set<string>()
  const result: string[] = []
  for (const raw of modsText.value.split('\n')) {
    const name = raw.trim().replace(/\\/g, '/')
    if (!name || seen.has(name)) continue
    seen.add(name)
    result.push(name)
  }
  // Sort alphabetically (case-insensitive)
  return result.sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }))
})

function save() {
  if (!profileSelected.value) return
  emit('on-profile-mods-edit', profileSelected.value.id, parsedMods.value)
  visible.value = false
}

function clearAll() {
  modsText.value = ''
}
</script>

<template>
  <Modal
    v-model:show="visible"
    class="min-w-120 max-w-200 max-h-[85%]"
    :title="$t('profilesTab.modals.editMods.title')"
    :subtitle="$t('profilesTab.modals.editMods.description')"
    @close="visible = false"
  >
    <div
      v-if="profileSelected"
      class="text-text-primary flex flex-col gap-3 p-4 min-h-0"
    >
      <div class="flex items-center justify-between gap-2">
        <label for="edit-mods" class="font-semibold">
          {{ $t('profilesTab.modals.editMods.field.label') }}
        </label>
        <span class="text-xs text-text-secondary">
          {{ $t('profilesTab.modals.editMods.count', { count: parsedMods.length }) }}
        </span>
      </div>

      <textarea
        id="edit-mods"
        v-model="modsText"
        spellcheck="false"
        autocomplete="off"
        class="w-full h-80 resize-none rounded-sm border border-border-default bg-surface-input
               text-text-primary text-sm font-mono p-3 leading-relaxed
               placeholder:text-text-secondary focus:outline-none focus:border-border-focus select-text"
        :placeholder="$t('profilesTab.modals.editMods.field.placeholder')"
      />

      <p class="text-xs text-text-secondary">
        {{ $t('profilesTab.modals.editMods.hint') }}
      </p>
    </div>

    <template #footer>
      <div class="flex justify-between gap-2 p-2">
        <Button
          type="button"
          :label="$t('profilesTab.modals.editMods.actions.clearAll')"
          @click="clearAll"
          variant="text"
        />
        <div class="flex gap-2">
          <Button
            type="button"
            :label="$t('common.actions.cancel')"
            @click="visible = false"
            variant="default"
          />
          <Button
            type="button"
            :label="$t('profilesTab.modals.editMods.actions.save')"
            @click="save"
            variant="primary"
          />
        </div>
      </div>
    </template>
  </Modal>
</template>
