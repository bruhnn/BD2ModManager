<script setup lang="ts">
import { computed, useId } from "vue"

defineOptions({ inheritAttrs: false })

const props = withDefaults(defineProps<{
  modelValue?: number
  label?: string
  description?: string
  disabled?: boolean
  icon?: any
  min?: number
  max?: number
  step?: number
  suffix?: string
}>(), {
  min: 0,
  max: 100,
  step: 1
})

const emit = defineEmits<{
  (event: "update:modelValue", value: number): void
  (event: "change", value: number): void
}>()

const classList = computed(() => [
  "slider relative block w-full h-5 m-0 appearance-none bg-transparent focus:outline-none",
  props.disabled ? "cursor-not-allowed" : "cursor-pointer"
])

const id = `slider-${useId()}`
const value = computed(() => props.modelValue ?? props.min)
const progress = computed(() => props.max > props.min
  ? Math.min(100, Math.max(0, (value.value - props.min) / (props.max - props.min) * 100))
  : 0
)

const onInput = (event: Event) => {
  if (props.disabled) return
  emit("update:modelValue", (event.target as HTMLInputElement).valueAsNumber)
}

const onChange = (event: Event) => {
  if (props.disabled) return
  emit("change", (event.target as HTMLInputElement).valueAsNumber)
}

</script>

<template>
  <div
    class="grid w-full min-w-0 grid-cols-3 items-center gap-4 select-none"
    :class="$attrs.class"
    data-slider
  >
    <div v-if="label || description" class="flex items-start gap-2">
      <component v-if="icon" :is="icon" class="w-4 h-4 mt-0.5 text-text-secondary shrink-0" />
      <div class="min-w-0">
        <label
          v-if="label"
          :for="id"
          class="text-text-primary text-sm font-medium"
          :class="disabled ? 'cursor-not-allowed' : 'cursor-pointer'"
        >
          {{ label }}
        </label>
        <p v-if="description" :id="`${id}-description`" class="text-xs text-text-secondary font-normal">
          {{ description }}
        </p>
      </div>
    </div>

    <div
      class="flex min-w-0 items-center gap-1"
      :class="[label || description ? 'col-span-2' : 'col-span-3', { 'opacity-50': disabled }]"
    >
      <div class="relative min-w-0 flex-1">
        <div class="slider-track" aria-hidden="true">
          <div class="slider-range" :style="{ width: `${progress}%` }" />
        </div>
        <input
          v-bind="{ ...$attrs, class: undefined }"
          :id="id"
          type="range"
          :class="classList"
          :value="value"
          :min="min"
          :max="max"
          :step="step"
          :disabled="disabled"
          :aria-valuetext="suffix ? `${value} ${suffix}` : undefined"
          :aria-describedby="description ? `${id}-description` : $attrs['aria-describedby'] as string | undefined"
          @input="onInput"
          @change="onChange"
        />
      </div>
    </div>

  </div>
</template>

<style scoped>
.slider-track {
  position: absolute;
  top: calc(50% - 1.5px);
  left: 10px;
  right: 10px;
  height: 3px;
  border-radius: 6px;
  background: var(--border-strong);
}

.slider-range {
  height: 100%;
  border-radius: inherit;
  background: var(--accent);
}

.slider::-webkit-slider-runnable-track {
  height: 3px;
  background: transparent;
}

.slider::-moz-range-track {
  height: 3px;
  background: transparent;
}

.slider::-moz-range-progress {
  background: transparent;
}

.slider::-webkit-slider-thumb {
  appearance: none;
  box-sizing: border-box;
  width: 20px;
  height: 20px;
  margin-top: -8.5px;
  border: 2px solid var(--border-strong);
  border-radius: 50%;
  background: var(--surface-app);
  box-shadow: 0 1px 1px rgb(0 0 0 / 14%);
  transition: background-color 150ms ease-in-out;
}

.slider::-moz-range-thumb {
  box-sizing: border-box;
  width: 20px;
  height: 20px;
  border: 2px solid var(--border-strong);
  border-radius: 50%;
  background: var(--surface-app);
  box-shadow: 0 1px 1px rgb(0 0 0 / 14%);
  transition: background-color 150ms ease-in-out;
}

.slider:not(:disabled):hover::-webkit-slider-thumb {
  background: var(--surface-panel);
  cursor: grab;
}

.slider:not(:disabled):hover::-moz-range-thumb {
  background: var(--surface-panel);
  cursor: grab;
}

.slider:focus-visible::-webkit-slider-thumb {
  outline: 1px solid var(--accent);
  outline-offset: 2px;
}

.slider:focus-visible::-moz-range-thumb {
  outline: 1px solid var(--accent);
  outline-offset: 2px;
}
</style>
