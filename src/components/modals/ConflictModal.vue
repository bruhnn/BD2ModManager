<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { convertFileSrc } from '@tauri-apps/api/core'
import { Check, Eye, Search, TriangleAlert } from '@lucide/vue'
import { useModsStore, type BD2ModExtended, type BD2ModType } from '../../stores/mods'
import { usePreferencesStore } from '../../stores/preferences'
import { globalModals } from '../../composables/useGlobalModals.ts'
import { useModActions } from '../../composables/useModActions.ts'
import { formatCharName, useLang } from '../../utils/formatCharName.ts'
import Modal from '../common/Modal.vue'
import Button from '../common/Button.vue'
import Checkbox from '../common/Checkbox.vue'
import Image from '../common/Image.vue'
import Input from '../common/Input.vue'

type ModTypeName = BD2ModType['type']

interface ConflictGroup {
    key: string
    label: string
    type: ModTypeName
    typeLabel: string
    headUrl: string
    imageUrl: string
    mods: BD2ModExtended[]
}

const MOD_TYPE_ORDER: Record<ModTypeName, number> = {
    Cutscene: 0,
    Standing: 1,
    Dating: 2,
    Scene: 3,
    NPC: 4,
    Minigame: 5,
}

const PLACEHOLDER_IMAGE = 'characters/standing/placeholder_character.png'

const { t } = useI18n()
const lang = useLang()
const modsStore = useModsStore()
const preferencesStore = usePreferencesStore()
const { enableMods, disableMods, previewMod } = useModActions()
const { isOpen, params, closeModal } = globalModals.conflict


const conflictGroups = ref<ConflictGroup[]>([])
const selectedKey = ref<string | null>(null)
const searchQuery = ref('')

const pendingChanges = ref(new Map<string, boolean>())
// set when opened from "Sync Mods"; params are cleared on close, so keep our own copy
const onSync = ref<(() => void | Promise<void>) | null>(null)

function getAssetUrl(mod: BD2ModExtended, type: 'heads' | 'standing'): string {
    const ids = mod.character?.id
    if (!ids) return ''
    return convertFileSrc(`${type}/${Array.isArray(ids) ? ids.join(',') : ids}`, 'bd2assets')
}

function getGroupLabel(mod: BD2ModExtended): string {
    switch (mod.modType.type) {
        case 'Scene':
            return t('modsTab.modals.conflicts.sceneLabel', { id: mod.modType.id })
        case 'Minigame':
            return t('common.modTypes.minigame')
        default:
            return mod.character ? formatCharName(mod.character, lang.value) : mod.modType.id
    }
}

function createConflictGroups(): ConflictGroup[] {
    const conflicting = modsStore.extendedMods.filter(mod => mod.enabled && mod.conflictingMods.length > 0)
    const byName = new Map(conflicting.map(mod => [mod.name, mod]))
    const visited = new Set<string>()
    const groups: ConflictGroup[] = []

    for (const mod of conflicting) {
        if (visited.has(mod.name)) continue

        const stack = [mod]
        const members: BD2ModExtended[] = []

        while (stack.length) {
            const current = stack.pop()!
            if (visited.has(current.name)) continue
            visited.add(current.name)
            members.push(current)

            for (const other of current.conflictingMods) {
                const next = byName.get(other.name)
                if (next && !visited.has(next.name)) stack.push(next)
            }
        }

        members.sort((a, b) => a.displayName.localeCompare(b.displayName))

        const first = members[0]
        const type = first.modType.type
        const label = getGroupLabel(first)

        groups.push({
            key: `${type}::${label}`,
            label,
            type,
            typeLabel: t(`common.modTypes.${type.toLowerCase()}`),
            headUrl: getAssetUrl(first, 'heads'),
            imageUrl: getAssetUrl(first, 'standing'),
            mods: members,
        })
    }

    groups.sort((a, b) =>
        Number(MOD_TYPE_ORDER[a.type] > 2) - Number(MOD_TYPE_ORDER[b.type] > 2)
        || a.label.localeCompare(b.label)
        || MOD_TYPE_ORDER[a.type] - MOD_TYPE_ORDER[b.type]
    )

    const target = params.value?.mod?.name
    return target ? groups.filter(g => g.mods.some(m => m.name === target)) : groups
}

watch(isOpen, open => {
    if (!open) return
    onSync.value = params.value?.onSync ?? null
    conflictGroups.value = createConflictGroups()
    selectedKey.value = conflictGroups.value[0]?.key ?? null
    searchQuery.value = ''
    pendingChanges.value.clear()
}, { immediate: true })

const filteredGroups = computed(() => {
    const query = searchQuery.value.trim().toLowerCase()
    if (!query) return conflictGroups.value
    return conflictGroups.value.filter(g => g.label.toLowerCase().includes(query))
})

const selectedGroup = computed(() => conflictGroups.value.find(g => g.key === selectedKey.value) ?? null)


function modLabel(mod: BD2ModExtended): string {
    return preferencesStore.modNameDisplay === 'short' ? mod.displayName : mod.name
}

function isModEnabled(mod: BD2ModExtended): boolean {
    return pendingChanges.value.get(mod.name) ?? mod.enabled
}

function setModEnabled(mod: BD2ModExtended, value: boolean) {
    if (value === mod.enabled) pendingChanges.value.delete(mod.name)
    else pendingChanges.value.set(mod.name, value)
}

function enabledCount(group: ConflictGroup): number {
    return group.mods.filter(isModEnabled).length
}

// ctrl or shift click toggles it so several can stay enabled
function pickMod(group: ConflictGroup, mod: BD2ModExtended, event: MouseEvent) {
    if (event.ctrlKey || event.metaKey || event.shiftKey) {
        setModEnabled(mod, !isModEnabled(mod))
        return
    }
    for (const other of group.mods) setModEnabled(other, other.name === mod.name)
}

async function applyChanges() {
    const allMods = conflictGroups.value.flatMap(g => g.mods)
    const toEnable = allMods.filter(mod => pendingChanges.value.get(mod.name) === true)
    const toDisable = allMods.filter(mod => pendingChanges.value.get(mod.name) === false)

    if (toEnable.length) await enableMods(toEnable)
    if (toDisable.length) await disableMods(toDisable)

    pendingChanges.value.clear()
    closeModal()
}

async function continueSync(apply: boolean) {
    const sync = onSync.value
    if (apply) await applyChanges()
    else closeModal()
    await sync?.()
}

const subtitle = computed(() => {
    if (!conflictGroups.value.length) return undefined
    if (onSync.value) return t('modsTab.confirmations.syncMods.messageWithConflicts')
    return t('modsTab.modals.conflicts.subtitle', { count: conflictGroups.value.length }, conflictGroups.value.length)
})
</script>

<template>
    <Modal :show="isOpen" size="lg" :title="t('modsTab.modals.conflicts.title')"
        :subtitle="subtitle" @close="closeModal">
        <p v-if="!conflictGroups.length" class="text-center py-12 px-4 text-sm text-text-secondary">
            {{ t('modsTab.modals.conflicts.empty') }}
        </p>

        <div v-else class="flex gap-3 h-120 min-h-0 p-3">
            <div class="w-64 shrink-0 flex flex-col bg-surface-card rounded-lg overflow-hidden">
                <div class="p-1.5 shrink-0">
                    <Input v-model="searchQuery" :icon-left="Search" clearable size="md"
                        :placeholder="t('modsTab.modals.conflicts.searchPlaceholder')" />
                </div>
                <div class="flex-1 min-h-0 overflow-y-auto flex flex-col gap-0.5 px-1.5 pb-1.5">
                    <button v-for="group in filteredGroups" :key="group.key"
                        class="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-left cursor-pointer transition-colors hover:bg-state-hover"
                        :class="{ 'bg-state-hover': selectedKey === group.key }" @click="selectedKey = group.key">
                        <Image :src="group.headUrl" :alt="group.label" class="w-8 h-8 rounded-full shrink-0 object-cover"
                            :error-src="PLACEHOLDER_IMAGE" skeleton />
                        <span class="flex-1 min-w-0">
                            <span class="block text-sm text-text-primary truncate">{{ group.label }}</span>
                            <span class="block text-xs text-text-secondary">{{ group.typeLabel }}</span>
                        </span>
                        <span v-if="enabledCount(group) > 1"
                            class="text-xs flex items-center gap-1 bg-error-bg text-error font-bold font-mono px-1.5 rounded-sm h-6 shrink-0">
                            <TriangleAlert class="w-4 h-4" />
                            {{ enabledCount(group) }}
                        </span>
                        <Check v-else class="w-4 h-4 text-success shrink-0" />
                    </button>
                    <p v-if="!filteredGroups.length" class="text-center py-12 px-4 text-sm text-text-secondary">
                        {{ t('modsTab.modals.conflicts.noResults') }}
                    </p>
                </div>
            </div>

            <div v-if="selectedGroup" class="flex-1 min-w-0 flex flex-col">
                <div class="flex items-center justify-between gap-3 px-1 pb-3 shrink-0">
                    <div class="flex items-baseline gap-2 min-w-0">
                        <h3 class="font-semibold text-base text-text-primary truncate">{{ selectedGroup.label }}</h3>
                        <span class="text-sm text-text-secondary shrink-0">{{ selectedGroup.typeLabel }}</span>
                    </div>
                    <span class="text-sm font-semibold shrink-0"
                        :class="enabledCount(selectedGroup) > 1 ? 'text-error' : 'text-text-secondary'">
                        {{ t('charactersTab.characterModal.enabledMods') }}: {{ enabledCount(selectedGroup) }}/{{ selectedGroup.mods.length }}
                    </span>
                </div>
                <div class="flex-1 min-h-0 overflow-y-auto pr-1">
                    <div class="grid grid-cols-3 gap-3">
                        <div v-for="mod in selectedGroup.mods" :key="mod.name"
                            class="rounded-lg cursor-pointer transition-all bg-surface-card hover:bg-state-hover flex flex-col overflow-hidden border"
                            :class="isModEnabled(mod) ? 'border-accent' : 'border-transparent'"
                            @click="pickMod(selectedGroup, mod, $event)">
                            <div class="relative">
                                <Image :src="selectedGroup.imageUrl" :alt="modLabel(mod)"
                                    class="w-full aspect-square rounded-t-md" :error-src="PLACEHOLDER_IMAGE" skeleton
                                    error-class="bg-text-primary" />
                                <div class="absolute top-2.5 left-2.5" @click.stop>
                                    <Checkbox :model-value="isModEnabled(mod)"
                                        @update:model-value="val => setModEnabled(mod, val)" />
                                </div>
                                <button
                                    class="absolute top-2 right-2 w-7 h-7 flex items-center justify-center rounded-sm cursor-pointer bg-surface-dialog/80 text-text-secondary hover:bg-surface-dialog hover:text-text-primary transition-colors"
                                    :title="t('charactersTab.characterModal.previewMod')"
                                    :aria-label="t('charactersTab.characterModal.previewMod')" @click.stop="previewMod(mod)">
                                    <Eye class="w-4 h-4" />
                                </button>
                            </div>
                            <div class="px-2 py-2">
                                <p class="font-semibold text-sm line-clamp-2 break-all" :title="mod.name"
                                    :class="isModEnabled(mod) ? 'text-text-primary' : 'text-text-secondary'">
                                    {{ modLabel(mod) }}
                                </p>
                                <p v-if="mod.author" class="text-xs text-text-secondary truncate mt-0.5">{{ mod.author }}</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <template #footer>
            <div class="flex p-3 justify-between items-center gap-2 w-full">
                <span class="text-sm text-text-secondary">
                    {{ conflictGroups.length ? t('modsTab.modals.conflicts.hint') : '' }}
                </span>
                <div v-if="onSync" class="flex gap-2 shrink-0">
                    <Button variant="text" :label="t('common.actions.cancel')" @click="closeModal" />
                    <Button variant="default" :label="t('modsTab.confirmations.syncMods.actions.syncAnyway')"
                        @click="continueSync(false)" />
                    <Button variant="primary" :label="t('modsTab.modals.conflicts.applyAndSync')"
                        :disabled="!pendingChanges.size" @click="continueSync(true)" />
                </div>
                <div v-else class="flex gap-2 shrink-0">
                    <Button variant="default" :label="t('common.actions.close')" @click="closeModal" />
                    <Button v-if="conflictGroups.length" variant="primary"
                        :label="t('modsTab.modals.conflicts.apply', { count: pendingChanges.size }, pendingChanges.size)"
                        :disabled="!pendingChanges.size" @click="applyChanges" />
                </div>
            </div>
        </template>
    </Modal>
</template>
