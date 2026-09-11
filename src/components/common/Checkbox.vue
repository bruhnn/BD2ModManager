<script setup lang="ts">
import { computed } from "vue"
import { Check } from "@lucide/vue"

const props = defineProps<{
  modelValue: boolean
  label?: string
  description?: string
  disabled?: boolean
  icon?: any
}>()

const emit = defineEmits<{
  (event: "update:modelValue", value: boolean): void
}>()

const onChange = (event: Event) => {
  if (props.disabled) return
  emit("update:modelValue", (event.target as HTMLInputElement).checked)
}

const classList = computed(() => [
  "w-5 h-5 rounded-sm flex items-center justify-center border border-border-default transition-all duration-150 ease-in-out focus:outline-none shrink-0",
  props.modelValue ? "bg-accent text-text-on-accent border-transparent!" : "bg-surface-input",
  !props.disabled && !props.modelValue? "hover:border-border-strong hover:bg-state-hover focus:border-border-focus": "",
  props.disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"
])

const id = `checkbox-${Math.random().toString(36).substring(2, 9)}`
</script>

<template>
  <label
    class="flex items-center gap-2 select-none"
    :class="{ 'cursor-not-allowed': disabled, 'cursor-pointer': !disabled }"
    data-checkbox
    :for="id"
  >
    <input
      type="checkbox"
      class="sr-only peer"
      :checked="modelValue"
      :disabled="disabled"
      @change="onChange"
      :id="id"
    />

    <!-- // checkbox  -->
    <div :class="classList">
      <Transition
        enter-active-class="transition transform duration-150 ease-out"
        enter-from-class="scale-50 opacity-0"
        enter-to-class="scale-100 opacity-100"
        leave-active-class="transition transform duration-100 ease-in"
        leave-from-class="scale-100 opacity-100"
        leave-to-class="scale-50 opacity-0"
      >
        <component
          v-if="modelValue && icon"
          :is="icon"
          class="w-3.5 h-3.5 text-text-primary min-w-0 shrink-0"
        />

        <Check
          v-else-if="modelValue"
          class="w-3.5 h-3.5 text-text-on-accent min-w-0 shrink-0"
          stroke-width="3"
        />
      </Transition>
    </div>

    <span v-if="label" class="text-text-primary text-sm font-normal">
      {{ label }}
      <p v-if="description" class="text-xs text-text-secondary mt-1 font-normal">
        {{ description }}
      </p>
    </span>
  </label>
</template>