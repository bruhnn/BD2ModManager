<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { openUrl } from '@tauri-apps/plugin-opener'
import { globalModals } from '../../composables/useGlobalModals'
import Modal from '../common/Modal.vue'
import Button from '../common/Button.vue'

const { t } = useI18n()
const { isOpen, closeModal } = globalModals.whatsNew

const versions = [
    {
        version: '4.3.0',
        highlights: [
            {
                title: 'whatsNew.release430.syncTitle',
                description: 'whatsNew.release430.syncDescription',
                details: [
                    { title: 'whatsNew.release430.syncManagedTitle', description: 'whatsNew.release430.syncManaged' },
                    { title: 'whatsNew.release430.syncUnmanagedTitle', description: 'whatsNew.release430.syncUnmanaged' },
                    { title: 'whatsNew.release430.syncReinstallTitle', description: 'whatsNew.release430.syncReinstall' },
                    { title: 'whatsNew.release430.syncFoldersTitle', description: 'whatsNew.release430.syncFolders' }
                ]
            },
            { title: 'whatsNew.release430.previewTitle', description: 'whatsNew.release430.previewDescription' }
        ],
        changelog: [
            'whatsNew.release430.modShortcuts',
            'whatsNew.release430.separateNotifications',
            'whatsNew.release430.gameDataNotification',
            'whatsNew.release430.characterFilters',
            'whatsNew.release430.unmanagedNotice',
            'whatsNew.release430.previewDownloads',
            'whatsNew.release430.updateSettings',
            'whatsNew.release430.updateChannels',
            'whatsNew.release430.renameDisplayName',
            'whatsNew.release430.stagingProtection',
            'whatsNew.release430.multipartDating',
            'whatsNew.release430.modSizeLimit',
            'whatsNew.release430.compareMods',
            'whatsNew.release430.characterTypeTabs',
            'whatsNew.release430.previewModToggle',
            'whatsNew.release430.autoSyncDelay',
            'whatsNew.release430.removeMissingProfileMods',
            'whatsNew.release430.activeDownloads',
            'whatsNew.release430.diskSpaceCheck',
            'whatsNew.release430.titlebarCredits',
            'whatsNew.release430.modLoaderDiscord',
            'whatsNew.release430.notificationActions',
            'whatsNew.release430.themeTransitions',
            'whatsNew.release430.managedMods',
            'whatsNew.release430.flatModFolders',
            'whatsNew.release430.syncProgress',
            'whatsNew.release430.syncResults',
            'whatsNew.release430.logFilters',
            'whatsNew.release430.releaseLogs',
            'whatsNew.release430.deletionRetry',
            'whatsNew.release430.updateControls',
            'whatsNew.release430.separateUpdateActions',
            'whatsNew.release430.groupedModErrors',
            'whatsNew.release430.translatedErrors',
            'whatsNew.release430.previewErrors',
            'whatsNew.release430.legacyProfiles',
            'whatsNew.release430.startupSettings',
            'whatsNew.release430.modalLayouts',
            'whatsNew.release430.notificationVisibility',
            'whatsNew.release430.folderMenuIcons',
            'whatsNew.release430.renamedProfileMods',
            'whatsNew.release430.checkboxToggle',
            'whatsNew.release430.nestedDirectories',
            'whatsNew.release430.sourceLinks',
            'whatsNew.release430.discoveryFailures',
            'whatsNew.release430.partialCopies',
            'whatsNew.release430.replacementRemoval',
            'whatsNew.release430.syncDeadlock',
            'whatsNew.release430.syncListeners',
            'whatsNew.release430.pendingAutoSync',
            'whatsNew.release430.syncCloseProtection',
            'whatsNew.release430.responsiveUpdates',
            'whatsNew.release430.repeatedUpdateChecks',
            'whatsNew.release430.failedUpdateIndicator',
            'whatsNew.release430.frontendRequests',
            'whatsNew.release430.characterAssets',
            'whatsNew.release430.standingPreviews',
            'whatsNew.release430.contributorTooltip',
            'whatsNew.release430.sidebarHeader',
            'whatsNew.release430.scrollbarCorner',
            'whatsNew.release430.modLoaderName',
            'whatsNew.release430.removedDiscovery'
        ]
    }
]
</script>

<template>
    <Modal :show="isOpen" :title="t('whatsNew.title')" size="lg" @close="closeModal">
        <div class="updates-content">
            <section v-for="(release, index) in versions" :key="release.version"
                class="version" :class="{ latest: index === 0 }">
                <div class="version-label">
                    <span class="version-dot" aria-hidden="true" />
                    <h3 class="version-number">
                        <span class="version-caption">{{ t('whatsNew.versionLabel') }}</span>
                        {{ release.version }}
                    </h3>
                </div>
                <div class="updates-sections">
                    <section v-for="highlight in release.highlights" :key="highlight.title" class="update-feature">
                        <h4 class="feature-title">{{ t(highlight.title) }}</h4>
                        <p class="feature-description">{{ t(highlight.description) }}</p>
                        <div v-for="detail in highlight.details" :key="detail.title" class="feature-detail">
                            <h5 class="detail-title">{{ t(detail.title) }}</h5>
                            <p class="feature-description">{{ t(detail.description) }}</p>
                        </div>
                    </section>
                    <section>
                        <h4 class="feature-title">{{ t('whatsNew.changelog') }}</h4>
                        <ul class="updates-list" :class="{ 'changelog-only': !release.highlights.length }">
                            <li v-for="item in release.changelog" :key="item">{{ t(item) }}</li>
                        </ul>
                    </section>
                </div>
            </section>
        </div>
        <template #footer>
            <div class="flex items-center justify-between gap-4 p-4">
                <button type="button" class="text-sm text-accent hover:underline cursor-pointer"
                    @click="openUrl('https://github.com/bruhnn/BD2ModManager/releases')">
                    {{ t('whatsNew.allReleases') }}
                </button>
                <Button :label="t('common.actions.close')" @click="closeModal" />
            </div>
        </template>
    </Modal>
</template>

<style scoped>
.updates-content {
    padding: 24px;
}

.version {
    position: relative;
    display: grid;
    grid-template-columns: 92px minmax(0, 1fr);
    gap: 12px;
    padding-bottom: 22px;
}

.version::before {
    content: '';
    position: absolute;
    left: 5px;
    top: 0;
    bottom: 0;
    width: 2px;
    background: var(--border-default);
}

.version:last-child {
    padding-bottom: 0;
}

.version:last-child::before {
    bottom: auto;
    height: 12px;
}

.version-label {
    position: sticky;
    top: 0;
    align-self: start;
    display: flex;
    gap: 12px;
    align-items: flex-start;
}

.version-dot {
    position: relative;
    z-index: 1;
    flex: none;
    width: 12px;
    height: 12px;
    margin-top: 6px;
    border-radius: 50%;
    background: var(--border-strong);
}

.version.latest .version-dot {
    background: var(--accent);
}

.version-number {
    min-width: 0;
    overflow-wrap: anywhere;
    font-size: 14px;
    line-height: 22px;
    font-weight: 600;
    color: var(--text-primary);
}

.version-caption {
    display: block;
    font-size: 10px;
    line-height: 16px;
    font-weight: 500;
    text-transform: uppercase;
    color: var(--text-secondary);
}

.updates-sections {
    display: flex;
    flex-direction: column;
    gap: 28px;
    min-width: 0;
}

.update-feature {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.feature-title {
    font-size: 16px;
    line-height: 24px;
    font-weight: 600;
    color: var(--text-primary);
}

.feature-description {
    font-size: 14px;
    line-height: 1.6;
    color: var(--text-secondary);
}

.feature-detail {
    margin-top: 8px;
}

.detail-title {
    margin-bottom: 6px;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
}

.updates-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 12px;
    padding-left: 20px;
    list-style: disc;
    font-size: 14px;
    line-height: 1.6;
    color: var(--text-primary);
}

.updates-list.changelog-only {
    margin-top: 0;
}

.updates-list li::marker {
    color: var(--text-secondary);
}

@media (max-width: 520px) {
    .updates-content {
        padding: 16px;
    }

    .version {
        grid-template-columns: 76px minmax(0, 1fr);
    }
}
</style>
