<script setup lang="ts">
import { ChevronDown } from '@lucide/vue'
import { computed } from 'vue'
import Popover from './Popover.vue'

const props = defineProps<{
  label?: string
  icon?: any
  labelClass?: string
  iconClass?: string | object | Array<string | object>
  disabled?: boolean
  size?: 'sm' | 'md' | 'lg'
  variant?: 'primary' | 'default'
  actions: Array<{
    label: string
    icon?: any
    disabled?: boolean
    clicked: () => void
  }>
}>()

const emit = defineEmits<{
  click: [e: MouseEvent]
}>()

function handleClick(event: MouseEvent) {
  if (props.disabled) return
  emit('click', event)
}

function handleActionClick(close: () => void, action: (typeof props.actions)[number]) {
  if (action.disabled) return
  close()
  action.clicked()
}

const SIZES = {
  sm: { button: 'h-7 px-2.5 text-xs gap-1.5 rounded-l-sm', chevron: 'h-7 w-6 rounded-r-sm' },
  md: { button: 'h-8 px-3 text-sm gap-2 rounded-l-md', chevron: 'h-8 w-7 rounded-r-md' },
  lg: { button: 'h-12 px-4 text-sm gap-2 rounded-l-lg', chevron: 'h-12 w-10 rounded-r-lg' },
}

const VARIANTS = {
  primary: 'bg-accent hover:bg-accent-hover active:bg-accent-active text-text-on-accent border-transparent',
  default: 'bg-surface-input border-border-default text-text-primary hover:border-border-strong active:bg-state-active'
}

// [TODO] fix border on primary
const classList = computed(() => [
  'inline-flex items-center border font-medium cursor-pointer select-none transition-colors disabled:pointer-events-none disabled:opacity-50',
  VARIANTS[props.variant ?? 'default'],
  SIZES[props.size ?? 'md'].button
])
</script>

<template>
  <div class="inline-flex">
    <button type="button" :disabled="disabled" :class="classList" @click="handleClick">
      <component v-if="icon" :is="icon" :class="[iconClass, 'size-[1.1em] shrink-0']" />
      <span v-if="label" :class="[labelClass, 'truncate']">{{ label }}</span>
      <slot />
    </button>

    <!-- <div class="w-px bg-border-strong self-stretch" /> -->
    <!-- <div :class="['w-px self-stretch', dividerClass, size === 'sm' ? 'my-1' : 'my-1.5']" /> -->

    <Popover placement="bottom-end">
      <template #trigger="{ toggle, isOpen }">
        <button type="button" :disabled="disabled" :class="[
          'inline-flex items-center justify-center border font-medium cursor-pointer select-none transition-colors disabled:pointer-events-none disabled:opacity-50',
          VARIANTS[props.variant ?? 'default'],
          SIZES[props.size ?? 'md'].chevron
        ]" aria-haspopup="true" :aria-expanded="isOpen" @click="toggle">
          <ChevronDown class="size-[1em] transition-transform duration-150" :class="{ 'rotate-180': isOpen }"
            stroke-width="2.5" />
        </button>
      </template>


      <template #default="{ close }">
        <div class="min-w-40 rounded-md border border-border-default bg-surface-popover">
          <button v-for="(action, i) in actions" :key="i" type="button" :disabled="action.disabled" role="menuitem"
            class="flex w-full font-medium items-center cursor-pointer gap-2 px-3 py-1.5 text-sm text-text-primary transition-colors hover:bg-state-hover disabled:pointer-events-none disabled:opacity-50"
            @click="handleActionClick(close, action)">
            <component v-if="action.icon" :is="action.icon" class="size-[1.1em] shrink-0 text-text-secondary" />
            {{ action.label }}
          </button>
        </div>
      </template>
    </Popover>
  </div>
</template>