<script setup lang="ts">
import { TriangleAlert, Upload,Trash2 } from '@lucide/vue'
import { useI18n } from 'vue-i18n'
import Button from '../../components/common/Button.vue'
import Tooltip from '../../components/common/Tooltip.vue'
import { computed } from 'vue';
import { PluginState, Status } from './types';
import GithubIcon from '../../components/icons/GithubIcon.vue';

const props = defineProps<{
    label: string
    description: string
    state: PluginState,
    disabled?: boolean
    showGithub?: boolean
    requiresBepInEx?: boolean
    bepInExInstalled?: boolean
}>()

const emit = defineEmits<{
    install: []
    installFromGithub: []
    remove: []
}>()

const { t } = useI18n()

function getStatusMessage(status: Status) {
    switch (status) {
        case Status.Installed: return t("browndustxTab.status.installed")
        case Status.InstalledButOutdated: return t("browndustxTab.status.installedButOutdated")
        case Status.NotInstalled: return t("browndustxTab.status.notInstalled")
        case Status.BepInExMissing: return t("browndustxTab.status.bepinexMissing")
        default: return status
    }
}

function isInstalled(status: Status) {
    return status === Status.Installed || status === Status.InstalledButOutdated
}

const canInstall = computed(() =>
    props.state.status === Status.NotInstalled &&
    (!props.requiresBepInEx || props.bepInExInstalled)
)

const cantRemoveReason = computed(() =>
    props.state.canRemove?.type === 'No'
        ? t(`browndustxTab.canRemoveReasons.${props.state.canRemove.reason}`, { name: props.label })
        : null
)
</script>

<template>
    <div
        class="grid grid-cols-[1fr_auto] lg:grid-cols-[2fr_100px_120px_280px] gap-2 lg:gap-4 items-center py-2.5 border-t border-border-default">
        <div class="min-w-0">
            <div class="flex items-center gap-1.5">
                <TriangleAlert v-if="state.status === Status.BepInExMissing" class="w-4 h-4 text-warning" />
                <span class="text-sm text-text-primary">{{ label }}</span>
                <span v-if="state.version" class="inline lg:hidden text-sm text-text-secondary">
                    v{{ state.version }}
                </span>
            </div>
            <p class="text-xs text-text-secondary truncate" :title="description">{{ description }}</p>
        </div>

        <span class="hidden lg:inline text-sm" :class="state.version ? 'text-text-primary' : 'text-text-secondary'">
            {{ state.version ?? '-' }}
        </span>

        <div class="hidden lg:flex items-center gap-1">
            <span class="text-xs" :class="{
                'text-success': isInstalled(state.status),
                'text-warning': state.status === Status.BepInExMissing || state.status === Status.InstalledButOutdated,
                'text-text-secondary': state.status === Status.NotInstalled,
            }">{{ getStatusMessage(state.status) }}</span>
        </div>

        <div class="flex gap-1 justify-end items-center">
            <template v-if="canInstall">
                <Button v-if="showGithub" variant="text" :label="$t('browndustxTab.actions.installFromGithub')"
                    :icon="GithubIcon" label-class="hidden lg:inline" :disabled="disabled"
                    @click="emit('installFromGithub')" />
                <Button variant="text" :label="$t('browndustxTab.actions.selectFile')" :icon="Upload"
                    label-class="hidden lg:inline" :disabled="disabled" @click="emit('install')" />
            </template>

            <template v-else-if="isInstalled(state.status)">
                <Tooltip v-if="cantRemoveReason" class="hidden lg:inline-flex" :text="cantRemoveReason">
                    <Button variant="text" :label="$t('browndustxTab.actions.remove')" :icon="Trash2"
                        label-class="hidden lg:inline" :disabled="disabled || state.canRemove?.type === 'No'"
                        @click="emit('remove')" />
                </Tooltip>
                <Button v-else variant="text" :label="$t('browndustxTab.actions.remove')" :icon="Trash2"
                    label-class="hidden lg:inline" :disabled="disabled" @click="emit('remove')" />
            </template>
        </div>
    </div>
</template>