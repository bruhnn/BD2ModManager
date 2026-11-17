<script setup lang="ts">
import { Check } from '@lucide/vue'

defineProps<{
    title: string;
    paths: readonly string[];
    invalid?: readonly string[];
    current?: string | null;
    emptyText: string;
}>();

const emit = defineEmits<{
    select: [path: string];
}>();
</script>

<template>
    <div class="flex flex-col">
        <span class="px-3 pt-1.5 pb-0.5 text-xs text-text-muted">{{ title }}</span>
        <span v-if="paths.length === 0" class="px-3 py-1.5 text-xs text-text-secondary">{{ emptyText }}</span>
        <button v-for="path in paths" :key="path" type="button" role="menuitem"
            :disabled="invalid?.includes(path)"
            class="flex w-full items-center cursor-pointer gap-2 px-3 py-1.5 text-sm text-text-primary transition-colors hover:bg-state-hover disabled:pointer-events-none"
            :title="path" @click="emit('select', path)">
            <Check v-if="path === current" class="size-[1.1em] shrink-0 text-accent" />
            <span v-else class="size-[1.1em] shrink-0"></span>
            <span class="font-mono truncate" :class="{ 'text-text-muted': invalid?.includes(path) }">{{ path }}</span>
            <span v-if="invalid?.includes(path)" class="ml-auto pl-2 shrink-0 text-xs text-error">
                {{ $t('settingsTab.general.sections.directories.invalid') }}
            </span>
        </button>
    </div>
</template>
