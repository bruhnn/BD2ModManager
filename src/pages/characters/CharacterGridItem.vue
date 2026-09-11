<script setup lang="ts">
import { convertFileSrc } from '@tauri-apps/api/core'
import { CostumeWithMods } from './CharacterGrid.vue'
import { isCostumeNew } from '../../stores/characters'
import { Check, X } from '@lucide/vue'
import { computed } from 'vue'
import Image from '../../components/common/Image.vue'
import { formatCharName, useLang } from '../../utils/formatCharName.ts'

const props = defineProps<{
    costume: CostumeWithMods
}>()

const imageUrl = computed(() => {
    const ids = Array.isArray(props.costume.id)
        ? props.costume.id.join(',')
        : props.costume.id
    return convertFileSrc(`standing/${ids}`, "bd2assets")
})

const lang = useLang()

const charName = computed(() => {
    return formatCharName(props.costume, lang.value)
})
</script>

<template>
    <div @click="$emit('open-mod-details', costume)"
        class="rounded-lg cursor-pointer transition-all bg-surface-card text-text-primary hover:bg-state-hover flex flex-col h-full overflow-hidden">
        <div class="relative">
            <Image :src="imageUrl" :alt="charName" class="w-full aspect-square rounded-t-md"
                error-src="characters/standing/placeholder_character.png" skeleton error-class="bg-text-primary" />
            <div class="absolute top-2.5 left-2.5 flex gap-1">
                <div v-if="costume.modsCount > 0"
                    class="bg-accent/75 text-text-on-accent text-xs px-2 py-1 rounded-full font-medium">
                    {{ $t('charactersTab.tags.modsCount', { count: costume.modsCount }) }}
                </div>
                <div v-if="costume.is_collab"
                    class="bg-warning-bg text-warning text-xs px-2 py-1 rounded-full font-medium">
                    {{ $t('charactersTab.tags.collab') }}
                </div>
            </div>
        </div>

        <div class="px-2 py-2 flex flex-col shrink-0">
            <div class="mb-2">
                <div class="font-semibold text-sm min-w-0 flex gap-2 items-center"
                    :title="charName">
                    <div v-if="isCostumeNew(costume)"
                        class="bg-error-bg text-error text-xs px-2 py-0.5 rounded-sm font-medium shrink-0">
                        {{ $t('charactersTab.tags.new') }}
                    </div>
                    <span class="truncate">
                        {{ charName }}
                    </span>
                </div>
            </div>

            <div
                class="flex justify-around items-center gap-2 text-xs text-text-primary font-mono overflow-x-auto scrollbar-hide">
                <div class="text-center p-1">
                    <div class="mb-1 flex items-center font-semibold gap-1">
                        {{ $t('charactersTab.modTypes.cutscene') }}
                    </div>
                    <div class="flex items-center justify-center"
                        :class="costume.hasCutscene ? 'text-success font-bold' : 'text-error'">
                        <Check class="w-[1.25em] h-[1.25em]" v-if="costume.hasCutscene" />
                        <X class="w-[1.25em] h-[1.25em]" v-else />
                    </div>
                </div>

                <div class="text-center p-1">
                    <div class="mb-1 flex items-center font-bold gap-1">
                        {{ $t('charactersTab.modTypes.standing') }}
                    </div>
                    <div class="flex justify-center"
                        :class="costume.hasStanding ? 'text-success font-bold' : 'text-error'">
                        <Check class="w-[1.25em] h-[1.25em]" v-if="costume.hasStanding" />
                        <X class="w-[1.25em] h-[1.25em]" v-else />
                    </div>
                </div>

                <div class="text-center p-1" v-if="costume.dating_id">
                    <div class="mb-1 flex items-center font-bold gap-1">
                        {{ $t('charactersTab.modTypes.dating') }}
                    </div>
                    <div class="flex justify-center"
                        :class="costume.hasDating ? 'text-success font-bold' : 'text-error'">
                        <Check class="w-[1.25em] h-[1.25em]" v-if="costume.hasDating" />
                        <X class="w-[1.25em] h-[1.25em]" v-else />
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style></style>