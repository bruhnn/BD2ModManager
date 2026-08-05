<script setup lang="ts">
import { X } from '@lucide/vue';
import { confirmState } from '../../plugins/ConfirmService';
import { ref, watch } from 'vue';
import { TransitionChild, TransitionRoot } from '@headlessui/vue';
import Button from './Button.vue';
import Checkbox from './Checkbox.vue';

const state = confirmState;
const rememberChoice = ref(false);

watch(() => state.visible, (visible) => {
  if (visible) {
    rememberChoice.value = false;
  }
});

const accept = () => {
  state.resolve?.(true, rememberChoice.value);
  state.visible = false;
};

const reject = () => {
  state.resolve?.(false, rememberChoice.value);
  state.visible = false;
};
</script>

<template>
  <teleport to="body">
    <TransitionRoot appear :show="state.visible" as="template">
      <div class="relative text-text-primary z-50">
        <TransitionChild as="template" enter="duration-150 ease-out" enter-from="opacity-0" enter-to="opacity-100"
          leave="duration-150 ease-in" leave-from="opacity-100" leave-to="opacity-0">
          <div class="fixed inset-0 bg-black/25 backdrop-blur-xs" />
        </TransitionChild>

        <div class="inset-0 fixed flex justify-center items-center">
          <TransitionChild enter="ease-out duration-150" enter-from="opacity-0 scale-95"
            enter-to="opacity-100 scale-100" leave="ease-in duration-150" leave-from="opacity-100 scale-100"
            leave-to="opacity-0 scale-95" as="template">
            <div class="bg-surface-dialog p-2.5 rounded-md border border-border-default shadow-lg min-w-80 max-w-120">
              <div class="flex justify-between items-center" data-tauri-drag-region>
                <div v-if="state.title" class="flex items-center gap-2">
                  <component v-if="state.icon" :is="state.icon" class="inline-block w-[1.5em] h-[1.5em]" />
                  <h1 class="font-medium text-lg">{{ state.title }}</h1>
                </div>
                <span v-else></span>
                <span>
                  <X @click="reject"
                    class="text-text-primary hover:text-accent-hover! w-[1.5em] h-[1.5em] transition-colors cursor-pointer" />
                </span>
              </div>

              <p class="py-4 text-base text-text-primary">{{ state.message }}</p>

              <div class="flex justify-between items-center">
                <Checkbox v-if="state.showRememberChoice" v-model="rememberChoice" input-id="remember-choice"
                  :label="$t('modals.confirmation.rememberChoice')" />


                <div class="flex flex-1 justify-end gap-2 overflow-hidden">
                  <Button @click="reject" variant="text">
                    {{ state.rejectButton?.label }}
                  </Button>
                  <Button @click="accept" variant="primary">
                    {{ state.acceptButton?.label }}
                  </Button>
                </div>
              </div>
            </div>
          </TransitionChild>
        </div>
      </div>
    </TransitionRoot>
  </teleport>
</template>