import { computed, ref } from "vue"
import { invoke } from "@tauri-apps/api/core"

const locale = ref<string | null>(null)

invoke<string>("get_user_locale").then((value) => {
    locale.value = value
})

const isChineseLanguage = computed(() =>
    locale.value?.toLowerCase().startsWith("zh") ?? false
)

export function useLocale() {
    return {
        locale,
        isChineseLanguage
    }
}
