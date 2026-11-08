<script lang="ts">
let closeActiveTooltip: (() => void) | null = null
</script>

<script setup lang="ts">
import { arrow, autoUpdate, flip, offset, shift, useFloating } from '@floating-ui/vue';
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
const arrowRef = ref<HTMLElement | null>(null)
const { floatingStyles, isPositioned, middlewareData, placement: actualPlacement } = useFloating(triggerRef, tooltipRef, {
  open: isRendered,
  placement: computed(() => props.placement ?? 'top'),
  whileElementsMounted: autoUpdate,
  middleware: [offset(8), flip(), shift({ padding: 4 }), arrow({ element: arrowRef, padding: 6 })],
})

const arrowStyles = computed(() => {
  const { x, y } = middlewareData.value.arrow ?? {}
  const side = actualPlacement.value.split('-')[0] as 'top' | 'right' | 'bottom' | 'left'
  const staticSide = { top: 'bottom', right: 'left', bottom: 'top', left: 'right' }[side]
  return {
    left: x != null ? `${x}px` : '',
    top: y != null ? `${y}px` : '',
    [staticSide]: '-5px',
    borderWidth: {
      top: '0 1px 1px 0',
      bottom: '1px 0 0 1px',
      left: '0 0 1px 1px',
      right: '1px 1px 0 0',
    }[side],
    backgroundColor: props.backgroundColor,
    borderColor: props.backgroundColor,
  }
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

function hideNow() {
  if (hideTimeout) { clearTimeout(hideTimeout); hideTimeout = null }
  if (renderTimeout) { clearTimeout(renderTimeout); renderTimeout = null }
  isVisible.value = false
  isRendered.value = false
}

function show() {
  if (closeActiveTooltip && closeActiveTooltip !== hideNow) closeActiveTooltip()
  closeActiveTooltip = hideNow
  if (hideTimeout) { clearTimeout(hideTimeout); hideTimeout = null }
  if (renderTimeout) { clearTimeout(renderTimeout); renderTimeout = null }
  isRendered.value = true
  requestAnimationFrame(() => { isVisible.value = true })
}

function hide() {
  if (hideTimeout) clearTimeout(hideTimeout)
  if (renderTimeout) clearTimeout(renderTimeout)
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
        class="z-9999 w-max max-w-xs rounded-md border border-border-default bg-surface-popover text-text-primary px-3 py-2 text-sm shadow-lg transition-opacity duration-150"
        :class="isVisible && isPositioned ? 'opacity-100' : 'opacity-0'"
      >
        <span class="flex items-center gap-2">
          <slot name="icon" />
          <span class="whitespace-normal">{{ text }}</span>
        </span>
        <div
          ref="arrowRef"
          :style="arrowStyles"
          class="absolute size-2.5 rotate-45 border-solid border-border-default bg-surface-popover"
        />
      </div>
    </Teleport>
  </div>
</template>
