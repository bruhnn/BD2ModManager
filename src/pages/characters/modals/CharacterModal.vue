<script setup lang="ts">
import { X, Calendar, Eye, BadgeDollarSign, ExternalLink, Info, Tag } from '@lucide/vue';
import { Character } from '../../../stores/characters';
import { BD2Mod, useModsStore } from '../../../stores/mods';
import { computed, ref } from 'vue';
import Button from '../../../components/common/Button.vue';
import Image from '../../../components/common/Image.vue';
import Modal from '../../../components/common/Modal.vue';
import Checkbox from '../../../components/common/Checkbox.vue';
import { useLoggingStore } from '../../../stores/logging';
import { getErrorMessage } from '../../../utils/errors';
import { useI18n } from 'vue-i18n';
import { Tab, TabGroup, TabList, TabPanels, TabPanel } from '@headlessui/vue';
import { useModsIndexStore } from '../../../stores/modsIndex';
import KofiIcon from '../../../components/icons/KofiIcon.vue';
import DiscordIcon from '../../../components/icons/DiscordIcon.vue';
import PatreonIcon from '../../../components/icons/PatreonIcon.vue';
import { openUrl } from '@tauri-apps/plugin-opener';
import AfDianIcon from '../../../components/icons/AfDianIcon.vue';
import { convertFileSrc } from '@tauri-apps/api/core';
import { useNotificationStore } from '../../../stores/notification.ts';
import { getCharName, useLang } from '../../../utils/formatCharName.ts';

const loggingStore = useLoggingStore();
const notificationStore = useNotificationStore();
const { t } = useI18n();
const modsIndex = useModsIndexStore();

const show = defineModel('show', {
    type: Boolean,
    required: true,
});

const props = defineProps<{
    selectedCostume: Character | null;
    toggleMod: (mod: BD2Mod) => void;
}>();

const modsStore = useModsStore();

const costumeIds = computed((): string[] => {
    const id = props.selectedCostume?.id;
    return Array.isArray(id) ? [...id] : id ? [id as string] : [];
});

const installedMods = computed(() => {
    if (!props.selectedCostume) return [];
    return modsStore.extendedMods.filter(mod => {
        if (!mod.modType) return false;
        const { type } = mod.modType;
        if (['Cutscene', 'Standing'].includes(type)) {
            return 'id' in mod.modType && costumeIds.value.includes(mod.modType.id);
        }
        if (type === 'NPC') {
            if (!mod.character) return false;
            const modCharIds = Array.isArray(mod.character.id) ? [...mod.character.id] : [mod.character.id];
            return modCharIds.some(id => costumeIds.value.includes(id));
        }
        if (type === 'Dating') {
            return 'id' in mod.modType && mod.modType.id === props.selectedCostume?.dating_id;
        }
        return false;
    });
});

const modsByType = computed(() => {
    const grouped = {
        Cutscene: [] as BD2Mod[],
        Standing: [] as BD2Mod[],
        Dating: [] as BD2Mod[]
    };
    installedMods.value.forEach(mod => {
        const type = mod.modType?.type === 'NPC' ? 'Standing' : mod.modType?.type;
        if (type && type in grouped) {
            grouped[type as keyof typeof grouped].push(mod);
        }
    });
    return grouped;
});

const enabledModsCount = computed(() =>
    installedMods.value.filter(mod => mod.enabled).length
);

async function openPreviewMod(mod: BD2Mod) {
    modsStore.previewMod(mod.name).then(() => {
        loggingStore.logDebug("Mod previewed successfully:", mod.name);
    }).catch((error) => {
        let errorMsg = getErrorMessage(t, error);
        notificationStore.add({
            type: "error",
            closable: true,
            title: t("modsTab.errors.modPreview.title"),
            message: errorMsg,
            duration: 5000
        });
        loggingStore.logError("Error previewing mod:", error);
    });
}

function getIconForLink(key: string) {
    switch (key) {
        case "patreon": return PatreonIcon;
        case "ko-fi": return KofiIcon;
        case "discord": return DiscordIcon;
        case "afdian": return AfDianIcon;
        default: return ExternalLink;
    }
}

function handleOpenLink(link: string | null) {
    if (!link) return;
    openUrl(link);
}

const tooltipVisible = ref<string | null>(null);

const hasIndexMods = computed(() => {
    if (!props.selectedCostume) return false;
    return ['cutscene', 'standing', 'dating'].some(
        type => costumeIds.value.some(id => modsIndex.getMods(id, type).length > 0)
    );
});

function getIndexMods(type: string) {
    return costumeIds.value.flatMap(id => modsIndex.getMods(id, type));
}

const imageUrl = computed(() => {
    if (!props.selectedCostume) return "#"
    const ids = Array.isArray(props.selectedCostume.id)
        ? props.selectedCostume.id.join(',')
        : props.selectedCostume.id
    return convertFileSrc(`standing/${ids}`, "bd2assets")
})

const lang = useLang()

const charName = computed(() => {   
    if (!props.selectedCostume) return
    return getCharName(props.selectedCostume, lang.value)
})
</script>

<template>
    <Modal v-model:show="show" size="lg" @close="() => show = false">
        <template #footer>
            <div class="flex p-3 justify-end items-center w-full border-t border-border-default">
                <Button variant="default" :label="$t('common.actions.close')" @click="show = false" />
            </div>
        </template>
        <template #header></template>

        <div v-if="selectedCostume" class="flex flex-col min-h-0 text-text-primary overflow-hidden">
            <div class="flex items-stretch border-b border-border-default shrink-0">
                <!-- [TODO] when clicked it shows full image -->
                <Image :src="imageUrl"
                    class="w-40 h-40 object-cover shrink-0 border-r border-border-default aspect-square"
                    skeleton
                    error-src="characters/standing/placeholder_character.png"
                    error-class="bg-text-primary" />

                <div class="flex-1 px-4 py-3 flex flex-col">
                    <div class="flex items-start justify-between gap-2">
                        <div>
                            <div class="flex items-baseline gap-2">
                                <h3 class="font-semibold text-base text-text-primary">{{ charName?.character }}</h3>
                                <span class="text-sm text-text-secondary">{{ charName?.costume }}</span>
                            </div>
                            <div class="flex flex-col tems-center gap-3 mt-1 text-xs text-text-secondary">
                                <span class="flex items-center gap-1">
                                    <Tag class="w-4 h-4"/>
                                    {{ Array.isArray(selectedCostume.id) ? selectedCostume.id.join(', ') : selectedCostume.id }}
                                </span>
                                <span v-if="selectedCostume.release_date" class="flex items-center gap-1">
                                    <Calendar class="w-4 h-4" />
                                    {{ new Date(selectedCostume.release_date).toLocaleDateString() }}
                                </span>
                                <!-- <span v-if="selectedCostume.is_collab"
                                    class="flex items-center gap-1 px-1.5 py-0.5 bg-accent-muted text-accent rounded text-xs font-medium">
                                    <Gem class="w-4 h-4" /> {{ $t('charactersTab.tags.collab') }}
                                </span> -->
                            </div>
                        </div>

                        <button @click="show = false"
                            class="text-text-secondary cursor-pointer hover:text-text-primary transition-colors p-1 rounded-sm hover:bg-state-hover"
                            :aria-label="$t('common.actions.close')">
                            <X class="w-4 h-4" />
                        </button>
                    </div>

                    <div class="flex gap-5 mt-3 flex-1 items-center">
                        <div>
                            <p class="text-base font-semibold leading-none">{{ enabledModsCount }}</p>
                            <p class="text-xs text-text-secondary mt-0.5">{{ $t('charactersTab.characterModal.enabledMods') }}</p>
                        </div>
                        <div>
                            <p class="text-base font-semibold leading-none">{{ installedMods.length }}</p>
                            <p class="text-xs text-text-secondary mt-0.5">{{ $t('charactersTab.characterModal.totalMods') }}</p>
                        </div>
                    </div>
                </div>
            </div>

            <div class="flex flex-col min-h-0 flex-1">
                <TabGroup>
                    <TabList class="flex shrink-0 items-center gap-1 px-2 py-2 border-b border-border-default" as="div">
                        <Tab v-slot="{ selected }" key="modsTab" as="template">
                            <button class="px-4 py-1.5 text-sm rounded-sm transition-colors outline-none cursor-pointer hover:bg-state-hover"
                                :class="selected ? 'bg-accent! text-text-on-accent font-medium' : 'text-text-secondary hover:text-text-primary'">
                                {{ $t('charactersTab.characterModal.modsTab') }}
                            </button>
                        </Tab>
                        <Tab v-slot="{ selected }" key="discoverModsTab" as="template">
                            <button class="px-4 py-1.5 text-sm rounded-sm transition-colors outline-none cursor-pointer  hover:bg-state-hover"
                                :class="selected ? 'bg-accent! text-text-on-accent font-medium' : 'text-text-secondary hover:text-text-primary'">
                                {{ $t('charactersTab.characterModal.discoverModsTab') }}
                            </button>
                        </Tab>
                    </TabList>

                    <TabPanels as="div" class="overflow-y-auto h-100">
                        <TabPanel key="modsPanel">
                            <div>
                                <div v-if="installedMods.length === 0" class="text-center py-12 px-4 text-text-secondary">
                                    <p class="text-sm font-medium mb-1">{{ $t('charactersTab.characterModal.noModsFound.title') }}</p>
                                    <p class="text-xs text-text-secondary">{{ $t('charactersTab.characterModal.noModsFound.description') }}</p>
                                </div>
                                <template v-else>
                                    <div v-for="(mods, type) in modsByType" :key="type" v-show="mods.length > 0">
                                        <div class="flex items-center justify-between px-4 py-2 bg-surface-dialog border-b border-border-default top-0 z-10">
                                            <span class="text-xs font-medium text-text-secondary uppercase tracking-wide">
                                                {{ $t(`charactersTab.modTypes.${type.toLowerCase()}`) }}
                                            </span>
                                            <span class="text-xs text-text-secondary">{{ mods.filter(m => m.enabled).length }}/{{ mods.length }}</span>
                                        </div>

                                        <label v-for="mod in mods" :key="mod.name"
                                            class="flex items-center gap-3 px-4 py-2.5 border-b border-border-default cursor-pointer hover:bg-state-hover transition-colors"
                                            :class="{ 'bg-surface-dialog': !mod.enabled }">
                                            <Checkbox :model-value="mod.enabled" @update:model-value="toggleMod(mod)" :disabled="modsStore.isSyncing" class="shrink-0" />
                                            <button @click.stop="openPreviewMod(mod)" :aria-label="$t('charactersTab.characterModal.previewMod')">
                                                <Eye class="w-6 h-6 cursor-pointer hover:text-text-primary! transition-colors active:scale-95 text-text-secondary" />
                                            </button>
                                            <div class="flex-1 min-w-0">
                                                <p class="text-sm truncate" :class="mod.enabled ? 'text-text-primary' : 'text-text-secondary'">{{ mod.name }}</p>
                                                <p v-if="mod.author" class="text-xs text-text-secondary mt-0.5">{{ mod.author }}</p>
                                            </div>
                                        </label>
                                    </div>
                                </template>
                            </div>
                        </TabPanel>

                        <TabPanel key="discoverModsPanel">
                            <div>
                                <div class="bg-surface-card border border-border-default rounded-lg p-3 m-2 flex items-start gap-2">
                                    <Info class="w-5 h-5 text-text-secondary" />
                                    <p class="text-sm text-text-secondary font-medium text-wrap">
                                        {{ $t('charactersTab.characterModal.discoverModsDescription', { latestUpdate: modsIndex.latestUpdate }) }}
                                    </p>
                                </div>
                                <template v-for="type in ['cutscene', 'standing', 'dating']">
                                    <div v-if="getIndexMods(type).length > 0"
                                        class="flex items-center justify-between px-4 py-2 bg-surface-dialog border-b border-border-default sticky top-0 z-10">
                                        <span class="text-xs font-medium text-text-secondary uppercase tracking-wide">
                                            {{ $t(`charactersTab.modTypes.${type}`) }}
                                        </span>
                                    </div>

                                    <label v-for="(mod, index) in getIndexMods(type)" :key="`${type}-${index}`"
                                        class="flex items-center gap-3 px-4 py-2.5 border-b border-border-default transition-colors">
                                        <div class="flex-1 min-w-0 flex items-center gap-2">
                                            <div class="relative flex items-center">
                                                <BadgeDollarSign class="w-5 h-5"
                                                    :class="{ 'text-success/70': !mod.is_paid, 'text-warning': mod.is_paid }"
                                                    @mouseenter="tooltipVisible = `${type}-${index}`"
                                                    @mouseleave="tooltipVisible = null" />
                                                
                                                    <span v-show="tooltipVisible === `${type}-${index}`"
                                                        class="absolute top-[50%] translate-y-[-50%] z-15 left-full ml-2 text-xs text-text-primary font-medium bg-surface-popover border border-border-default px-2 py-1 rounded-sm whitespace-nowrap">
                                                        {{ mod.is_paid ? $t('charactersTab.characterModal.paidMod') : $t('charactersTab.characterModal.freeMod') }}
                                                    </span>

                                            </div>

                                            <p class="text-sm truncate text-text-primary flex-1">{{ mod.authorData?.name }}</p>

                                            <div class="flex flex-row gap-4">
                                                <div v-for="(link, key) in Object.fromEntries(Object.entries(mod.authorData?.links || {}).filter(([_, link]) => link))"
                                                    :key="key" class="flex items-center gap-1.5 cursor-pointer group"
                                                    @click="handleOpenLink(link)">
                                                    <component :is="getIconForLink(key)" class="w-4 h-4"
                                                        :color="{ 'patreon': '#FF424D', 'ko-fi': '#29ABE0', 'discord': '#5865F2', 'afdian': '#946CE6' }[key]" />
                                                    <span :title="link || ''"
                                                        class="text-sm text-text-primary font-medium transition-colors" :class="[
                                                            `group-hover:text-[${{ 'patreon': '#FF424D', 'ko-fi': '#29ABE0', 'discord': '#5865F2', 'afdian': '#946CE6' }[key]}]`
                                                        ]">{{ key[0].toUpperCase() + key.slice(1) }}</span>
                                                </div>
                                            </div>
                                        </div>
                                    </label>
                                </template>
                                <div v-if="!hasIndexMods" class="text-center py-12 px-4">
                                    <p class="text-sm font-medium text-text-secondary mb-1">{{ $t('charactersTab.characterModal.noIndexModsFound.title') }}</p>
                                    <p class="text-xs text-text-secondary">{{ $t('charactersTab.characterModal.noIndexModsFound.description') }}</p>
                                </div>
                            </div>
                        </TabPanel>
                    </TabPanels>
                </TabGroup>
            </div>
        </div>
    </Modal>
</template>
