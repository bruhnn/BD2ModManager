import { computed, readonly, ref, watch } from "vue"
import { useSettingsStore } from "./settings"
import { defineStore } from "pinia"
import { invoke } from "@tauri-apps/api/core"
import { useLoggingStore } from "./logging"
import { useNotificationStore } from "./notification"
import { getErrorMessage } from "../utils/errors"
import { i18n } from "../i18n"

export interface UserTheme {
    name: string
    author?: string
    colors: Record<string, string>
}

const APP_THEMES = [
    { label: 'Dark 1', value: 'dark-1' },
    { label: 'Dark 2', value: 'dark-2' },
    { label: 'Dark 3', value: 'dark-3' },
    { label: 'Dark 4', value: 'dark-4' },
    { label: 'Light 1', value: 'light-1' },
    { label: 'Light 2', value: 'light-2' },
]

const T = 'settingsTab.general.sections.application.theme'

export const useThemesStore = defineStore('themes', () => {
    const t = i18n.global.t
    const logging = useLoggingStore()
    const notificationStore = useNotificationStore()
    const settingsStore = useSettingsStore()

    const userThemes = ref<UserTheme[]>([])
    const currentTheme = computed(() => settingsStore.settings.theme)
    const isCurrentThemeUserTheme = computed(() => userThemes.value.some(theme => theme.name === currentTheme.value))

    const availableThemes = computed(() => [
        ...APP_THEMES,
        ...userThemes.value.map(theme => ({ label: `${theme.name} (${theme.author || t(`${T}.unknownAuthor`)})`, value: theme.name })),
    ])

    async function loadUserThemes() {
        try {
            userThemes.value = await invoke<UserTheme[]>("get_user_themes")
        } catch (error) {
            logging.logError("Failed to load user themes:", error)
        }
    }

    async function createUserTheme(theme: UserTheme): Promise<boolean> {
        try {
            await invoke("create_user_theme", { theme })
            userThemes.value.push(theme)
            notificationStore.add({ type: 'success', message: t(`${T}.notifications.created`, { name: theme.name }) })
            return true
        } catch (error) {
            logging.logError("Failed to create user theme:", error)
            notificationStore.add({
                type: 'error',
                title: t(`${T}.notifications.createFailed`),
                message: getErrorMessage(t, error),
            })
            return false
        }
    }

    async function updateUserTheme(oldName: string, theme: UserTheme): Promise<boolean> {
        try {
            await invoke("update_user_theme", { oldName, theme })
            userThemes.value = userThemes.value.map(t => t.name === oldName ? theme : t)
            if (oldName !== theme.name && currentTheme.value === oldName) {
                await settingsStore.saveSettings({ theme: theme.name })
            }
            notificationStore.add({ type: 'success', message: t(`${T}.notifications.updated`, { name: theme.name }) })
            return true
        } catch (error) {
            logging.logError("Failed to update user theme:", error)
            notificationStore.add({
                type: 'error',
                title: t(`${T}.notifications.updateFailed`),
                message: getErrorMessage(t, error),
            })
            return false
        }
    }

    async function deleteUserTheme(name: string) {
        try {
            await invoke("delete_user_theme", { themeName: name })
            userThemes.value = userThemes.value.filter(t => t.name !== name)
            if (currentTheme.value === name) {
                await settingsStore.saveSettings({ theme: 'dark-1' })
            }
            notificationStore.add({ type: 'success', message: t(`${T}.notifications.deleted`, { name }) })
        } catch (error) {
            logging.logError("Failed to delete user theme:", error)
            notificationStore.add({
                type: 'error',
                title: t(`${T}.notifications.deleteFailed`),
                message: getErrorMessage(t, error),
            })
        }
    }

    // one <style> tag with a [data-theme="name"]  per user theme
    const styleElem = document.querySelector<HTMLStyleElement>('#user-themes') ?? document.createElement('style')
    styleElem.id = 'user-themes'
    document.head.appendChild(styleElem)

    watch(userThemes, (themes) => {
        styleElem.textContent = themes.map(theme => {
            const vars = Object.entries(theme.colors).map(([key, value]) => `--${key}: ${value};`).join(' ')
            return `[data-theme=${JSON.stringify(theme.name)}] { ${vars} }`
        }).join('\n')
    }, { immediate: true, deep: true })

    return {
        availableThemes: readonly(availableThemes),
        userThemes: readonly(userThemes),
        currentTheme,
        isCurrentThemeUserTheme,
        loadUserThemes,
        createUserTheme,
        updateUserTheme,
        deleteUserTheme,
    }
})
