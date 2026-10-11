<script setup lang="ts">
import { autoUpdate, offset, shift, useFloating } from '@floating-ui/vue'
import { computed, ref, nextTick, onMounted, onBeforeUnmount, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  errors: string[]
}>()

const labelRef = ref<HTMLElement | null>(null)
const descriptionRef = ref<HTMLElement | null>(null)
const labelContentRef = ref<HTMLElement | null>(null)
const labelWidth = ref<number | null>(null)

const { floatingStyles } = useFloating(labelRef, descriptionRef, {
  placement: 'top',
  whileElementsMounted: autoUpdate,
  middleware: [
    offset(4),
    shift()
  ],
})

const { t } = useI18n()

const isVisible = ref(false)
const isRendered = ref(false)

let hideTimeout: ReturnType<typeof setTimeout> | null = null
let renderTimeout: ReturnType<typeof setTimeout> | null = null
let animationFrame: number | null = null

const labelText = computed(() =>
  isVisible.value
    ? props.errors.join(', ')
    : props.errors.length === 1
      ? props.errors[0]
      : `${props.errors[0]} + ${props.errors.length - 1}`
)

const mergedStyles = computed(() => ({
  ...floatingStyles.value,
  visibility: isRendered.value ? 'visible' as const : 'hidden' as const,
  pointerEvents: isVisible.value ? 'auto' as const : 'none' as const,
}))

async function updateLabelWidth() {
  await nextTick()

  if (labelContentRef.value) {
    labelWidth.value = labelContentRef.value.scrollWidth + 16
  }
}

function show() {
  if (hideTimeout) {
    clearTimeout(hideTimeout)
    hideTimeout = null
  }

  if (renderTimeout) {
    clearTimeout(renderTimeout)
    renderTimeout = null
  }

  if (animationFrame !== null) {
    cancelAnimationFrame(animationFrame)
  }

  isRendered.value = true

  animationFrame = requestAnimationFrame(() => {
    isVisible.value = true
  })
}

function hide() {
  if (hideTimeout) clearTimeout(hideTimeout)

  hideTimeout = setTimeout(() => {
    isVisible.value = false

    renderTimeout = setTimeout(() => {
      isRendered.value = false
    }, 150)
  }, 100)
}

watch(labelText, updateLabelWidth)

onMounted(updateLabelWidth)

onBeforeUnmount(() => {
  if (hideTimeout) clearTimeout(hideTimeout)
  if (renderTimeout) clearTimeout(renderTimeout)
  if (animationFrame !== null) cancelAnimationFrame(animationFrame)
})
</script>

<template>
  <div class="relative w-fit" @mouseenter="show" @mouseleave="hide">
    <div
      ref="labelRef"
      :style="{ width: labelWidth !== null ? `${labelWidth}px` : undefined }"
      class="box-border overflow-hidden whitespace-nowrap rounded-md bg-error-bg text-error px-2 py-1 text-xs font-medium transition-[width] duration-250 ease-in-out"
    >
      <span ref="labelContentRef" class="block w-max whitespace-nowrap">
        {{ labelText }}
      </span>
    </div>

    <teleport to="body">
      <div
        ref="descriptionRef"
        :style="mergedStyles"
        class="z-9999 w-max max-w-xs rounded-md border border-border-default bg-surface-popover text-text-primary py-2 text-sm shadow-lg transition-all duration-150"
        :class="isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-1'"
        @mouseenter="show"
        @mouseleave="hide"
      >
        <div class="flex flex-col gap-2">
          <template v-for="(error, index) in [...errors].reverse()" :key="index">
            <div class="flex items-center gap-2 px-3">
              <span class="text-left">
                {{ t(`modErrors.${error.charAt(0).toLowerCase() + error.slice(1)}`) }}
              </span>
            </div>

            <div
              v-if="index < errors.length - 1"
              class="h-px w-full bg-border-default"
            />
          </template>
        </div>
      </div>
    </teleport>
  </div>
</template>