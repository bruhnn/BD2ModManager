<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useFloating, offset, flip, shift, autoUpdate } from '@floating-ui/vue'
import { ChevronRight } from 'lucide-vue-next'

export interface ContextMenuItem {
    label?: string
    key: string
    shortcut?: string
    type?: 'divider'
    children?: ContextMenuItem[]
    show?: boolean
}

const props = defineProps<{
    options: ContextMenuItem[]
    show: boolean
    x: number
    y: number
}>()

const emit = defineEmits<{
    select: [key: string]
    'update:show': [value: boolean]
}>()

const virtualRef = computed(() => ({
    getBoundingClientRect() {
        return {
            x: props.x,
            y: props.y,
            top: props.y,
            left: props.x,
            bottom: props.y,
            right: props.x,
            width: 0,
            height: 0,
        }
    },
}))

const floatingRef = ref<HTMLElement | null>(null)

const { floatingStyles } = useFloating(virtualRef, floatingRef, {
    whileElementsMounted: autoUpdate,
    placement: 'bottom-start',
    middleware: [offset(4), flip(), shift({ padding: 8 })],
})

const activeSubmenu = ref<string | null>(null)
const submenuParentRef = ref<HTMLElement | null>(null)
const submenuFloatingRef = ref<HTMLElement | null>(null)

const { floatingStyles: submenuStyles } = useFloating(submenuParentRef, submenuFloatingRef, {
    whileElementsMounted: autoUpdate,
    placement: 'right-start',
    middleware: [offset(4), flip(), shift({ padding: 8 })],
})

let submenuTimeout: ReturnType<typeof setTimeout> | null = null

function showSubmenu(key: string, el: HTMLElement) {
    if (submenuTimeout) {
        clearTimeout(submenuTimeout)
        submenuTimeout = null
    }
    submenuParentRef.value = el
    activeSubmenu.value = key
}

function hideSubmenu() {
    submenuTimeout = setTimeout(() => {
        activeSubmenu.value = null
    }, 100)
}

function cancelHideSubmenu() {
    if (submenuTimeout) {
        clearTimeout(submenuTimeout)
        submenuTimeout = null
    }
}

function handleSelect(key: string) {
    emit('select', key)
    emit('update:show', false)
    activeSubmenu.value = null
}

function handleClickOutside(event: MouseEvent) {
    if (!props.show) return
    const target = event.target as HTMLElement
    if (floatingRef.value?.contains(target)) return
    if (submenuFloatingRef.value?.contains(target)) return
    emit('update:show', false)
    activeSubmenu.value = null
}

function handleKeyDown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
        emit('update:show', false)
        activeSubmenu.value = null
    }
}

onMounted(() => {
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleKeyDown)
})

onBeforeUnmount(() => {
    document.removeEventListener('mousedown', handleClickOutside)
    document.removeEventListener('keydown', handleKeyDown)
})

watch(() => props.show, (val) => {
    if (!val) {
        activeSubmenu.value = null
    }
})
</script>

<template>
    <teleport to="body">
        <div v-show="show" ref="floatingRef" :style="floatingStyles"
            class="z-5 min-w-48 rounded-md border border-border-default bg-surface-popover py-1" @contextmenu.prevent>
            <template v-for="item in options" :key="item.key">
                <div v-if="item.type === 'divider'" class="my-0.5 h-px bg-border-default" />

                <div v-else-if="item.children"
                    class="flex cursor-pointer items-center justify-between px-3 py-1.5 text-sm hover:bg-state-hover transition-colors"
                    @mouseenter="showSubmenu(item.key, $event.currentTarget as HTMLElement)" @mouseleave="hideSubmenu">
                    <span>{{ item.label }}</span>
                    <ChevronRight class="ml-4 h-4 w-4 text-text-secondary" />
                </div>

                <div v-else
                    class="flex cursor-pointer items-center justify-between gap-4 px-3 py-1.5 text-sm hover:bg-state-hover transition-colors"
                    @click="handleSelect(item.key)">
                    <span>{{ item.label }}</span>
                    <span class="min-w-16 text-right text-xs text-text-secondary">{{ item.shortcut }}</span>
                </div>
            </template>
        </div>

        <div v-show="activeSubmenu !== null" ref="submenuFloatingRef" :style="submenuStyles"
            class="z-5 min-w-44 rounded-md border border-border-default bg-surface-popover py-1 shadow-lg"
            @mouseenter="cancelHideSubmenu" @mouseleave="hideSubmenu" @contextmenu.prevent>
            <template v-for="parent in options.filter(o => o.children)" :key="parent.key">
                <template v-if="activeSubmenu === parent.key">
                    <template v-for="child in parent.children" :key="child.key">
                        <div v-if="child.type === 'divider'" class="my-1 h-px bg-border-default" />
                        <div v-else
                            class="cursor-pointer px-3 py-1.5 text-sm hover:bg-state-hover transition-colors"
                            @click="handleSelect(child.key)">
                            {{ child.label }}
                        </div>
                    </template>
                </template>
            </template>
        </div>
    </teleport>
</template>