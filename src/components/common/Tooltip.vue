<script setup lang="ts">
import { autoUpdate, offset, shift, useFloating } from '@floating-ui/vue';
import type { Placement } from '@floating-ui/vue';
import { computed, ref } from 'vue'

const props = defineProps<{
  text: string
  placement?: Placement
  backgroundColor?: string
  textColor?: string
}>()

const triggerRef = ref<HTMLElement | null>(null)
const tooltipRef = ref<HTMLElement | null>(null)
const isVisible = ref(false)
const isRendered = ref(false)
const { floatingStyles, isPositioned } = useFloating(triggerRef, tooltipRef, {
  open: isRendered,
  placement: computed(() => props.placement ?? 'top'),
  whileElementsMounted: autoUpdate,
  middleware: [offset(4), shift()],
})

let hideTimeout: ReturnType<typeof setTimeout> | null = null
let renderTimeout: ReturnType<typeof setTimeout> | null = null

const mergedStyles = computed(() => ({
  ...floatingStyles.value,
  backgroundColor: props.backgroundColor,
  borderColor: props.backgroundColor,
  color: props.textColor,
  visibility: isRendered.value && isPositioned.value ? 'visible' as const : 'hidden' as const,
  pointerEvents: 'none' as const,
}))

function show() {
  if (hideTimeout) { clearTimeout(hideTimeout); hideTimeout = null }
  if (renderTimeout) { clearTimeout(renderTimeout); renderTimeout = null }
  isRendered.value = true
  requestAnimationFrame(() => { isVisible.value = true })
}

function hide() {
  hideTimeout = setTimeout(() => {
    isVisible.value = false
    renderTimeout = setTimeout(() => { isRendered.value = false }, 150)
  }, 100)
}
</script>

<template>
  <div ref="triggerRef" class="relative inline-flex" @mouseenter="show" @mouseleave="hide" @focusin="show" @focusout="hide">
    <slot />
    <Teleport to="body">
      <div
        ref="tooltipRef"
        role="tooltip"
        :style="mergedStyles"
        class="z-9999 w-max max-w-xs rounded-md border border-border-default bg-bg-elevated text-text-primary px-3 py-2 text-sm shadow-lg transition-opacity duration-150"
        :class="isVisible && isPositioned ? 'opacity-100' : 'opacity-0'"
      >
        <span class="flex items-center gap-2">
          <slot name="icon" />
          <span class="whitespace-normal">{{ text }}</span>
        </span>
      </div>
    </Teleport>
  </div>
</template>
