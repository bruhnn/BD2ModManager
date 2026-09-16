<script setup>
import { ref, computed, watch, useTemplateRef } from "vue"
import { Listbox, ListboxButton, ListboxOptions, ListboxOption } from "@headlessui/vue"
import { ChevronsUpDownIcon, Check } from "@lucide/vue"
import { flip, offset, shift, size as floatingSize, useFloating } from "@floating-ui/vue"

const props = defineProps({
    modelValue: {
        type: String,
        default: null
    },
    options: {
        type: Array,
        required: true // format: [{ label: 'Light', value: 'light', disabled: true }]
    },
    placeholder: {
        type: String,
        default: "Select an option"
    },
    disabled: {
        type: Boolean,
        default: false
    },
    multiple: {
        type: Boolean,
        default: false
    },
    size: {
        type: String,
        default: "md" // 'sm', 'md', 'lg'
    }
})

const emit = defineEmits(["update:modelValue"])

const internalValue = ref(props.modelValue)

watch(
    () => props.modelValue,
    (val) => {
        internalValue.value = val
    }
)

const updateValue = (val) => {
    emit("update:modelValue", val)
}

const selectedLabel = computed(() => {
    const found = props.options?.find((o) => o.value === internalValue.value)
    return found ? found.label : props.placeholder
})

const reference = useTemplateRef("reference")
const floating = useTemplateRef("floating")
const { floatingStyles } = useFloating(reference, floating, {
    placement: "bottom-start",
    // strategy: "fixed",
    middleware: [
        offset(4),
        flip(),
        shift({ padding: 4 }),
        floatingSize({
            apply({ elements, availableHeight }) {
                Object.assign(elements.floating.style, {
                    maxHeight: `${availableHeight}px`
                })
            },
            padding: 4
        })
    ]
})

// [TODO] fix listboxoptions showing on bottom then moving up

const SIZES = {
    sm: 'h-7 px-2.5 text-xs rounded-sm',
    md: 'h-8 px-3 text-sm rounded-sm',
    lg: 'h-12 px-4 text-sm rounded-lg',
}

const classList = computed(() => [
    'relative pr-8 w-full cursor-pointer border border-border-default bg-surface-input text-left text-text-primary transition-colors duration-200 focus:outline-none focus:ring-0',
    SIZES[props.size ?? 'md']
])
</script>

<template>
    <Listbox v-model="internalValue" @update:model-value="updateValue" :multiple="multiple" :disabled="disabled">
        <div class="relative">
            <ListboxButton ref="reference" :class="classList">
                <span v-if="multiple">
                    <span v-if="Array.isArray(internalValue) && internalValue.length > 0" class="block truncate">
                        {{internalValue.map(v => {
                            const found = options.find(o => o.value === v)
                            return found ? found.label : v
                        }).join(', ')}}
                    </span>
                    <span v-else class="block truncate text-text-secondary">
                        {{ placeholder }}
                    </span>
                </span>
                <span v-else class="block truncate">
                    {{ selectedLabel }}
                </span>
                <span class="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2">
                    <ChevronsUpDownIcon class="h-4 w-4 text-text-primary opacity-60" />
                </span>
            </ListboxButton>

            <transition enter-active-class="transition duration-200 ease-out" enter-from-class="opacity-0 scale-95"
                enter-to-class="opacity-100 scale-100" leave-active-class="transition duration-150 ease-in"
                leave-from-class="opacity-100 scale-100" leave-to-class="opacity-0 scale-95">
                <ListboxOptions ref="floating" :style="floatingStyles"
                    class="w-full min-h-0 z-9998 max-h-screen overflow-y-auto rounded-sm border border-border-default bg-surface-popover shadow-lg focus:outline-none">
                    <div v-if="options?.length == 0" class="text-text-secondary text-xs p-2 text-cnter">
                        {{ $t("common.messages.selectEmptyState") }}
                    </div>
                    <ListboxOption v-else v-for="option in options" :key="option.value" :value="option.value"
                        v-slot="{ selected }" :disabled="option.disabled">
                        <li class="relative cursor-pointer select-none py-2 pl-10 pr-4 text-text-primary text-sm hover:bg-state-hover"
                            :class="{ 'bg-state-selected!': selected, 'opacity-50 cursor-not-allowed': option.disabled }">
                            <span :class="[selected ? 'font-semibold' : 'font-medium', 'block truncate']">
                                {{ option.label }}
                            </span>
                            <span v-if="selected" class="absolute inset-y-0 left-0 flex items-center pl-3 text-accent">
                                <Check class="h-4 w-4" />
                            </span>
                        </li>
                    </ListboxOption>
                </ListboxOptions>
            </transition>
        </div>
    </Listbox>
</template>

<style scoped></style>