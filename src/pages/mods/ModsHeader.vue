<script lang="ts" setup>
import { Check, Filter, SearchIcon } from 'lucide-vue-next'
import Input from '../../components/common/Input.vue'
import Button from '../../components/common/Button.vue'
import Checkbox from '../../components/common/Checkbox.vue'
import Popover from '../../components/common/Popover.vue'
import { usePreferencesStore } from '../../stores/preferences.ts'

const preferencesStore = usePreferencesStore()

interface Filters {
    searchQuery: string
    // searchType: string
    modTypes: string[]
    onlyEnabled: boolean
    onlyDisabled: boolean
    onlyConflicts: boolean
    onlyErrors: boolean
}

const filters = defineModel<Filters>("filters", {
    default: () => ({
        searchQuery: '',
        modTypes: [],
        onlyEnabled: false,
        onlyDisabled: false,
        onlyConflicts: false,
        onlyErrors: false,
    })
})

const modTypes = ["Cutscene", "Standing", "Scene", "Dating", "NPC", "Minigame"];

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
                <Popover placement="bottom-start" trigger="hover">
                    <template #trigger="{ isOpen, open, close }">
                        <Button :icon="Filter":label="$t('modsTab.header.actions.filters')"
                            @click="isOpen ? close() : open()" />
                    </template>

                    <template #default>
                        <div
                            class="flex flex-col min-w-80 bg-surface-popover border-border-default border p-4 py-0 pb-2 rounded-md">
                            <div class="font-semibold text-lg text-left py-2">
                                {{ $t('modsTab.header.advancedFilters.title') }}
                            </div>

                            <div class="flex flex-col gap-1 text-md">
                                <Checkbox v-model="filters.onlyEnabled"
                                    :label="$t('modsTab.header.advancedFilters.actions.onlyEnabledMods')" />
                                <Checkbox v-model="filters.onlyDisabled"
                                    :label="$t('modsTab.header.advancedFilters.actions.onlyDisabledMods')" />
                                <Checkbox v-model="filters.onlyConflicts"
                                    :label="$t('modsTab.header.advancedFilters.actions.onlyConflictsMods')" />
                                <Checkbox v-model="filters.onlyErrors"
                                    :label="$t('modsTab.header.advancedFilters.actions.onlyErrorsMods')" />
                            </div>
                        </div>
                    </template>
                </Popover>
                <div class="flex-1">
                    <Input v-model="filters.searchQuery" :icon-left="SearchIcon" clearable size="md"
                        :placeholder="$t('modsTab.header.searchPlaceholder')" />
                </div>

            </div>
        </div>
        <!-- :class="{
            'bg-accent! text-text-on-accent!': filters.modTypes.includes(modType),
        }" -->
        <div class="flex justify-between items-center gap-2 ">
            <div class="flex gap-2">
                <button v-for="modType in modTypes" :key="modType" @click="toggleModTypes(modType)"
                    class="text-xs transition-all focus:outline-none bg-surface-input border-border-default cursor-pointer capitalize items-center flex border font-semibold rounded-full py-1 px-2 active:scale-[1] active:bg-state-active disabled:pointer-events-none disabled:opacity-50"

                    :class="[filters.modTypes.includes(modType) ? getModTypeClass(modType) : 'hover:bg-state-hover! text-text-secondary']">
                    <span class="overflow-hidden transition-all duration-150"
                        :class="filters.modTypes.includes(modType) ? 'w-4 mr-1' : 'w-0'">
                        <Transition enter-active-class="transition-all duration-150"
                            enter-from-class="opacity-0 scale-50" enter-to-class="opacity-100 scale-100"
                            leave-active-class="transition-all duration-100" leave-from-class="opacity-100 scale-100"
                            leave-to-class="opacity-0 scale-50">
                            <Check v-if="filters.modTypes.includes(modType)" class="w-4 h-4 shrink-0"
                                :stroke-width="2" />
                        </Transition>
                    </span>
                    {{ $t(`common.modTypes.${modType.toLowerCase()}`) }}
                </button>
            </div>
        </div>
    </div>
</template>