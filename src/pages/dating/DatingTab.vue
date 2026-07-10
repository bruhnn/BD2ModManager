<script setup lang="ts">
import { Grid3X3, List, RefreshCcw } from 'lucide-vue-next';
import { computed, reactive, ref, onActivated, onDeactivated } from 'vue';
import { useLocalStorage } from '@vueuse/core';
import { useI18n } from 'vue-i18n';

import { Character, useCharactersStore } from '../../stores/characters';
import { BD2Mod, useModsStore } from '../../stores/mods';

import { useHeader } from '../../composables/useHeader';

import DatingGrid from './DatingGrid.vue';
import DatingModal from './modals/DatingModal.vue';
import Button from '../../components/common/Button.vue';
import Input from '../../components/common/Input.vue';
import Select from '../../components/common/Select.vue';
import Image from '../../components/common/Image.vue';
import { convertFileSrc } from '@tauri-apps/api/core';
import { formatCharName, useLang } from '../../utils/formatCharName';
import type { DatingCostume } from './DatingGrid.vue';

const { t } = useI18n();
const charactersStore = useCharactersStore();
const modsStore = useModsStore();

const viewMode = useLocalStorage('dating-view-mode', 'grid'); // 'grid' or 'list'
const lang = useLang();

const userFilters = reactive({
    searchQuery: '',
    sortBy: 'a-z',
    dating: 'any'
});

const sortOptions = computed(() => [
    { label: t('charactersTab.filters.sortBy.options.nameAsc'), value: 'a-z' },
    { label: t('charactersTab.filters.sortBy.options.nameDesc'), value: 'z-a' },
    { label: t('charactersTab.filters.sortBy.options.releaseAsc'), value: 'newest' },
    { label: t('charactersTab.filters.sortBy.options.releaseDesc'), value: 'oldest' },
    { label: t('charactersTab.filters.sortBy.options.modsDesc'), value: 'mods-desc' },
    { label: t('charactersTab.filters.sortBy.options.modsAsc'), value: 'mods-asc' },
]);

const modStatusOptions = computed(() => [
    { label: t('charactersTab.filters.modStatus.options.any'), value: 'any' },
    { label: t('charactersTab.filters.modStatus.options.enabled'), value: 'enabled' },
    { label: t('charactersTab.filters.modStatus.options.disabled'), value: 'disabled' }
]);

// Index dating mods by the character id they resolve to (via dating_id).
const datingIndex = computed(() => {
    type Mod = typeof modsStore.mods[number];
    const index = new Map<string, { enabled: boolean; mods: Mod[] }>();

    for (const mod of modsStore.mods) {
        if (!mod.modType || mod.modType.type !== 'Dating' || !('id' in mod.modType)) continue;

        const characterId = charactersStore.getCharacterIdByDatingId(mod.modType.id);
        if (!characterId) continue;

        let entry = index.get(characterId);
        if (!entry) {
            entry = { enabled: false, mods: [] };
            index.set(characterId, entry);
        }
        entry.mods.push(mod);
        if (mod.enabled) entry.enabled = true;
    }

    return index;
});

function idList(id: string | readonly string[]) {
    return Array.isArray(id) ? id : [id as string];
}

// Index installed Scene-typed mods (affection mods use the "specialillust"
// prefix, which the Rust classifier maps to the Scene type). Keyed by the
// Scene mod id, which matches an AffectionEntry.id in dating.json.
const affectionModIndex = computed(() => {
    const present = new Set<string>();
    const enabled = new Set<string>();
    for (const mod of modsStore.mods) {
        if (!mod.modType || mod.modType.type !== 'Scene' || !('id' in mod.modType)) continue;
        present.add(mod.modType.id);
        if (mod.enabled && !mod.errors.length) enabled.add(mod.modType.id);
    }
    return { present, enabled };
});

// Per-character affection status resolved via the labelled affection list from
// dating.json (keyed by dating_id).
function getAffectionStatus(char: Character) {
    if (!char.dating_id) return { total: 0, enabled: 0, hasAffection: false };
    const affection = charactersStore.getAffection(char.dating_id);
    const total = affection.length;
    const enabled = affection.filter(a => affectionModIndex.value.enabled.has(a.id)).length;
    return { total, enabled, hasAffection: enabled > 0 };
}

function hasDatingInstalled(id: string | readonly string[]) {
    return idList(id).some(i => datingIndex.value.get(i)?.enabled);
}

function getInstalledMods(id: string | readonly string[]) {
    return idList(id).flatMap(i => datingIndex.value.get(i)?.mods ?? []);
}

function getInstalledModsCount(id: string | readonly string[]) {
    return idList(id).reduce((sum, i) => sum + (datingIndex.value.get(i)?.mods.length ?? 0), 0);
}

// All characters that have a dating_id — shown even when no dating mods are
// installed, so the tab is never empty just because the user lacks mods.
const datingCharacters = computed(() => {
    return charactersStore.characters.filter(char => !!char.dating_id);
});

const totalModsCount = computed(() =>
    datingCharacters.value.reduce((sum, c) => sum + getInstalledModsCount(c.id), 0)
);
const enabledModsCount = computed(() =>
    datingCharacters.value.reduce((sum, c) =>
        sum + getInstalledMods(c.id).filter(m => m.enabled && !m.errors.length).length, 0)
);

const filteredCharacters = computed(() => {
    const search = userFilters.searchQuery.toLowerCase();
    return datingCharacters.value.filter(char => {
        if (search &&
            !char.character.toLowerCase().includes(search) &&
            !char.costume.toLowerCase().includes(search)
        ) return false;

        const enabled = hasDatingInstalled(char.id);
        if (userFilters.dating === 'enabled' && !enabled) return false;
        if (userFilters.dating === 'disabled' && enabled) return false;

        return true;
    });
});

const sortedCharacters = computed(() => {
    const arr = [...filteredCharacters.value];
    arr.sort((a, b) => {
        switch (userFilters.sortBy) {
            case 'a-z':
                return a.character.localeCompare(b.character) || a.costume.localeCompare(b.costume);
            case 'z-a':
                return b.character.localeCompare(a.character) || b.costume.localeCompare(a.costume);
            case 'newest':
                return new Date(b.release_date || 0).getTime() - new Date(a.release_date || 0).getTime();
            case 'oldest':
                return new Date(a.release_date || 0).getTime() - new Date(b.release_date || 0).getTime();
            case 'mods-desc':
                return getInstalledModsCount(b.id) - getInstalledModsCount(a.id);
            case 'mods-asc':
                return getInstalledModsCount(a.id) - getInstalledModsCount(b.id);
            default:
                return 0;
        }
    });
    return arr;
});

const datingGrid = computed<DatingCostume[]>(() =>
    sortedCharacters.value.map(costume => {
        const aff = getAffectionStatus(costume);
        return {
            ...costume,
            hasDating: hasDatingInstalled(costume.id),
            modsCount: getInstalledModsCount(costume.id),
            affectionEnabled: aff.enabled,
            affectionTotal: aff.total,
            hasAffection: aff.hasAffection
        };
    })
);

function listImageUrl(costume: Character) {
    const ids = Array.isArray(costume.id) ? costume.id.join(',') : costume.id;
    return convertFileSrc(`standing/${ids}`, 'bd2assets');
}

const showModal = ref(false);
const selectedCostume = ref<Character | null>(null);

function openModDetails(costume: Character) {
    selectedCostume.value = costume;
    showModal.value = true;
}

function toggleMod(mod: BD2Mod) {
    if (mod.enabled) {
        modsStore.disableMods([mod.name]);
    } else {
        modsStore.enableMods([mod.name]);
    }
}

function refreshData() {
    charactersStore.loadCharacters();
    charactersStore.loadDating();
    modsStore.discoverMods();
}

const scrollTop = ref(0);
const scrollContainer = ref<HTMLElement | null>(null);

onDeactivated(() => {
    if (scrollContainer.value) scrollTop.value = scrollContainer.value.scrollTop;
});
onActivated(() => {
    if (scrollContainer.value) scrollContainer.value.scrollTop = scrollTop.value;
});

useHeader({
    title: t('datingTab.title'),
    subtitle: computed(() =>
        t('datingTab.subtitle', {
            enabledModsCount: enabledModsCount.value,
            totalModsCount: totalModsCount.value
        })
    ),
    buttons: [
        { icon: RefreshCcw, label: t('common.actions.refreshMods'), action: refreshData },
    ]
});
</script>

<template>
    <div class="flex flex-row w-full h-full p-4 py-2 gap-4 bg-surface-app overflow-hidden">
        <div class="flex-1 min-h-0 overflow-hidden">
            <div v-if="datingGrid.length === 0" class="text-center py-12 text-text-secondary">
                <p class="text-lg">{{ t('datingTab.charactersNotFound') }}</p>
            </div>

            <DatingGrid v-else-if="viewMode === 'grid'" :items="datingGrid" @open-mod-details="openModDetails" />

            <!-- List view -->
            <div v-else ref="scrollContainer" class="h-full overflow-y-auto bg-surface-app">
                <div v-for="costume in datingGrid"
                    :key="Array.isArray(costume.id) ? costume.id.join('-') : (costume.id as string)"
                    @click="openModDetails(costume)"
                    class="flex bg-surface-card rounded-lg overflow-hidden cursor-pointer hover:bg-state-hover transition-colors mx-2 mb-2">
                    <div class="shrink-0">
                        <Image :src="listImageUrl(costume)" class="w-42 h-42 object-cover object-top rounded-t-md aspect-square"
                            error-src="characters/standing/placeholder_character.png" error-class="bg-text-primary" skeleton />
                    </div>
                    <div class="flex flex-col flex-1 p-2 min-w-0">
                        <div class="text-lg font-medium flex gap-2 items-center flex-wrap">
                            <span class="truncate">{{ formatCharName(costume, lang) }}</span>
                            <div v-if="costume.modsCount > 0"
                                class="flex bg-accent/75 text-text-on-accent text-xs px-2 py-1 rounded-full font-medium whitespace-nowrap">
                                {{ t('charactersTab.tags.modsCount', { count: costume.modsCount }) }}
                            </div>
                        </div>
                        <div class="flex flex-1 items-end gap-8 md:gap-12 mr-4 md:mr-8 mt-2">
                            <div class="flex flex-col items-center">
                                <span class="font-semibold text-sm md:text-base">{{ t('charactersTab.modTypes.dating') }}</span>
                                <span class="font-mono text-xs md:text-sm" :class="{
                                    'text-success': costume.hasDating,
                                    'text-error': !costume.hasDating
                                }">
                                    {{ costume.hasDating ? t('charactersTab.modTypes.states.enabled', 'Enabled') : t('charactersTab.modTypes.states.disabled', 'Disabled') }}
                                </span>
                            </div>
                            <div v-if="(costume.affectionTotal ?? 0) > 0" class="flex flex-col items-center">
                                <span class="font-semibold text-sm md:text-base">{{ t('datingTab.affection.title') }}</span>
                                <span class="font-mono text-xs md:text-sm" :class="{
                                    'text-success': costume.affectionEnabled === costume.affectionTotal,
                                    'text-warning': (costume.affectionEnabled ?? 0) > 0 && costume.affectionEnabled !== costume.affectionTotal,
                                    'text-error': (costume.affectionEnabled ?? 0) === 0
                                }">
                                    {{ costume.affectionEnabled }}/{{ costume.affectionTotal }}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div
            class="flex overflow-y-auto flex-col gap-2.5 items-start justify-start w-full max-w-[20%] min-w-50 p-2 bg-surface-panel rounded-md border border-border-default">
            <h1 class="text-lg font-bold text-text-primary flex flex-row justify-between items-center w-full">
                {{ t('charactersTab.filters.title') }}
                <div class="flex gap-1">
                    <Button @click="viewMode = 'grid'" :icon="Grid3X3" :icon-class="{
                        'text-accent': viewMode === 'grid',
                        'text-text-primary': viewMode !== 'grid',
                        'text-xs': true
                    }" />
                    <Button @click="viewMode = 'list'" :icon="List" :icon-class="{
                        'text-accent': viewMode === 'list',
                        'text-text-primary': viewMode !== 'list',
                        'text-xs': true
                    }" />
                </div>
            </h1>

            <div class="flex flex-col gap-4 w-full">
                <div class="min-h-10 w-full">
                    <Input v-model="userFilters.searchQuery" :placeholder="t('charactersTab.filters.searchPlaceholder')" class="w-64" />
                </div>

                <div class="flex flex-col gap-1.5">
                    <label class="text-sm font-semibold text-text-primary">{{ t('charactersTab.filters.sortBy.title') }}</label>
                    <Select v-model="userFilters.sortBy" :options="sortOptions" />
                </div>

                <div class="flex flex-col gap-1.5">
                    <label class="text-sm font-semibold text-text-primary">{{ t('charactersTab.filters.modStatus.hasDating') }}</label>
                    <Select v-model="userFilters.dating" :options="modStatusOptions" />
                </div>
            </div>
        </div>

        <DatingModal v-model:show="showModal" :selectedCostume="selectedCostume" :toggleMod="toggleMod" />
    </div>
</template>

<style scoped></style>
