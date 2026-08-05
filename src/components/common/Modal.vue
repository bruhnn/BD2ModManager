<script setup lang="ts">
import { TransitionRoot, TransitionChild, Dialog, DialogPanel } from '@headlessui/vue'
import { XIcon } from '@lucide/vue';

defineOptions({ inheritAttrs: false });

const show = defineModel('show', {
  type: Boolean,
  required: true,
});

const props = withDefaults(
  defineProps<{
    title?: string,
    subtitle?: string,
    overlay?: boolean,
    closeOnEscape?: boolean
  }>(),
  {
    overlay: true,
    closeOnEscape: true
  }
);

defineEmits(["close"])
</script>

<template>
  <TransitionRoot :show="show" as="template" enter="duration-300 ease-out" enter-from="opacity-0" enter-to="opacity-100"
    leave="duration-200 ease-in" leave-from="opacity-100" leave-to="opacity-0">
    <Dialog as="div" class="relative z-10" @close="props.closeOnEscape ? $emit('close') : null"
      :close-on-escape="closeOnEscape">
      <TransitionChild v-if="overlay" as="template" enter="ease-out duration-300" enter-from="opacity-0"
        enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
        <div class="fixed inset-0 bg-black/30" />
      </TransitionChild>

      <div class="fixed inset-0 flex w-screen items-center justify-center">
        <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95"
          enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100"
          leave-to="opacity-0 scale-95">
          <DialogPanel :class="[
            'flex flex-col mx-4 rounded-xl overflow-hidden bg-surface-dialog border border-border-default max-h-[90vh]',
            $attrs.class
          ]">
            <div v-if="!$slots.header" class="flex flex-col p-4 gap-2 border-b border-border-default shrink-0">
              <div class="flex items-center justify-between" data-tauri-drag-region>
                <h2 v-if="title && !$slots.header" class="text-lg font-bold text-text-primary" data-tauri-drag-region>{{ title }}</h2>
                <XIcon v-if="show" @click="$emit('close')"
                  class="text-text-primary size-5 hover:text-accent! cursor-pointer" />
              </div>
              <p v-if="subtitle && !$slots.header" class="text-sm text-text-secondary">{{ subtitle }}</p>
            </div>

            <div v-else class="shrink-0" data-tauri-drag-region>
              <slot name="header" />
            </div>

            <div class="bg-surface-dialog flex flex-col flex-1 min-h-0 overflow-y-auto">
              <slot />
            </div>

            <div v-if="$slots.footer" class="bg-surface-dialog border-t border-border-default shrink-0">
              <slot name="footer" />
            </div>
          </DialogPanel>
        </TransitionChild>
      </div>
    </Dialog>
  </TransitionRoot>
</template>