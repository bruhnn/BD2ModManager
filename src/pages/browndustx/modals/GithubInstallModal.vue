<script setup lang="ts">
import { ref, watch } from 'vue';
import { DownloadIcon, TriangleAlert } from '@lucide/vue';
import Modal from '../../../components/common/Modal.vue';
import Button from '../../../components/common/Button.vue';
import Checkbox from '../../../components/common/Checkbox.vue';
import { platform } from '@tauri-apps/plugin-os';
import { useLoggingStore } from '../../../stores/logging';

const loggingStore = useLoggingStore()

const showModal = defineModel('show', {
    type: Boolean,
    required: true
});

const emit = defineEmits<{
    close: []
    onVersionSelect: [downloadUrl: string]
}>()

const props = defineProps({
    releasesUrl: {
        type: String,
        required: true
    },
    recommendedVersion: {
        type: String,
        required: true
    },
    assetsFilterRegex: {
        type: RegExp,
        required: false
    }
})

interface GithubRelease {
    version: string;
    published_at: string;
    releases_url: string;
    assets: {
        name: string;
        size: number;
        download_url: string;
    }[];
}

const isLoading = ref(false)
const releases = ref([] as GithubRelease[])
const enableOtherVersions = ref(false)

function filterAssets(assets: any[]) {
    if (!props.assetsFilterRegex) return assets

    const currentPlatform = platform()
    return assets.filter(asset => {
        return currentPlatform === 'windows'
            ? props.assetsFilterRegex?.test(asset.name) && asset.name.endsWith('.zip')
            : true;
    });
}

async function getReleases() {
    isLoading.value = true

    try {
        const response = await fetch(props.releasesUrl)

        const data: any[] = await response.json()
        
        // sort by published date
        // data.sort((a, b) => new Date(b.published_at).getTime() - new Date(a.published_at).getTime())

        // filter out pre-releases and limit to 10, then map to our GithubRelease type, filtering the assets
        releases.value = data.filter((release: any) => !release.prerelease).slice(0, 10).map(release => ({
            version: release.tag_name,
            published_at: release.published_at,
            releases_url: release.html_url,
            assets: filterAssets(release.assets).map((asset: any) => ({
                name: asset.name,
                size: asset.size,
                download_url: asset.browser_download_url
            }))
        }))

        // put the recommended version on top
        releases.value.sort((a, b) => {
            if (a.version === props.recommendedVersion) return -1
            if (b.version === props.recommendedVersion) return 1
            return 0;
        });
    } catch (error) {
        loggingStore.logError(`Error getting github releases from ${props.releasesUrl}:`, error)
    } finally {
        isLoading.value = false
    }
}

watch(() => showModal.value,
    async (newVal) => {
        if (newVal && releases.value.length === 0) {
            await getReleases();
        }
    }
);

function formatDate(dateString: string) {
    return new Date(dateString).toLocaleDateString()
}

function handleVersionSelected(downloadUrl: string) {
    showModal.value = false
    emit('onVersionSelect', downloadUrl)
}
</script>

<template>
    <Modal v-model:show="showModal" @close="showModal = false" size="lg"
        :title="$t('browndustxTab.modals.installFromGithub.title')">
        <template #footer>
            <div class="flex justify-end gap-2 p-2">
                <Button label="Cancel" @click="$emit('close')" />
            </div>
        </template>

        <div class="p-4">
            <div v-if="isLoading" class="text-center py-8 text-text-secondary">
                {{ $t('browndustxTab.modals.installFromGithub.loading') }}
            </div>

            <div v-else-if="releases.length > 0" class="space-y-4">
                <div v-if="enableOtherVersions">
                    <p class="text-sm text-warning flex gap-2">
                        <TriangleAlert class="w-4 h-4 shrink-0 text-warning" />
                        {{ $t('browndustxTab.modals.installFromGithub.enableOtherVersionsWarning') }}
                    </p>
                </div>
                <div class="space-y-2 overflow-y-auto max-h-96">
                    <div v-for="release in releases" :key="release.version">
                        <div
                            class="w-full flex items-center gap-3 p-3 border border-border-default rounded transition-opacity"
                            :class="[
                                release.version === recommendedVersion || enableOtherVersions
                                    ? ''
                                    : 'opacity-40 cursor-not-allowed select-none'
                            ]"
                        >
                            <div class="flex flex-col flex-1 items-start justify-center">
                                <div class="flex items-center gap-2">
                                    <span class="text-primary font-semibold">BepInEx {{ release.version }}</span>
                                    <span
                                        v-if="release.version === recommendedVersion"
                                        class="text-xs px-2.5 py-1 rounded-full bg-success-bg font-bold text-success "
                                    >
                                        {{ $t('browndustxTab.modals.installFromGithub.badges.recommended') }}
                                    </span>
                                </div>
                                <span class="text-sm font-mono text-text-secondary">
                                    {{ formatDate(release.published_at) }}
                                </span>
                            </div>
                            <Button
                                variant="default"
                                :icon="DownloadIcon"
                                :label="$t('browndustxTab.modals.installFromGithub.actions.install')"
                                :disabled="release.version !== recommendedVersion && !enableOtherVersions"
                                @click="handleVersionSelected(release.assets[0].download_url)"
                            />
                        </div>
                    </div>
                </div>

                <div class="border-border-default space-y-2">
                    <Checkbox
                        v-model="enableOtherVersions"
                        :label="$t('browndustxTab.modals.installFromGithub.options.enableOtherVersions')"
                    />
                </div>
            </div>

            <div v-else class="text-center py-8">
                <p class="text-text-secondary mb-2">{{ $t('browndustxTab.modals.installFromGithub.failedToLoadVersions') }}</p>
                <Button variant="primary" :label="$t('browndustxTab.modals.installFromGithub.actions.retry')" @click="getReleases" />
            </div>
        </div>
    </Modal>
</template>
