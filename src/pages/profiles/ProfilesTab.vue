<script setup lang="ts">
import { computed, ref, useTemplateRef } from 'vue'
import { useProfilesStore } from '../../stores/profiles'
import { Edit, ListChecks, PlusCircle, RefreshCcw, Trash2, TriangleAlert } from 'lucide-vue-next'
import { useHeader } from '../../composables/useHeader'
import { useI18n } from 'vue-i18n'
import EditProfile from './modals/EditProfile.vue'
import EditProfileMods from './modals/EditProfileMods.vue'
import CreateProfile from './modals/CreateProfile.vue'
import Button from '../../components/common/Button.vue'
import { useConfirm } from '../../plugins/ConfirmService'
import { useNotificationStore } from '../../stores/notification.ts'
import { usePreferencesStore } from '../../stores/preferences'

const profilesStore = useProfilesStore()
const notificationStore = useNotificationStore()
const preferencesStore = usePreferencesStore()
const confirm = useConfirm()
const { t } = useI18n()

const editProfileModal = useTemplateRef('editProfileModal')
const editProfileModsModal = useTemplateRef('editProfileModsModal')
const createProfileModal = useTemplateRef('createProfileModal')

const profileSelectedId = ref<string | null>('default')

const selectedProfile = computed(() => {
  if (!profileSelectedId.value) return null
  return profilesStore.getProfileById(profileSelectedId.value)
})

const sortedEnabledMods = computed(() => {
  if (!selectedProfile.value?.enabledMods) return []
  return [...selectedProfile.value.enabledMods].sort((a, b) => 
    a.localeCompare(b, undefined, { sensitivity: 'base' })
  )
})

function editSelected() {
  if (!profileSelectedId.value) return

  const profile = profilesStore.getProfileById(profileSelectedId.value)

  editProfileModal.value?.show({
    id: profile?.id || '',
    name: profile?.name || '',
    description: profile?.description || null
  })
}

function createNewProfile() {
  createProfileModal.value?.show(profilesStore.profiles)
}

async function deleteSelected() {
  if (!profileSelectedId.value || profileSelectedId.value === 'default') return

  const result = await confirm.confirm({
    title: t('profilesTab.confirmations.deleteProfile.title'),
    message: t('profilesTab.confirmations.deleteProfile.message', { profileName: selectedProfile.value?.name }),
    icon: TriangleAlert,
    acceptButton: {
      label: t('profilesTab.confirmations.deleteProfile.actions.deleteProfile'),
      position: 'right'
    },
    rejectButton: {
      label: t('common.actions.cancel'),
      position: 'right'
    }
  })

  if (!result.confirmed) return

  const deletedName = selectedProfile.value?.name

  try {
    await profilesStore.deleteProfile(profileSelectedId.value)
    profileSelectedId.value = null
    notificationStore.add({
      severity: 'success',
      title: t('profilesTab.notifications.profileDeleted.title'),
      message: t('profilesTab.notifications.profileDeleted.description', { profileName: deletedName }),
      duration: 3000
    })
  } catch {
    notificationStore.add({
      severity: 'error',
      title: t('profilesTab.notifications.profileDeleteFailed.title'),
      message: t('profilesTab.notifications.profileDeleteFailed.description', { profileName: deletedName }),
      duration: 3000
    })
  }
}

async function onProfileEdit(id: string, name: string, description: string | null) {
  try {
    await profilesStore.editProfile(id, name, description)
    notificationStore.add({
      severity: 'success',
      title: t('profilesTab.notifications.profileUpdated.title'),
      message: t('profilesTab.notifications.profileUpdated.description', { profileName: name }),
      duration: 3000
    })
  } catch {
    notificationStore.add({
      severity: 'error',
      title: t('profilesTab.notifications.profileUpdateFailed.title'),
      message: t('profilesTab.notifications.profileUpdateFailed.description', { profileName: name }),
      duration: 3000
    })
  }
}


function editModsSelected() {
  if (!profileSelectedId.value) return

  const profile = profilesStore.getProfileById(profileSelectedId.value)
  if (!profile) return

  editProfileModsModal.value?.show({
    id: profile.id,
    name: profile.name,
    enabledMods: [...(profile.enabledMods || [])]
  })
}

async function onProfileModsEdit(id: string, modNames: string[]) {
  const profile = profilesStore.getProfileById(id)
  try {
    await profilesStore.setProfileEnabledMods(id, modNames)
    notificationStore.add({
      severity: 'success',
      title: t('profilesTab.notifications.modsUpdated.title'),
      message: t('profilesTab.notifications.modsUpdated.description', { profileName: profile?.name }),
      duration: 3000
    })
  } catch {
    notificationStore.add({
      severity: 'error',
      title: t('profilesTab.notifications.modsUpdateFailed.title'),
      message: t('profilesTab.notifications.modsUpdateFailed.description', { profileName: profile?.name }),
      duration: 3000
    })
  }
}
async function onProfileCreate(
  name: string,
  description: string | null,
  profileTemplateId: string | null
) {
  try {
    await profilesStore.createProfile(name, description, profileTemplateId)
    notificationStore.add({
      severity: 'success',
      title: t('profilesTab.notifications.profileCreated.title'),
      message: t('profilesTab.notifications.profileCreated.description', { profileName: name }),
      duration: 3000
    })
  } catch {
    notificationStore.add({
      severity: 'error',
      title: t('profilesTab.notifications.profileCreateFailed.title'),
      message: t('profilesTab.notifications.profileCreateFailed.description', { profileName: name }),
      duration: 3000
    })
  }
}

async function onProfileSwitch(id: string) {
  const profile = profilesStore.getProfileById(id)
  try {
    await profilesStore.switchProfile(id)
  } catch {
    notificationStore.add({
      severity: 'error',
      title: t('profilesTab.notifications.profileSwitchFailed.title'),
      message: t('profilesTab.notifications.profileSwitchFailed.description', { profileName: profile?.name }),
      duration: 3000
    })
  }
}

async function refreshProfiles() {
  await profilesStore.loadProfiles()
}

useHeader({
  title: t('profilesTab.title'),
  subtitle: t('profilesTab.subtitle'),
  buttons: [
    {
      label: t('profilesTab.actions.refreshProfiles'),
      icon: RefreshCcw,
      action: refreshProfiles
    },
    {
      label: t('profilesTab.actions.createProfile'),
      icon: PlusCircle,
      action: createNewProfile
    }
  ]
})
</script>

<template>
  <div class="w-full h-full flex flex-col">
    <CreateProfile ref="createProfileModal" @on-profile-create="onProfileCreate" />
    <EditProfile ref="editProfileModal" @on-profile-edit="onProfileEdit" />
    <EditProfileMods ref="editProfileModsModal" @on-profile-mods-edit="onProfileModsEdit" />

    <div class="flex flex-col p-4 py-2 w-full h-full">
      <div class="w-full flex-1 border border-border-default rounded-lg bg-surface-panel flex overflow-hidden">

        <div class="flex-1 min-w-0 w-full overflow-y-auto border-r border-border-default">
          <div class="flex flex-col">
            <div
              v-for="profile in profilesStore.sortedProfiles"
              :key="profile.id"
              class="p-3 cursor-pointer flex items-center justify-between gap-2 hover:bg-state-hover transition-colors duration-150 border-b border-border-default"
              :class="profileSelectedId && profileSelectedId === profile.id
                ? 'bg-state-selected!'
                : 'bg-bg-surface'"
              @click="profileSelectedId = profile.id"
            >
              <div class="flex flex-col min-w-0 overflow-hidden">
                <span class="font-medium">{{ profile.name }}</span>
                <span class="text-sm text-text-secondary mt-1 truncate">
                  {{ profile.description === 'd3f4ult'
                    ? $t('profilesTab.defaultProfile')
                    : profile.description || $t('profilesTab.emptyDescription') }}
                </span>
              </div>

              <div>
                <span
                  v-if="profilesStore.activeProfileId === profile.id"
                  class="font-medium text-accent"
                >
                  {{ $t('profilesTab.activeProfile') }}
                </span>
                <span
                  v-else
                  class="font-medium whitespace-nowrap hover:text-accent-hover transition-colors duration-150 cursor-pointer"
                  @click.stop="onProfileSwitch(profile.id)"
                >
                  {{ $t('profilesTab.actions.setAsCurrent') }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div class="flex-1 min-w-0 p-4 box-border">
          <div v-if="selectedProfile" class="flex flex-col gap-4 h-full">

            <div class="flex justify-between items-center gap-2">
              <div class="overflow-hidden min-w-0">
                <h3 class="font-bold text-lg">{{ selectedProfile.name }}</h3>
                <p class="text-text-secondary text-sm truncate">
                  {{ selectedProfile.description === 'd3f4ult'
                    ? $t('profilesTab.defaultProfile')
                    : selectedProfile.description || $t('profilesTab.emptyDescription') }}
                </p>
              </div>

              <div class="flex gap-2">
                <Button
                  variant="text"
                  :label="$t('profilesTab.actions.editProfile')"
                  :icon="Edit"
                  @click="editSelected"
                />
                <Button
                  v-if="preferencesStore.showEditModsButton"
                  variant="text"
                  :label="$t('profilesTab.actions.editMods')"
                  :icon="ListChecks"
                  @click="editModsSelected"
                />
                <Button
                  variant="text"
                  :label="$t('profilesTab.actions.deleteProfile')"
                  :icon="Trash2"
                  :disabled="selectedProfile.id === 'default'"
                  @click="deleteSelected"
                />
              </div>
            </div>

            <div class="flex flex-col gap-1 h-full flex-1 overflow-y-auto">
              <h4 class="font-semibold text-base text-text-primary">
                {{ $t('profilesTab.enabledMods', { count: sortedEnabledMods.length }) }}
              </h4>

              <div class="flex flex-col gap-1 bg-surface-card rounded-md p-2 flex-1 h-full overflow-y-auto select-text scrollbar-hide">
                <div
                  v-for="mod in sortedEnabledMods"
                  :key="mod"
                  class="text-sm text-text-secondary hover:bg-state-hover break-all"
                >
                  {{ mod }}
                </div>

                <div
                  v-if="sortedEnabledMods.length === 0"
                  class="text-sm text-text-secondary italic"
                >
                  {{ $t('profilesTab.noModsEnabled') }}
                </div>
              </div>
            </div>
          </div>

          <div v-else class="text-text-secondary text-center mt-8">
            {{ $t('profilesTab.noProfileSelected') }}
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

<style scoped></style>