<script setup lang="ts">
import { ChevronLeft, ChevronRight, RotateCcw } from '@lucide/vue'
import { computed, ref, useTemplateRef } from 'vue'
import { useI18n } from 'vue-i18n'

import { UserTheme, useThemesStore } from '../../../../stores/themes.ts'

import Modal from '../../../../components/common/Modal.vue'
import Button from '../../../../components/common/Button.vue'
import Input from '../../../../components/common/Input.vue'
import themeTemplate from '../../../../styles/themes/dark-2.css?raw'

const { t } = useI18n()
const themesStore = useThemesStore()

const GROUP_BY_PREFIX: Record<string, string> = {
    surface: 'surfaces',
    text: 'texts',
    border: 'borders',
    state: 'states',
    accent: 'accent',
    mod: 'mods',
    changelog: 'changelogs'
}

// color names from dark-2.css, without "--": 'surface-app', 'text-primary', ...
const NAMES = [...themeTemplate.matchAll(/--([\w-]+)\s*:/g)].map(m => m[1])

const groupOf = (name: string) => GROUP_BY_PREFIX[name.split('-')[0]] ?? 'statuses'

function labelOf(name: string) {
    const prefix = name.split('-')[0]
    return GROUP_BY_PREFIX[prefix] ? name.slice(prefix.length + 1) || prefix : name
}

const GROUPS = ['surfaces', 'texts', 'borders', 'states', 'accent', 'mods', 'statuses', 'changelogs']

const emit = defineEmits<{
    save: [theme: UserTheme, originalName: string]
}>()

const modalType = ref<'creator' | 'editor'>('creator')
const isModalVisible = ref(false)
const theme = ref<UserTheme>({ name: '', author: '', colors: {} })
const originalName = ref('')
const showNameError = ref(false)
const initialColors = ref<Record<string, string>>({})
const activeTab = ref('surfaces')
const tabsRef = useTemplateRef('tabs')

const nameError = computed(() => {
    const value = theme.value.name
    if (!value.trim()) return t('settingsTab.general.sections.application.theme.editor.errors.empty')
    const badChar = [...value].find(c => '<>:"/\\|?*'.includes(c) || c.charCodeAt(0) < 32)
    if (badChar) return badChar.charCodeAt(0) < 32 ? t('settingsTab.general.sections.application.theme.editor.errors.controlChar') : t('settingsTab.general.sections.application.theme.editor.errors.invalidChar', { char: badChar })
    if (/[. ]$/.test(value)) return t('settingsTab.general.sections.application.theme.editor.errors.trailing')
    if (value.length > 200) return t('settingsTab.general.sections.application.theme.editor.errors.tooLong')
    const taken = themesStore.availableThemes.some(t =>
        t.value.toLowerCase() === value.toLowerCase() && t.value.toLowerCase() !== originalName.value.toLowerCase())
    if (taken) return t('settingsTab.general.sections.application.theme.editor.errors.taken')
    return null
})

defineExpose({
    modalType,
    openModal(type: 'creator' | 'editor') {
        const existing = type === 'editor'
            ? themesStore.userThemes.find(t => t.name === themesStore.currentTheme)
            : undefined
        const style = getComputedStyle(document.documentElement)
        const onScreen = Object.fromEntries(NAMES.map(n => [n, style.getPropertyValue(`--${n}`).trim()]))

        modalType.value = type
        originalName.value = existing?.name ?? ''
        initialColors.value = { ...onScreen, ...existing?.colors }
        theme.value = { name: existing?.name ?? '', author: existing?.author ?? '', colors: { ...initialColors.value } }
        activeTab.value = 'surfaces'
        showNameError.value = false
        isModalVisible.value = true
    },
    closeModal() {
        isModalVisible.value = false
    },
})

function save() {
    if (nameError.value) {
        showNameError.value = true
        return
    }
    emit('save', { ...theme.value, colors: { ...theme.value.colors } }, originalName.value)
}

// color picker only knows #rrggbb, so rgba() values keep their alpha
function toHex(value: string) {
    const m = value.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
    if (!m) return value
    return '#' + [m[1], m[2], m[3]].map(n => Number(n).toString(16).padStart(2, '0')).join('')
}

function withColor(old: string, hex: string) {
    const alpha = old.match(/rgba\([^)]*,\s*([\d.]+)\)/)
    if (!alpha) return hex
    const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16))
    return `rgba(${r}, ${g}, ${b}, ${alpha[1]})`
}

// "-bg" color follows its base color until it is changed
function setColor(colorName: string, hex: string) {
    const colors = theme.value.colors
    const bg = `${colorName}-bg`
    if (bg in colors && toHex(colors[bg]) === toHex(colors[colorName])) {
        colors[bg] = withColor(colors[bg], hex)
    }
    colors[colorName] = withColor(colors[colorName], hex)
}

function setBackground(colorName: string, hex: string) {
    const colors = theme.value.colors
    colors[`${colorName}-bg`] = withColor(colors[`${colorName}-bg`], hex)
}
</script>

<template>
    <Modal size="md" :title="t(`settingsTab.general.sections.application.theme.editor.${modalType === 'creator' ? 'createTitle' : 'editTitle'}`)" v-model:show="isModalVisible"
        @close="isModalVisible = false" :close-on-escape="false">
        <div class="grid grid-cols-2 gap-3 px-4 pt-4">
            <div>
                <label for="themeName" class="mb-1 block text-sm text-text-secondary">{{ t(`settingsTab.general.sections.application.theme.editor.name`) }}</label>
                <div class="h-8">
                    <Input id="themeName" v-model="theme.name" :placeholder="t(`settingsTab.general.sections.application.theme.editor.namePlaceholder`)" :error="showNameError && !!nameError" />
                </div>
                <p v-if="showNameError && nameError" class="mt-1 text-xs text-error">{{ nameError }}</p>
            </div>
            <div>
                <label for="themeAuthor" class="mb-1 block text-sm text-text-secondary">{{ t(`settingsTab.general.sections.application.theme.editor.author`) }}</label>
                <div class="h-8">
                    <Input id="themeAuthor" v-model="theme.author" :placeholder="t(`settingsTab.general.sections.application.theme.editor.authorPlaceholder`)" />
                </div>
            </div>
        </div>

        <div class="mx-4 mt-4 flex border-b border-border-default">
            <button class="shrink-0 cursor-pointer px-1 text-text-secondary hover:text-text-primary"
                @click="tabsRef?.scrollBy({ left: -150, behavior: 'smooth' })">
                <ChevronLeft class="size-4" />
            </button>
            <div ref="tabs" class="flex min-w-0 flex-1 overflow-x-auto scrollbar-none"
                @wheel.prevent="($event.currentTarget as HTMLElement).scrollLeft += $event.deltaY">
                <button v-for="group in GROUPS" :key="group" @click="activeTab = group"
                    class="shrink-0 -mb-px cursor-pointer whitespace-nowrap border-b-2 px-3 py-2 text-sm transition-colors"
                    :class="activeTab === group ? 'border-accent text-text-primary' : 'border-transparent text-text-secondary hover:text-text-primary'">
                    {{ t(`settingsTab.general.sections.application.theme.editor.groups.${group}`) }}
                </button>
            </div>
            <button class="shrink-0 cursor-pointer px-1 text-text-secondary hover:text-text-primary"
                @click="tabsRef?.scrollBy({ left: 150, behavior: 'smooth' })">
                <ChevronRight class="size-4" />
            </button>
        </div>

        <div class="min-h-36 p-4">
            <div class="grid grid-cols-[repeat(auto-fill,minmax(160px,1fr))] gap-2">
                <div v-for="colorName in NAMES.filter(n => groupOf(n) === activeTab && !n.endsWith('-bg'))"
                    :key="colorName" class="rounded-lg bg-surface-card p-1">
                    <label class="relative flex cursor-pointer items-center gap-2.5 rounded-md p-1 hover:bg-state-hover">
                        <span class="size-9 shrink-0 rounded-md" :style="{ background: theme.colors[colorName] }" />
                        <span class="min-w-0">
                            <span class="block truncate text-sm capitalize text-text-primary">{{
                                labelOf(colorName).replace('-', ' ') }}</span>
                            <span class="block truncate font-mono text-xs text-text-secondary">{{ theme.colors[colorName]
                                }}</span>
                        </span>
                        <input type="color" class="absolute inset-0 size-full cursor-pointer opacity-0"
                            :value="toHex(theme.colors[colorName])"
                            @input="setColor(colorName, ($event.target as HTMLInputElement).value)" />
                    </label>
                    <label v-if="`${colorName}-bg` in theme.colors"
                        class="relative flex cursor-pointer items-center gap-2.5 rounded-md p-1 hover:bg-state-hover">
                        <span class="size-9 shrink-0 rounded-md ring-1 ring-inset ring-border-default"
                            :style="{ background: theme.colors[`${colorName}-bg`] }" />
                        <span class="min-w-0">
                            <span class="block truncate text-sm text-text-primary">{{
                                t('settingsTab.general.sections.application.theme.editor.background') }}</span>
                            <span class="block truncate font-mono text-xs text-text-secondary">{{
                                toHex(theme.colors[`${colorName}-bg`]) }}</span>
                        </span>
                        <input type="color" class="absolute inset-0 size-full cursor-pointer opacity-0"
                            :value="toHex(theme.colors[`${colorName}-bg`])"
                            @input="setBackground(colorName, ($event.target as HTMLInputElement).value)" />
                    </label>
                </div>
            </div>
        </div>

        <template #footer>
            <div class="flex items-center justify-between gap-2 p-4">
                <Button :label="t(`settingsTab.general.sections.application.theme.editor.reset`)" :icon="RotateCcw" variant="text" @click="theme.colors = { ...initialColors }" />
                <span class="inline-flex gap-2">
                    <Button :label="$t('common.actions.cancel')" @click="isModalVisible = false" />
                    <Button variant="primary" :label="$t('common.actions.save')" @click="save" />
                </span>
            </div>
        </template>
    </Modal>
</template>
