<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { AlertOctagon, Check, RefreshCcw } from '@lucide/vue';
import { open } from '@tauri-apps/plugin-dialog';
import { dirname } from '@tauri-apps/api/path';
import { useLoggingStore } from '../../stores/logging';
import { useSettingsStore } from '../../stores/settings';
import { useI18n } from 'vue-i18n';

import RefinedGithub from '../../assets/icons/github.svg';
import { openUrl } from '@tauri-apps/plugin-opener';
import DiscordIcon from '../icons/DiscordIcon.vue';

import Button from '../common/Button.vue';
import Input from '../common/Input.vue';
import Modal from '../common/Modal.vue';
import KofiIcon from '../icons/KofiIcon.vue';
import AfDianIcon from '../icons/AfDianIcon.vue';
import { invoke } from '@tauri-apps/api/core';

const loggingStore = useLoggingStore()
const settingsStore = useSettingsStore()
const { locateGamePath, validateGamePath, saveSettings } = settingsStore
const { settings } = storeToRefs(settingsStore)
const { t } = useI18n()

const visible = defineModel('visible', {
    type: Boolean,
    required: true,
    default: false
})

const errorMessage = ref<string | null>(null)
const errorKey = ref(0)
const gamePathsFound = ref<string[]>([])

function setError(msg: string | null) {
    errorMessage.value = msg
    if (msg) errorKey.value++
}

async function handlePathSelected(path: string) {
    try {
        const isValid = await validateGamePath(path)

        if (!isValid) {
            setError(t('modals.welcome.selectGameDirectory.errors.invalidDirectory', { path }))
            return
        }

        await saveSettings({ gameDirectory: path })
        errorMessage.value = null
    } catch (err) {
        setError(t('modals.welcome.selectGameDirectory.errors.unknownError', { error: err }))
    }
}

async function handleDirectoryBrowse() {
    const file = await open({
        filters: [{ name: 'Executable Files', extensions: ['exe'] }],
        multiple: false,
        directory: false,
    })

    if (typeof file === 'string') {
        if (!file.toLowerCase().endsWith('browndust ii.exe')) {
            setError(t('modals.welcome.selectGameDirectory.errors.invalidGameExecutable'))
            return
        }

        const folder = await dirname(file)
        handlePathSelected(folder)
    }
}

function onClose() {
    visible.value = false
}

async function findGamePaths() {
    loggingStore.logDebug('WelcomeModal opened, attempting to locate game path.')

    const detectedGamePaths = await locateGamePath()
    if (detectedGamePaths && detectedGamePaths.length > 0) {
        // add some paths to test
        gamePathsFound.value = detectedGamePaths
    } else {
        loggingStore.logDebug('No game paths found by locateGamePath.')
        gamePathsFound.value = []
    }
}

onMounted(async () => {
    loggingStore.logDebug('WelcomeModal mounted.')

    if (visible.value) {
        await findGamePaths()
    }

    try {
        locale.value = await invoke('get_user_locale')
    } catch (error) {
        loggingStore.logError('Failed to get user locale', error)
    }
})

watch(visible, async (isVisible) => {
    if (isVisible) {
        await findGamePaths()
    }
})

const GITHUB_URL = 'https://github.com/bruhnn/BD2ModManager'
const DISCORD_URL = 'https://discord.gg/B3Aqz6tDG2'
const KOFI_URL = 'https://ko-fi.com/bruhnn'
const AFDIAN_URL = 'https://afdian.com/a/bruhnn'

const locale = ref('unknown')
const isChineseLanguage = computed(() => locale.value.startsWith('zh'))
</script>

<template>
    <Modal v-model:show="visible" class="w-[80%] max-w-200 max-h-[80%]" @close="onClose" :close-on-escape="false"
        :title="$t('modals.welcome.title')" :subtitle="$t('modals.welcome.subtitle')">
        <div class="w-full h-full flex flex-col gap-4 p-4">
            <div v-if="!isChineseLanguage"
                class="flex items-center gap-3 p-3 rounded-md border border-orange-500/30 bg-orange-500/10 cursor-pointer hover:bg-orange-500/20 transition-colors"
                @click="openUrl(KOFI_URL)">
                <KofiIcon class="w-4 h-4 fill-orange-400 shrink-0" />
                <div class="flex flex-col gap-0.5">
                    <p class="text-xs font-semibold text-orange-300">{{ $t('modals.welcome.supportBanner.title') }}</p>
                    <p class="text-xs text-orange-200/80">{{ $t('modals.welcome.supportBanner.messageKofi') }}</p>
                </div>
            </div>

            <div v-else
                class="flex items-center gap-3 p-3 rounded-md border border-purple-500/30 bg-purple-500/10 cursor-pointer hover:bg-purple-500/20 transition-colors"
                @click="openUrl(AFDIAN_URL)">
                <AfDianIcon class="w-4 h-4 fill-purple-400 shrink-0" />
                <div class="flex flex-col gap-0.5">
                    <p class="text-xs font-semibold text-purple-300">{{ $t('modals.welcome.supportBanner.title') }}</p>
                    <p class="text-xs text-purple-200/80">{{ $t('modals.welcome.supportBanner.messageAfdian') }}</p>
                </div>
            </div>

            <div class="flex items-center justify-ceter gap-2">
                <span @click="openUrl(GITHUB_URL)"
                    class="text-sm flex items-center gap-1.5 text-text-secondary bg-surface-card border border-border-default rounded-full px-3 py-1 hover:text-text-primary! hover:bg-state-hover! cursor-pointer transition-colors">
                    <RefinedGithub class="w-4 h-4 fill-text-secondary" />
                    {{ $t('modals.welcome.chips.github') }}
                </span>
                <span @click="openUrl(DISCORD_URL)"
                    class="text-sm flex items-center gap-1.5 text-text-secondary bg-surface-card border border-border-default rounded-full px-3 py-1 hover:text-text-primary! hover:bg-state-hover! cursor-pointer transition-colors">
                    <DiscordIcon class="w-4 h-4 fill-text-secondary" />
                    {{ $t('modals.welcome.chips.discord') }}
                </span>
            </div>

            <div class="flex flex-col gap-3">
                <div class="flex flex-col gap-1">
                    <p class="text-sm font-medium text-text-primary">{{ $t('modals.welcome.selectGameDirectory.title') }}</p>
                    <p class="text-xs text-text-secondary">
                        {{ $t('modals.welcome.selectGameDirectory.description') }}
                    </p>
                </div>

                <div class="flex gap-2 items-stretch h-10">
                    <Input readonly :model-value="settings.gameDirectory ?? ''"
                        :placeholder="$t('modals.welcome.selectGameDirectory.placeholders.gamePath')" />
                    <Button :label="$t('common.actions.browse')" @click="handleDirectoryBrowse" />
                </div>

                <div v-if="gamePathsFound.length > 0" class="flex flex-col gap-2">
                    <div class="flex justify-between items-center">
                        <p class="text-sm font-medium text-text-primary">
                            {{ $t('modals.welcome.selectGameDirectory.labels.foundPaths') }}
                        </p>
                        <Button variant="text" size="sm" @click="findGamePaths" label="Rescan" :icon="RefreshCcw" />
                    </div>
                    <div
                        class="w-full border rounded border-border-default bg-surface-card flex flex-col max-h-48 overflow-y-auto">
                        <div v-for="path in gamePathsFound" :key="path"
                            class="px-3 py-2 hover:bg-state-hover! active:bg-state-active! cursor-pointer flex items-center gap-2 rounded border border-transparent transition-colors"
                            @click="handlePathSelected(path)">
                            <Check v-if="path === settings.gameDirectory"
                                class="text-accent w-4 h-4 shrink-0" />
                            <span class="text-text-primary text-sm font-mono truncate">{{ path }}</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <template #footer>
            <div class="flex justify-between shrink-0 p-2 px-4">
                <div v-if="settings.gameDirectory && !errorMessage" class="flex items-center gap-2">
                    <Check class="text-success w-4 h-4 shrink-0" />
                    <span class="text-success text-sm">
                        {{ $t('modals.welcome.selectGameDirectory.validPath') }}
                    </span>
                </div>
                <div v-if="errorMessage" :key="errorKey" class="flex items-center gap-2 error-shake">
                    <AlertOctagon class="text-error w-4 h-4 shrink-0" />
                    <span class="text-error text-xs">{{ errorMessage }}</span>
                </div>
                <Button @click="onClose" variant="primary" :label="$t('common.actions.continue')" />
            </div>
        </template>
    </Modal>
</template>

<style scoped>
@keyframes shake {
    0%, 100% { transform: translateX(0); }
    20%       { transform: translateX(-5px); }
    60%       { transform: translateX(5px); }
}

.error-shake {
    animation: shake 0.3s ease-in-out;
}
</style>