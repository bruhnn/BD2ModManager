<script lang="ts" setup>
import { computed } from 'vue'
import { Check, Filter, SearchIcon } from '@lucide/vue'
import Input from '../../components/common/Input.vue'
import Button from '../../components/common/Button.vue'
import Checkbox from '../../components/common/Checkbox.vue'
import Popover from '../../components/common/Popover.vue'
import { usePreferencesStore } from '../../stores/preferences.ts'

const preferencesStore = usePreferencesStore()

export type FilterKey = 'enabled' | 'disabled' | 'conflicts' | 'errors' | 'managed' | 'unmanaged'

interface Filters {
    searchQuery: string
    // searchType: string
    modTypes: string[]
    include: FilterKey[]
    exclude: FilterKey[]
}

defineProps<{
    filterCounts: Record<FilterKey, number>
}>()

const filters = defineModel<Filters>('filters', {
    default: () => ({
        searchQuery: '',
        modTypes: [],
        include: [],
        exclude: [],
    }),
})

const activeFilterCount = computed(() => filters.value.include.length + filters.value.exclude.length)

const FILTER_CATEGORIES: { name: 'status' | 'issues' | 'source'; keys: FilterKey[] }[] = [
    { name: 'status', keys: ['enabled', 'disabled'] },
    { name: 'issues', keys: ['conflicts', 'errors'] },
    { name: 'source', keys: ['managed', 'unmanaged'] },
]

function setFilter(list: 'include' | 'exclude', key: FilterKey, checked: boolean) {
    const other = list === 'include' ? 'exclude' : 'include'
    filters.value[list] = filters.value[list].filter((k) => k !== key)
    if (checked) {
        filters.value[list].push(key)
        filters.value[other] = filters.value[other].filter((k) => k !== key)
    }
}

function resetFilters() {
    filters.value.include = []
    filters.value.exclude = []
}

const modTypes = ['Cutscene', 'Standing', 'Scene', 'Dating', 'NPC', 'Minigame']

function toggleModTypes(modType: string) {
    let index = filters.value.modTypes.indexOf(modType)

    if (index == -1) {
        filters.value.modTypes.push(modType)
    } else {
        filters.value.modTypes.splice(index, 1)
    }
}

function getModTypeClass(modType: string) {
    if (!preferencesStore.enableModTypeColors) {
        return 'bg-accent! text-text-on-accent! border-transparent!'
    }
    switch (modType) {
        case 'Cutscene':
            return 'text-mod-cutscene! bg-mod-cutscene-bg! border-transparent!'
        case 'Standing':
            return 'text-mod-standing! bg-mod-standing-bg! border-transparent!'
        case 'Scene':
            return 'text-mod-scene! bg-mod-scene-bg! border-transparent!'
        case 'Dating':
            return 'text-mod-dating! bg-mod-dating-bg! border-transparent!'
        case 'NPC':
            return 'text-mod-npc! bg-mod-npc-bg! border-transparent!'
        case 'Minigame':
            return 'text-mod-minigame! bg-mod-minigame-bg! border-transparent!'
        default:
            return ''
    }
}

// [TODO]: Add filters to search; character:value, author:value, modname:value
</script>

<template>
    <div class="flex flex-col justify-between items-stretch gap-2">
        <div class="flex items-stretch">
            <!-- Search -->
            <div class="flex flex-1 gap-2">
                <Popover placement="bottom-start">
                    <template #trigger="{ isOpen, open, close }">
                        <Button
                            :icon="Filter"
                            :label="$t('modsTab.header.actions.filters')"
                            :class="{ 'border-accent! bg-accent-muted! ring-1 ring-inset ring-accent': activeFilterCount > 0 }"
                            @click="isOpen ? close() : open()"
                        >
                            <span
                                v-if="activeFilterCount > 0"
                                class="rounded-full bg-accent-muted text-accent text-[11px] leading-4 px-1.5 tabular-nums"
                            >
                                {{ activeFilterCount }}
                            </span>
                        </Button>
                    </template>

                    <template #default>
                        <div class="flex flex-col w-80 bg-surface-popover border-border-default border rounded-md">
                            <div class="flex justify-between items-center py-2 pl-4 pr-3 border-b border-border-default font-semibold">
                                {{ $t('modsTab.header.advancedFilters.title') }}
                                <button
                                    class="text-xs font-medium text-text-secondary hover:text-text-primary cursor-pointer focus:outline-none"
                                    @click="resetFilters"
                                >
                                    {{ $t('modsTab.header.advancedFilters.reset') }}
                                </button>
                            </div>

                            <div class="grid grid-cols-[1fr_56px_56px] items-center gap-y-1 px-4 py-2.5">
                                <template
                                    v-for="(category, index) in FILTER_CATEGORIES"
                                    :key="category.name"
                                >
                                    <div
                                        v-if="index > 0"
                                        class="col-span-full h-px bg-border-default mt-1.5"
                                    ></div>
                                    <span class="text-xs font-semibold text-text-secondary pt-1.5">
                                        {{ $t(`modsTab.header.advancedFilters.categories.${category.name}`) }}
                                    </span>
                                    <template v-if="index === 0">
                                        <span class="text-xs font-semibold text-text-secondary pt-1.5 text-center">
                                            {{ $t('modsTab.header.advancedFilters.include') }}
                                        </span>
                                        <span class="text-xs font-semibold text-text-secondary pt-1.5 text-center">
                                            {{ $t('modsTab.header.advancedFilters.exclude') }}
                                        </span>
                                    </template>
                                    <template v-else>
                                        <span></span>
                                        <span></span>
                                    </template>

                                    <template
                                        v-for="key in category.keys"
                                        :key="key"
                                    >
                                        <span class="flex items-center gap-2 h-6.5 text-sm text-text-primary">
                                            {{ $t(`modsTab.header.advancedFilters.options.${key}`) }}
                                            <span class="text-xs text-text-secondary tabular-nums">
                                                {{ filterCounts[key] }}
                                            </span>
                                        </span>
                                        <div class="flex justify-center">
                                            <Checkbox
                                                :model-value="filters.include.includes(key)"
                                                @update:model-value="setFilter('include', key, $event)"
                                            />
                                        </div>
                                        <div class="flex justify-center">
                                            <Checkbox
                                                :model-value="filters.exclude.includes(key)"
                                                @update:model-value="setFilter('exclude', key, $event)"
                                            />
                                        </div>
                                    </template>
                                </template>
                            </div>
                        </div>
                    </template>
                </Popover>
                <div class="flex-1">
                    <Input
                        v-model="filters.searchQuery"
                        :icon-left="SearchIcon"
                        clearable
                        size="md"
                        :placeholder="$t('modsTab.header.searchPlaceholder')"
                    />
                </div>
            </div>
        </div>
        <!-- :class="{
            'bg-accent! text-text-on-accent!': filters.modTypes.includes(modType),
        }" -->
        <div class="flex justify-between items-center gap-2">
            <div class="flex gap-2">
                <button
                    v-for="modType in modTypes"
                    :key="modType"
                    @click="toggleModTypes(modType)"
                    class="text-xs transition-all focus:outline-none bg-surface-input border-border-default cursor-pointer capitalize items-center flex border font-semibold rounded-full py-1 px-2 active:scale-[1] active:bg-state-active disabled:pointer-events-none disabled:opacity-50"
                    :class="[filters.modTypes.includes(modType) ? getModTypeClass(modType) : 'hover:bg-state-hover! text-text-secondary']"
                >
                    <span
                        class="overflow-hidden transition-all duration-150"
                        :class="filters.modTypes.includes(modType) ? 'w-4 mr-1' : 'w-0'"
                    >
                        <Transition
                            enter-active-class="transition-all duration-150"
                            enter-from-class="opacity-0 scale-50"
                            enter-to-class="opacity-100 scale-100"
                            leave-active-class="transition-all duration-100"
                            leave-from-class="opacity-100 scale-100"
                            leave-to-class="opacity-0 scale-50"
                        >
                            <Check
                                v-if="filters.modTypes.includes(modType)"
                                class="w-4 h-4 shrink-0"
                                :stroke-width="2"
                            />
                        </Transition>
                    </span>
                    {{ $t(`common.modTypes.${modType.toLowerCase()}`) }}
                </button>
            </div>
        </div>
    </div>
</template>
