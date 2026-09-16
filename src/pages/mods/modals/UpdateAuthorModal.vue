<script setup lang="ts">
import { ref, computed } from 'vue';
import Modal from '../../../components/common/Modal.vue';
import Button from '../../../components/common/Button.vue';
import Input from '../../../components/common/Input.vue';

const visible = ref(false)
const mods = ref<{ name: string; author: string }[]>([])
const on_save = ref<((newAuthor: string) => void) | undefined>(undefined)
const newModAuthor = ref('')

const isMultiple = computed(() => mods.value.length > 1)

defineExpose({
    open(payload: {
        mods: { name: string; author: string }[];
        onSave?: (newAuthor: string) => void;
    }) {
        visible.value = true;
        mods.value = payload.mods;
        newModAuthor.value = !isMultiple.value ? payload.mods[0].author : '';
        on_save.value = payload.onSave;
    }
});

function saveChanges() {
    on_save.value?.(newModAuthor.value);
    visible.value = false;
}

function cancel() {
    visible.value = false;
    mods.value = [];
    newModAuthor.value = '';
}
</script>

<template>
    <Modal v-model:show="visible" @close="visible = false"
        :title="$t('modsTab.modals.changeModAuthor.title')"
        :subtitle="isMultiple
            ? $t('modsTab.modals.changeModAuthor.descriptionMultiple', { count: mods.length })
            : $t('modsTab.modals.changeModAuthor.description', { modName: mods[0]?.name })">
        <template #footer>
            <div class="flex justify-end space-x-2 p-2">
                <Button variant="default" @click="cancel">{{ $t('common.actions.cancel') }}</Button>
                <Button variant="primary" @click="saveChanges">{{ $t('common.actions.save') }}</Button>
            </div>
        </template>

        <div class="p-4 flex flex-col gap-4">
            <div v-if="!isMultiple">
                <p class="text-md text-primary mb-1 font-bold">{{ $t('modsTab.modals.changeModAuthor.labels.modName') }}</p>
                <p class="font-medium text-sm truncate text-primary">{{ mods[0]?.name }}</p>
            </div>

            <div>
                <label for="newModAuthor" class="block text-sm font-medium text-primary">{{
                    $t('modsTab.modals.changeModAuthor.labels.newAuthor') }}</label>
                <div class="h-10">
                    <Input id="newModAuthor" class="w-full h-full" :model-value="newModAuthor" @update:model-value="val => newModAuthor = val"
                        :placeholder="!isMultiple ? mods[0]?.author : $t('modsTab.modals.changeModAuthor.placeholder')" />
                </div>
            </div>
        </div>
    </Modal>
</template>
