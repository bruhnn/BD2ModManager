import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Language } from '../stores/settings'
import { Character } from '../stores/characters'
import { usePreferencesStore } from '../stores/preferences'

export function useLang() {
    const { locale } = useI18n()
    const preferencesStore = usePreferencesStore()
    return computed((): Language => {
        if (preferencesStore.forceEnglishNames) return 'en'
        const raw = locale.value?.split('_')[1]?.toLowerCase()
        return (raw as Language) ?? 'en'
    })
}

export function formatCharName(costume: Character, lang: Language): string {
    return `${costume.character_name[lang] ?? costume.character_name.en} - ${costume.costume_name[lang] ?? costume.costume_name.en}`
}

export function getCharName(costume: Character, lang: Language): { character: string; costume: string } {
    return {
        character: costume.character_name[lang] ?? costume.character_name.en,
        costume: costume.costume_name[lang] ?? costume.costume_name.en
    }
}

export function getCharNameInAllLangs(costume: Character): { character: string; costume: string }[] {
    const langs = Array.from(new Set([
        ...Object.keys(costume.character_name),
        ...Object.keys(costume.costume_name)
    ])) as Language[]

    return langs.map(lang => ({
        character: costume.character_name[lang] ?? costume.character_name.en,
        costume: costume.costume_name[lang] ?? costume.costume_name.en
    }))
}