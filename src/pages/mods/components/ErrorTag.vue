<script setup lang="ts">
import { autoUpdate, offset, shift, useFloating } from '@floating-ui/vue';
import { computed, ref } from 'vue'

defineProps<{
  label: string
  description: string
}>()

const labelRef = ref<HTMLElement | null>(null)
const descriptionRef = ref<HTMLElement | null>(null)
const {
  floatingStyles
} = useFloating(labelRef, descriptionRef, {
  placement: 'top',
  whileElementsMounted: autoUpdate,
  middleware: [
    offset(4),
    shift()
  ],
})

const isVisible = ref(false)
const isRendered = ref(false)
let hideTimeout: ReturnType<typeof setTimeout> | null = null
let renderTimeout: ReturnType<typeof setTimeout> | null = null

const mergedStyles = computed(() => ({
  ...floatingStyles.value,
  visibility: isRendered.value ? 'visible' as const : 'hidden' as const,
  pointerEvents: isVisible.value ? 'auto' as const : 'none' as const,
}))

function show() {
  if (hideTimeout) {
    clearTimeout(hideTimeout)
    hideTimeout = null
  }
  if (renderTimeout) {
    clearTimeout(renderTimeout)
    renderTimeout = null
  }
  isRendered.value = true
  requestAnimationFrame(() => {
    isVisible.value = true
  })
}

function hide() {
  hideTimeout = setTimeout(() => {
    isVisible.value = false
    renderTimeout = setTimeout(() => {
      isRendered.value = false
    }, 150)
  }, 100)
}
</script>

<template>
  <div class="relative" @mouseenter="show" @mouseleave="hide">
    <div ref="labelRef" class="truncate rounded-md bg-error-bg text-error px-2 py-1 text-xs font-medium border border-transparent transition-colors">
      {{ label }}
    </div>
    <teleport to="body">
      <div ref="descriptionRef" :style="mergedStyles" class=" z-9999 w-max max-w-xs rounded-md border border-border-default bg-surface-popover text-text-primary px-3 py-2 text-sm shadow-lg transition-all duration-150" :class="isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-1'"
        @mouseenter="show" @mouseleave="hide">
        {{ description }}
      </div>
    </teleport>
  </div>
</template>