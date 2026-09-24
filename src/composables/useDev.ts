import { useLocalStorage } from "@vueuse/core"
import { computed } from "vue"

export function useDev() {
    const isDev = computed(() => {
        if (useLocalStorage('isDev', false, { mergeDefaults: false }).value) {
            return true
        }
        return import.meta.env.DEV
    })

    function setDevMode(value: boolean) {
        useLocalStorage('isDev', false, { mergeDefaults: false }).value = value
    }

    return { isDev, setDevMode }
}