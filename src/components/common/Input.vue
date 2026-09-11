<script setup lang="ts">
import { TransitionRoot } from '@headlessui/vue'
import { X } from '@lucide/vue'
import { useAttrs, computed } from 'vue'

defineOptions({ inheritAttrs: false })

const searchQuery = defineModel<string>({ default: '' })

const props = defineProps<{
  placeholder?: string
  disabled?: boolean
  readonly?: boolean
  iconLeft?: any
  iconRight?: any
  clearable?: boolean
  label?: string
  hint?: string
  error?: boolean
  size?: 'sm' | 'md' | 'lg'
}>()

const emit = defineEmits<{
  (event: 'enter'): void
}>()

const attrs = useAttrs()

const SIZES = {
  sm: 'h-7 px-2.5 text-xs rounded-sm',
  md: 'h-8 px-3 text-sm rounded-sm',
  lg: 'h-12 px-4 text-sm rounded-sm',
}

const showClear = computed(
  () =>
    props.clearable &&
    typeof searchQuery.value === 'string' &&
    searchQuery.value.length > 0 &&
    !props.disabled &&
    !props.readonly
)

const showIconRight = computed(() => props.iconRight && !showClear.value)
</script>

<template>
  <div class="flex flex-col gap-1.5 w-full h-full">
    <div class="relative flex items-center w-full group h-full">
      <input
        v-model="searchQuery"
        v-bind="attrs"
        :placeholder="placeholder"
        :disabled="disabled"
        :readonly="readonly"
        :tabindex="readonly ? -1 : undefined"
        type="text"
        class="w-full transition-colors
               border bg-surface-input text-text-primary
               placeholder:text-text-secondary
               focus:outline-none
               disabled:opacity-50 disabled:cursor-not-allowed
               read-only:cursor-default"
        :class="[
          SIZES[size ?? 'md'],
          iconLeft  ? 'pl-7'  : '',
          (showIconRight || showClear) ? 'pr-7' : '',
          error
            ? 'border-error focus:border-error hover:border-error'
            : 'border-border-default hover:border-border-strong focus:border-border-focus',
        ]"
        @keydown.enter.prevent="emit('enter')"
      />

      <component
        v-if="iconLeft"
        :is="iconLeft"
        class="absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4
               text-text-secondary pointer-events-none
               transition-colors group-hover:text-text-primary"
      />

      <component
        v-if="showIconRight"
        :is="iconRight"
        class="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4
               text-text-secondary pointer-events-none
               transition-colors"
      />

      <TransitionRoot
        :show="showClear"
        enter="transition-opacity duration-75"
        enter-from="opacity-0"
        enter-to="opacity-100"
        leave="transition-opacity duration-150"
        leave-from="opacity-100"
        leave-to="opacity-0"
      >
        <X
          class="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4
                 text-text-secondary cursor-pointer
                 hover:text-text-primary transition-colors"
          @click="searchQuery = ''"
        />
      </TransitionRoot>
    </div>
  </div>
</template>