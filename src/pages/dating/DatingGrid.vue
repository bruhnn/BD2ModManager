<script setup lang="ts">
import { computed, ref, watch, ComponentPublicInstance } from 'vue';
import { useVirtualizer } from '@tanstack/vue-virtual';
import { useResizeObserver } from '@vueuse/core';
import { Character } from '../../stores/characters';
import DatingGridItem from './DatingGridItem.vue';
import { useSaveScroll } from '../../composables/useSaveScroll';

export interface DatingCostume extends Character {
    hasDating?: boolean;
    modsCount: number;
    affectionEnabled?: number;
    affectionTotal?: number;
    hasAffection?: boolean;
}

const props = defineProps<{ items: DatingCostume[] }>();
defineEmits<{ 'open-mod-details': [costume: Character] }>();

const parentRef = ref<HTMLElement | null>(null);
const columnCount = ref(4);

function getColumnCount(width: number) {
    if (width >= 940) return 5;
    if (width >= 740) return 4;
    if (width >= 480) return 3;
    if (width >= 440) return 2;
    return 1;
}

useResizeObserver(parentRef, ([entry]) => {
    columnCount.value = getColumnCount(entry.contentRect.width);
});

const rows = computed(() => {
    const result: DatingCostume[][] = [];
    for (let i = 0; i < props.items.length; i += columnCount.value) {
        result.push(props.items.slice(i, i + columnCount.value));
    }
    return result;
});

const rowVirtualizer = useVirtualizer({
    get count() { return rows.value.length; },
    getScrollElement: () => parentRef.value,
    estimateSize: () => 340,
    overscan: 4,
    measureElement: (element, _entry, instance) => {
        const index = Number(element.getAttribute('data-index'));
        const cached = instance.measurementsCache[index]?.size;
        if (cached !== undefined) return cached;
        return element.getBoundingClientRect().height;
    },
});

watch(columnCount, () => {
    rowVirtualizer.value.measure();
});

const virtualRows = computed(() => rowVirtualizer.value.getVirtualItems());
const totalSize = computed(() => rowVirtualizer.value.getTotalSize());

const measureElement = (el: Element | ComponentPublicInstance | null) => {
    if (!el || !(el instanceof Element)) return;
    rowVirtualizer.value.measureElement(el);
};

useSaveScroll(rowVirtualizer)
</script>

<template>
    <div v-if="items.length === 0" class="text-center py-12 text-text-secondary">
        <p class="text-lg">{{ $t('datingTab.charactersNotFound') }}</p>
    </div>

    <div v-else ref="parentRef" class="h-full overflow-y-auto bg-surface-app" style="contain: strict">
        <div :style="{ height: `${totalSize}px`, width: '100%', position: 'relative' }">
            <div :style="{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                transform: `translateY(${virtualRows[0]?.start ?? 0}px)`,
            }">
                <div
                    v-for="virtualRow in virtualRows"
                    :key="String(virtualRow.key)"
                    :ref="measureElement"
                    :data-index="virtualRow.index"
                    class="grid gap-4 pb-4"
                    :style="{ gridTemplateColumns: `repeat(${columnCount}, minmax(0, 1fr))` }"
                >
                    <DatingGridItem
                        v-for="costume in rows[virtualRow.index]"
                        :key="Array.isArray(costume.id) ? costume.id.join('-') : costume.id as string"
                        :costume="costume"
                        @open-mod-details="$emit('open-mod-details', costume)"
                    />
                </div>
            </div>
        </div>
    </div>
</template>
