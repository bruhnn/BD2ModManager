<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { open } from '@tauri-apps/plugin-dialog';
import { ArrowRight } from '@lucide/vue';
import { globalModals } from '../../composables/useGlobalModals';
import { ConvertSpineProgress, ConvertSpineResult, useModsStore } from '../../stores/mods';
import { useLoggingStore } from '../../stores/logging';
import { getErrorMessage } from '../../utils/errors';
import Button from '../common/Button.vue';
import Checkbox from '../common/Checkbox.vue';
import Input from '../common/Input.vue';
import Modal from '../common/Modal.vue';

const { t } = useI18n();
const modsStore = useModsStore();
const loggingStore = useLoggingStore();

const { isOpen, params, closeModal } = globalModals.oldSpineMods;

const mods = computed(() => params.value?.mods ?? []);
const selected = ref<Record<string, boolean>>({});
const createBackup = ref(true);
const backupDirectory = ref('');
const converting = ref(false);
const progress = ref<ConvertSpineProgress | null>(null);
const result = ref<ConvertSpineResult | null>(null);
const error = ref<string | null>(null);

watch(isOpen, (open) => {
    if (!open) return;
    selected.value = {};
    selectAll(true);
    createBackup.value = true;
    backupDirectory.value = params.value?.defaultBackupDirectory ?? '';
    progress.value = null;
    result.value = null;
    error.value = null;
});

const selectedMods = computed(() => mods.value.filter((mod) => selected.value[mod.modName]));

function selectAll(value: boolean) {
    for (const mod of mods.value) {
        selected.value[mod.modName] = value;
    }
}

const progressText = computed(() => {
    if (!progress.value) return t('modsTab.modals.oldSpineMods.converting', { done: 0, total: 0 });
    const key = progress.value.phase === 'backup' ? 'backingUp' : 'converting';
    return t(`modsTab.modals.oldSpineMods.${key}`, { done: progress.value.done, total: progress.value.total });
});

function close() {
    if (converting.value) return;
    closeModal();
}

async function changeBackupDirectory() {
    const folder = await open({ multiple: false, directory: true, defaultPath: backupDirectory.value || undefined });
    if (typeof folder === 'string') backupDirectory.value = folder;
}

async function convert() {
    if (converting.value) return;
    converting.value = true;
    error.value = null;
    progress.value = null;

    try {
        result.value = await modsStore.convertOldSpineMods(
            selectedMods.value.map((mod) => mod.modName),
            createBackup.value ? backupDirectory.value : null,
            (value) => { progress.value = value; },
        );
    } catch (err) {
        loggingStore.logError('Failed to convert Spine 4.1 mods:', JSON.stringify(err));
        // keep the modal open so another backup folder can be chosen
        error.value = getErrorMessage(t, err);
    } finally {
        converting.value = false;
    }
}
</script>

<template>
    <Modal :show="isOpen" size="lg" :title="t('modsTab.modals.oldSpineMods.title')"
        :subtitle="result ? undefined : t('modsTab.modals.oldSpineMods.subtitle', mods.length)"
        :close-on-escape="!converting" @close="close">
        <div class="flex flex-col gap-4 bg-surface-dialog p-4">
            <template v-if="!result">
                <div class="flex flex-col gap-1">
                    <div class="flex justify-start gap-1">
                        <Button variant="default" size="sm" :disabled="converting" :label="t('common.actions.selectAll')"
                            @click="selectAll(true)" />
                        <Button variant="default" size="sm" :disabled="converting" :label="t('common.actions.selectNone')"
                            @click="selectAll(false)" />
                    </div>
                    <div class="rounded-lg bg-surface-card overflow-hidden">
                        <div class="max-h-72 overflow-y-auto">
                            <div v-for="(mod, index) in mods" :key="mod.modName"
                                class="flex items-center justify-between gap-3 px-3 py-1.5 text-sm"
                                :class="{ 'border-t border-border-default': index > 0 }">
                                <Checkbox v-model="selected[mod.modName]" :disabled="converting"
                                    :label="mod.displayName || mod.modName" :title="mod.modName" class="min-w-0" />
                                <span class="flex shrink-0 items-center gap-1.5 text-xs text-text-secondary" :title="mod.files.join('\n')">
                                    Spine 4.1 <ArrowRight class="w-3.5 h-3.5" /> 4.2
                                </span>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="flex flex-col gap-2">
                    <Checkbox v-model="createBackup" :disabled="converting"
                        :label="t('modsTab.modals.oldSpineMods.createBackup')" />
                    <div v-if="createBackup" class="flex items-center gap-2 pl-7">
                        <Input class="w-full min-w-32" :model-value="backupDirectory" :title="backupDirectory" readonly
                            :disabled="converting" />
                        <Button class="shrink-0" :disabled="converting"
                            :label="t('modsTab.modals.oldSpineMods.changeBackupFolder')"
                            @click="changeBackupDirectory" />
                    </div>
                </div>

                <p v-if="converting" class="text-sm text-text-secondary">{{ progressText }}</p>
                <p v-if="error" class="text-sm text-error wrap-anywhere">{{ error }}</p>
            </template>

            <template v-else>
                <template v-if="result.backupError">
                    <p class="text-sm text-error wrap-anywhere">
                        {{ t('modsTab.modals.oldSpineMods.backupFailed', { error: result.backupError }) }}
                    </p>
                </template>
                <template v-else>
                    <p class="text-sm text-text-primary">
                        {{ result.converted.length
                            ? t('modsTab.modals.oldSpineMods.converted', { count: result.converted.length }, result.converted.length)
                            : t('modsTab.modals.oldSpineMods.noneConverted') }}
                    </p>

                    <div v-if="result.failed.length" class="flex flex-col gap-2">
                        <p class="text-sm text-error">{{ t('modsTab.modals.oldSpineMods.failed') }}</p>
                        <div class="max-h-56 overflow-y-auto rounded-lg bg-surface-card px-3 py-1.5">
                            <p v-for="failure in result.failed" :key="failure.modName + failure.file"
                                class="text-xs text-text-secondary wrap-anywhere">
                                {{ [failure.modName, failure.file].filter(Boolean).join('/') }}: {{ failure.error }}
                            </p>
                        </div>
                    </div>

                    <p v-if="result.backupPath" class="text-sm text-text-secondary wrap-anywhere">
                        {{ t('modsTab.modals.oldSpineMods.backedUp', { path: result.backupPath }) }}
                    </p>
                    <p v-if="result.converted.length" class="text-sm text-text-secondary">
                        {{ t('modsTab.modals.oldSpineMods.syncNote') }}
                    </p>
                </template>
            </template>
        </div>

        <template #footer>
            <div class="flex justify-end gap-2 p-3">
                <template v-if="!result">
                    <Button variant="text" :disabled="converting" :label="t('common.actions.cancel')" @click="close" />
                    <Button variant="primary"
                        :disabled="converting || !selectedMods.length || (createBackup && !backupDirectory)"
                        :label="t('modsTab.modals.oldSpineMods.convert')" @click="convert" />
                </template>
                <Button v-else variant="primary" :label="t('common.actions.close')" @click="close" />
            </div>
        </template>
    </Modal>
</template>
