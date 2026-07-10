import { computed, readonly, shallowRef } from "vue";
import { defineStore } from "pinia";
import { timeOperation } from "../utils/timeOp";
import { invoke } from "@tauri-apps/api/core";
import { Language } from "./settings";

export interface Character {
    id: string | readonly string[];
    character: string;
    costume: string;
    character_image: string;
    character_skill_preview?: string;
    standing?: boolean;
    cutscene?: boolean;
    dating_id?: string;
    release_date?: string;
    is_collab?: boolean;
    gender?: string;
    npc_id?: string;

    // new keys
    costume_id: string,
    character_id: Int16Array,
    character_name: { [Lang in Language]: string }
    costume_name: { [Lang in Language]: string }
    skin_type: "normal" | "special" | "prestige"
    grade: number
    element: "dark" | "light" | "water" | "fire" | "wind"
}

/** A single labelled affection entry within a dating definition. */
export interface AffectionEntry {
    /** Label from dating.txt, e.g. "1", "2-1", "2-2". */
    label: string;
    /** Scene mod id (matches modType.id for a Scene-typed mod). */
    id: string;
}

/** A dating character entry from dating.json. */
export interface DatingDefinition {
    dating_id: string;
    costume_id: string;
    character: string;
    costume: string;
    affection: AffectionEntry[];
}

interface CharactersJson {
    characters: Character[];
    dating: DatingMap;
}

interface DatingJson {
    dating: DatingDefinition[];
}

type DatingMap = Record<string, string>;

export function isCostumeNew(costume: Character): boolean {
    if (!costume.release_date) return false;

    const daysCount = 7;
    const releaseDate = new Date(costume.release_date).getTime();
    const daysAgo = Date.now() - daysCount * 24 * 60 * 60 * 1000;

    return releaseDate > daysAgo;
}

export const useCharactersStore = defineStore("characters", () => {
    const characters = shallowRef<Character[]>([]);
    const datingMap = shallowRef<DatingMap>({});
    const charactersMap = shallowRef<Record<string, Character>>({});
    const datingToCharacterMap = shallowRef<Record<string, Character>>({});

    // Dating affection data from dating.json
    const datingDefinitions = shallowRef<DatingDefinition[]>([]);
    const datingDefinitionsMap = shallowRef<Record<string, DatingDefinition>>({});

    const groupedCharacters = computed<Record<string, Character[]>>(() => {
        return characters.value.reduce((acc, c) => {
            if (!acc[c.character]) {
                acc[c.character] = [];
            }
            acc[c.character].push(c);
            return acc;
        }, {} as Record<string, Character[]>);
    });

    function updateCharacters(data: CharactersJson) {
        timeOperation(() => {
            characters.value = data.characters
            datingMap.value = data.dating;

            charactersMap.value = Object.fromEntries(
                data.characters.flatMap((c) => {
                    if (Array.isArray(c.id)) {
                        return c.id.map(id => [id, c] as [string, Character]);
                    }
                    return [[c.id, c]] as [string, Character][];
                })
            );

            datingToCharacterMap.value = Object.fromEntries(
                Object.entries(data.dating)
                    .map(([key, id]) => {
                        const character = getCharacterById(id);
                        return character ? [key, character] : null;
                    })
                    .filter((entry): entry is [string, Character] => entry !== null)
            );

            console.log(charactersMap.value)
        }, `updateCharacters (${data.characters.length} characters, ${Object.keys(data.dating).length} dating mappings)`);
    }

    function getCharacterById(id: string): Character | null {
        return timeOperation(() => {
            return charactersMap.value[id] || null;
        }, `getCharacterById(${id})`, false);
    }

    function getCharacterByDatingId(datingId: string): Character | null {
        return timeOperation(() => {
            return datingToCharacterMap.value[datingId] || null;
        }, `getCharacterByDatingId(${datingId})`, false);
    }

    function getCharacterIdByDatingId(datingId: string): string | null {
        return timeOperation(() => {
            return datingMap.value[datingId] || null;
        }, `getCharacterIdByDatingId(${datingId})`, false);
    }

    function getCharacterByNpcId(npcId: string): Character | null {
        return timeOperation(() => {
            return characters.value.find(char => char.npc_id === npcId) || null;
        }, `getCharacterByNpcId(${npcId})`, false);
    }

    function updateDating(data: DatingJson) {
        datingDefinitions.value = data.dating ?? [];
        datingDefinitionsMap.value = Object.fromEntries(
            (data.dating ?? []).map(d => [d.dating_id, d])
        );
    }

    /** Returns the labelled affection list for a dating_id, or []. */
    function getAffection(datingId: string): AffectionEntry[] {
        return datingDefinitionsMap.value[datingId]?.affection ?? [];
    }

    async function loadDating() {
        try {
            const data = await invoke<DatingJson>("get_dating");
            updateDating(data);
            if (import.meta.env.DEV)
                console.info("Dating definitions loaded:", datingDefinitions.value.length);
        } catch (error) {
            console.error("Failed to load dating definitions:", error);
        }
    }

    async function loadCharacters() {
        try {
            const data = await invoke<CharactersJson>("get_characters");
            updateCharacters(data);
            if (import.meta.env.DEV)
                console.info("Local characters loaded:", characters.value.length);
        } catch (error) {
            console.error("Failed to load local characters:", error);
        }
    }

    return {
        characters: readonly(characters),
        datingDefinitions: readonly(datingDefinitions),
        groupedCharacters: readonly(groupedCharacters),
        loadCharacters,
        loadDating,
        getCharacterById,
        getCharacterByDatingId,
        getCharacterIdByDatingId,
        getCharacterByNpcId,
        getAffection,
    };
});