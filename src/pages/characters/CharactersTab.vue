<script setup lang="ts">
import { Grid3X3, List, RefreshCcw, FolderPlus } from 'lucide-vue-next';

import { computed, defineComponent, h, nextTick, onActivated, onDeactivated, onMounted, reactive, ref, watch } from 'vue';
import { useLocalStorage } from '@vueuse/core';
import { useRoute } from 'vue-router';
import { useI18n } from 'vue-i18n';

import { Character, useCharactersStore } from '../../stores/characters';
import { BD2Mod, useModsStore } from '../../stores/mods';

import { useHeader } from '../../composables/useHeader';

import CharacterList from './CharacterList.vue';
import CharacterGrid from './CharacterGrid.vue';

import Button from '../../components/common/Button.vue';
import Input from '../../components/common/Input.vue';
import CharacterModal from './modals/CharacterModal.vue';
import Select from '../../components/common/Select.vue';
import Checkbox from '../../components/common/Checkbox.vue';
import { useModInstall } from '../../composables/useModInstall';
import Popover from '../../components/common/Popover.vue';
import { Language } from '../../stores/settings.ts';

const { t } = useI18n()
const route = useRoute()

const charactersStore = useCharactersStore()
const modsStore = useModsStore()

const totalModsCount = computed(() => modsStore.mods.length)
const enabledModsCount = computed(() => modsStore.mods.filter(mod => mod.enabled && !mod.errors.length).length)

const viewMode = useLocalStorage('characters-view-mode', 'grid') // 'grid' or 'list'

const userFilters = reactive({
    searchQuery: '',
    sortBy: 'a-z',
    cutscene: 'any',
    standing: 'any',
    dating: 'any',
    hideCollabCharacters: false,
    onlyCollabCharacters: false,
    hideMenCharacters: false,
    hideWomenCharacters: false,
    releasePeriod: 'all',
    onlyCharactersWithMods: false,
    onlyCharactersWithoutMods: false
})

const { installFromZip, installFromFolder } = useModInstall()

const addModMenuItems = computed(() => [
    { label: t('charactersTab.actions.installFromZip'), clicked: installFromZip },
    { label: t('charactersTab.actions.installFromFolder'), clicked: installFromFolder }
])

const sortOptions = computed(() => [
    { label: t('charactersTab.filters.sortBy.options.nameAsc'), value: 'a-z' },
    { label: t('charactersTab.filters.sortBy.options.nameDesc'), value: 'z-a' },
    { label: t('charactersTab.filters.sortBy.options.releaseDesc'), value: 'oldest' },
    { label: t('charactersTab.filters.sortBy.options.releaseAsc'), value: 'newest' },
    { label: t('charactersTab.filters.sortBy.options.modsDesc'), value: 'mods-desc' },
    { label: t('charactersTab.filters.sortBy.options.modsAsc'), value: 'mods-asc' },
]);

const releasePeriodOptions = computed(() => [
    { label: t('charactersTab.filters.releasePeriod.options.all'), value: 'all' },
    { label: t('charactersTab.filters.releasePeriod.options.lastWeek'), value: 'lastWeek' },
    { label: t('charactersTab.filters.releasePeriod.options.lastTwoWeeks'), value: 'lastTwoWeeks' },
    { label: t('charactersTab.filters.releasePeriod.options.lastMonth'), value: 'lastMonth' },
    { label: t('charactersTab.filters.releasePeriod.options.lastThreeMonths'), value: 'lastThreeMonths' },
    { label: t('charactersTab.filters.releasePeriod.options.lastSixMonths'), value: 'lastSixMonths' },
    { label: t('charactersTab.filters.releasePeriod.options.lastYear'), value: 'lastYear' }
]);

const modStatusOptions = computed(() => [
    { label: t('charactersTab.filters.modStatus.options.any'), value: 'any' },
    { label: t('charactersTab.filters.modStatus.options.enabled'), value: 'enabled' },
    { label: t('charactersTab.filters.modStatus.options.disabled'), value: 'disabled' }
]);

const showCostumeModal = ref(false);
const selectedCostume = ref<Character | null>(null);

const scrollTop = ref(0);
const scrollContainer = ref<HTMLElement | null>(null);

const modIndex = computed(() => {
    type Mod = typeof modsStore.mods[number];
    const index = new Map<string, { enabledTypes: Set<string>; mods: Mod[] }>();

    for (const mod of modsStore.mods) {
        if (!mod.modType || !('id' in mod.modType)) continue;
        if (!['Cutscene', 'Standing', 'Dating', 'NPC'].includes(mod.modType.type)) continue;

        let id = mod.modType.id;
        if (mod.modType.type === 'Dating') {
            const characterId = charactersStore.getCharacterIdByDatingId(id);
            if (!characterId) continue;
            id = characterId;
        } else if (mod.modType.type === 'NPC') {
            if (!mod.character) continue
            const ids = Array.isArray(mod.character.id) ? mod.character.id : [mod.character.id]
            for (const charId of ids) {
                let entry = index.get(charId)
                if (!entry) { entry = { enabledTypes: new Set(), mods: [] }; index.set(charId, entry) }
                entry.mods.push(mod)
                if (mod.enabled) entry.enabledTypes.add('Standing')
            }
            continue
        }

        let entry = index.get(id);
        if (!entry) {
            entry = { enabledTypes: new Set(), mods: [] };
            index.set(id, entry);
        }
        // some mods are made using NPC id, it changesthe standing and NPC too

        entry.mods.push(mod);

        if (mod.enabled) {
            entry.enabledTypes.add(mod.modType.type);
        }
    }

    console.log(index)

    return index;
});

function hasCutsceneInstalled(id: string | readonly string[]) {
    const ids = Array.isArray(id) ? id : [id];
    return ids.some(i => modIndex.value.get(i)?.enabledTypes.has('Cutscene'));
}

function hasStandingInstalled(id: string | readonly string[]) {
    const ids = Array.isArray(id) ? id : [id];

    return ids.some(i => modIndex.value.get(i)?.enabledTypes.has('Standing'));
}

function hasDatingInstalled(id: string | readonly string[]) {
    const ids = Array.isArray(id) ? id : [id];
    return ids.some(i => modIndex.value.get(i)?.enabledTypes.has('Dating'));
}

function getInstalledMods(id: string | readonly string[]) {
    const ids = Array.isArray(id) ? id : [id];
    return ids.flatMap(i => modIndex.value.get(i)?.mods ?? []);
}

function getInstalledModsCount(id: string | readonly string[]) {
    const ids = Array.isArray(id) ? id : [id];
    return ids.reduce((sum, i) => sum + (modIndex.value.get(i)?.mods.length ?? 0), 0);
}

function toggleMod(mod: BD2Mod) {
    if (mod.enabled) {
        modsStore.disableMods([mod.name])
    } else {
        modsStore.enableMods([mod.name])
    }
}

const filteredCharacters = computed(() => {
    const search = userFilters.searchQuery.toLowerCase();

    return charactersStore.characters.filter((char) => {
    if (search) {
        const matchesSearch = Object.keys(char.character_name).some((locale) => {
            const l = locale as Language;
            return (
                char.character_name[l].toLowerCase().includes(search) ||
                char.costume_name[l].toLowerCase().includes(search)
            );
        });
        if (!matchesSearch) return false;
    }

        const cutsceneEnabled = hasCutsceneInstalled(char.id);
        const standingEnabled = hasStandingInstalled(char.id);
        const datingEnabled = hasDatingInstalled(char.id);

        if (userFilters.cutscene === 'enabled' && !cutsceneEnabled) return false;
        if (userFilters.cutscene === 'disabled' && cutsceneEnabled) return false;

        if (userFilters.standing === 'enabled' && !standingEnabled) return false;
        if (userFilters.standing === 'disabled' && standingEnabled) return false;

        // if filtering by dating, also exclude characters that don't have dating at all. we can check dating_id
        if (userFilters.dating !== 'any' && !char.dating_id) return false;
        if (userFilters.dating === 'enabled' && !datingEnabled) return false;
        if (userFilters.dating === 'disabled' && datingEnabled) return false;

        if (userFilters.hideMenCharacters && char?.gender === 'male') return false;
        if (userFilters.hideWomenCharacters && char?.gender === 'female') return false;

        if (userFilters.onlyCollabCharacters && !char.is_collab) return false;

        if (userFilters.onlyCharactersWithMods && getInstalledModsCount(char.id) === 0) return false;
        if (userFilters.onlyCharactersWithoutMods && getInstalledModsCount(char.id) > 0) return false;

        switch (userFilters.releasePeriod) {
            case 'lastWeek':
                if (!char.release_date || new Date(char.release_date) < new Date(Date.now() - 7 * 86400000)) return false;
                break;
            case 'lastTwoWeeks':
                if (!char.release_date || new Date(char.release_date) < new Date(Date.now() - 14 * 86400000)) return false;
                break;
            case 'lastMonth':
                if (!char.release_date || new Date(char.release_date) < new Date(Date.now() - 30 * 86400000)) return false;
                break;
            case 'lastThreeMonths':
                if (!char.release_date || new Date(char.release_date) < new Date(Date.now() - 90 * 86400000)) return false;
                break;
            case 'lastSixMonths':
                if (!char.release_date || new Date(char.release_date) < new Date(Date.now() - 180 * 86400000)) return false;
                break;
            case 'lastYear':
                if (!char.release_date || new Date(char.release_date) < new Date(Date.now() - 365 * 86400000)) return false;
                break;
        }

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

const charactersGrid = computed(() =>
    sortedCharacters.value.map((costume) => ({
        ...costume,
        hasCutscene: hasCutsceneInstalled(costume.id),
        hasStanding: hasStandingInstalled(costume.id),
        hasDating: hasDatingInstalled(costume.id),
        modsCount: getInstalledModsCount(costume.id)
    }))
);

const charactersList = computed(() => {
    const groups = new Map<string, Character[]>();

    for (const char of sortedCharacters.value) {
        if (!groups.has(char.character)) {
            groups.set(char.character, []);
        }
        groups.get(char.character)!.push(char);
    }

    return Array.from(groups.entries()).map(([name, costumes]) => ({
        name,
        costumes: costumes.map(costume => ({
            ...costume,
            hasCutscene: hasCutsceneInstalled(costume.id),
            hasStanding: hasStandingInstalled(costume.id),
            hasDating: hasDatingInstalled(costume.id),
            modsCount: getInstalledModsCount(costume.id)
        }))
    }));
});

function refreshData() {
    charactersStore.loadCharacters()
    modsStore.discoverMods()
}

const openCostumeDetails = (costume: Character) => {
    selectedCostume.value = costume;
    showCostumeModal.value = true;
};

const AddModMenu = defineComponent({
    setup() {
        return () =>
            h(Popover, {}, {
                trigger: ({ toggle }: any) =>
                    h(Button, {
                        label: t('charactersTab.actions.addMod'),
                        icon: FolderPlus,
                        variant: 'text',
                        onClick: toggle
                    }),
                default: ({ close }: any) =>
                    h('ul', { class: 'bg-surface-popover border-border-default border rounded-md' }, addModMenuItems.value.map(item =>
                        h('li', { key: item.label },
                            h('button', {
                                class: 'w-full cursor-pointer text-left px-4 py-2 hover:bg-state-hover  text-sm font-medium',
                                onClick: () => { item.clicked(); close() }
                            }, item.label)
                        )
                    ))
            })
    }
})

useHeader({
    title: t('charactersTab.title'),
    subtitle: computed(() =>
        t('charactersTab.subtitle', {
            enabledModsCount: enabledModsCount.value,
            totalModsCount: totalModsCount.value
        })
    ),
    buttons: [
        { icon: RefreshCcw, label: t('common.actions.refreshMods'), action: refreshData },
        { render: () => h(AddModMenu) }
    ]
})

onDeactivated(() => {
    if (scrollContainer.value) scrollTop.value = scrollContainer.value.scrollTop;
});

onActivated(() => {
    if (scrollContainer.value) scrollContainer.value.scrollTop = scrollTop.value;
});

onMounted(() => {
    if (route.query.characterId) {
        console.log('Found characterId in query:', route.query.characterId);
        const costume = charactersStore.getCharacterById(route.query.characterId as string);
        if (costume) {
            selectedCostume.value = costume;
            showCostumeModal.value = true;
        }
    }

    console.log(modIndex)
})

watch(() => route.query.characterId, (newCharacterId) => {
    nextTick(() => {
        if (newCharacterId) {
            const costume = charactersStore.getCharacterById(newCharacterId as string);
            if (costume) {
                selectedCostume.value = costume;
                showCostumeModal.value = true;
            }
        } else {
            showCostumeModal.value = false;
            selectedCostume.value = null;
        }
    })
})
</script>

<template>
    <div class="flex flex-row w-full h-full p-4 py-2 gap-4 bg-surface-app overflow-hidden">
        <div class="flex-1 min-h-0 overflow-hidden">
            <CharacterList v-if="viewMode == 'list'" :items="charactersList" @openModDetails="openCostumeDetails" />
            <CharacterGrid v-else :items="charactersGrid" @openModDetails="openCostumeDetails" />
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
                    <Input v-model="userFilters.searchQuery" :placeholder="t('charactersTab.filters.searchPlaceholder')"
                        class="w-64" />
                </div>

                <div class="flex flex-col gap-1.5">
                    <label class="text-sm font-semibold text-text-primary">{{ t('charactersTab.filters.sortBy.title')
                        }}</label>
                    <Select v-model="userFilters.sortBy" :options="sortOptions" />
                </div>

                <div class="flex flex-col gap-2">
                    <label class="text-sm font-semibold text-text-primary">{{ t('charactersTab.filters.modStatus.title')
                        }}</label>
                    <div class="flex flex-col gap-2">
                        <div class="flex flex-col gap-1">
                            <label for="cutscene" class="text-xs font-medium text-text-secondary">{{
                                t('charactersTab.filters.modStatus.hasCutscene') }}</label>
                            <Select id="cutscene" v-model="userFilters.cutscene" :options="modStatusOptions" />
                        </div>
                        <div class="flex flex-col gap-1">
                            <label for="standing" class="text-xs font-medium text-text-secondary">{{
                                t('charactersTab.filters.modStatus.hasStanding') }}</label>
                            <Select id="standing" v-model="userFilters.standing" :options="modStatusOptions" />
                        </div>
                        <div class="flex flex-col gap-1">
                            <label for="dating" class="text-xs font-medium text-text-secondary">{{
                                t('charactersTab.filters.modStatus.hasDating') }}</label>
                            <Select id="dating" v-model="userFilters.dating" :options="modStatusOptions" />
                        </div>
                    </div>
                </div>

                <div class="flex flex-col gap-2">
                    <label class="text-sm font-semibold text-text-primary">{{
                        t('charactersTab.filters.extraFilters.title') }}</label>
                    <div class="flex flex-col gap-1.5">
                        <Checkbox v-model="userFilters.hideMenCharacters"
                            :label="t('charactersTab.filters.extraFilters.hideMenCharacters')" />
                        <Checkbox v-model="userFilters.hideWomenCharacters"
                            :label="t('charactersTab.filters.extraFilters.hideWomenCharacters')" />
                        <Checkbox v-model="userFilters.onlyCharactersWithMods"
                            :label="t('charactersTab.filters.extraFilters.onlyCharactersWithMods')" />
                        <Checkbox v-model="userFilters.onlyCharactersWithoutMods"
                            :label="t('charactersTab.filters.extraFilters.onlyCharactersWithoutMods')" />
                        <Checkbox v-model="userFilters.onlyCollabCharacters"
                            :label="t('charactersTab.filters.extraFilters.onlyCollabCharacters')" />
                    </div>
                </div>

                <div class="flex flex-col gap-2">
                    <label class="text-sm font-semibold text-text-primary">{{
                        t('charactersTab.filters.releasePeriod.title') }}</label>
                    <Select v-model="userFilters.releasePeriod" :options="releasePeriodOptions" />
                </div>
            </div>
        </div>

        <CharacterModal v-model:show="showCostumeModal" :selectedCostume="selectedCostume"
            :getInstalledMods="getInstalledMods" :toggleMod="toggleMod" />
    </div>
</template>

<style scoped></style>