<script setup lang="ts">
import { computed, MaybeRef } from 'vue'
import type { Component } from 'vue';

const props = defineProps<{
  label?: MaybeRef<string>
  icon?: Component
  labelClass?: string
  iconClass?: string | object | Array<string | object>
  disabled?: boolean
  variant?: 'primary' | 'default' | 'text' | 'danger'
  size?: 'sm' | 'md' | 'lg'
}>()

const emit = defineEmits<{
  click: [event: MouseEvent]
}>()

async function handleClick(event: MouseEvent) {
  if (props.disabled) return
  emit('click', event)
}

const SIZES = {
  sm: 'h-7 px-2.5 text-xs rounded-sm gap-1.5',
  md: 'h-8 px-3 text-sm rounded-md gap-2',
  lg: 'h-12 px-4 text-sm rounded-lg gap-2',
}

const VARIANTS = {
  primary: 'bg-accent text-text-on-accent hover:bg-accent-hover active:bg-accent-active border-transparent',
  default:'bg-surface-input text-text-primary border-border-default active:bg-state-active hover:border-border-strong justify-center',
  text: 'bg-transparent text-text-primary hover:bg-state-hover border-transparent active:bg-state-active',
  danger: 'bg-error text-text-on-accent hover:text-text-on-accent border-error hover:border-transparent',
}

const classList = computed(() => [
    'inline-flex items-center font-medium border cursor-pointer transition-colors disabled:pointer-events-none disabled:opacity-50 whitespace-nowrap',
    SIZES[props.size ?? 'md'],
    VARIANTS[props.variant ?? 'default']
])
</script>

<template>
  <button v-bind="$attrs" @click="handleClick" :disabled="disabled" :class="classList">
    <component v-if="icon" :is="icon" :class="[iconClass, 'size-[1.1em]']" />
    <span v-if="label" :class="[labelClass, 'truncate']">{{ label }}</span>
    <slot />
  </button>
</template>

<style scoped></style>