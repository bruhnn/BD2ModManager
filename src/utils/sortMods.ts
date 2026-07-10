import type { BD2Mod } from '../stores/mods';

/** Last path segment (mod folder name), ignoring trailing separators. */
function basename(p: string): string {
    const parts = p.split(/[\\/]/).filter(Boolean);
    return parts.length ? parts[parts.length - 1] : p;
}

/** True when the character is a plain latin A-Z / a-z letter. */
function startsWithAToZ(name: string): boolean {
    return /^[A-Za-z]/.test(name);
}

/**
 * Returns a new array of mods sorted A-Z by their folder path on disk.
 * Non-mutating. Uses numeric-aware locale compare so that, e.g.,
 * `mod2` sorts before `mod10` rather than between `mod1` and `mod2`.
 *
 * Mods whose folder name does NOT start with an A-z letter (e.g. names
 * beginning with a number, symbol, or non-latin character) are pushed
 * BEHIND the A-z ones, then sorted amongst themselves.
 *
 * Used by the per-character mod modal and the NPC mod modal so that
 * installed mods are listed in stable alphabetical order regardless of
 * the order they come back from the backend.
 */
export function sortModsByPath(mods: readonly BD2Mod[]): BD2Mod[] {
    return [...mods].sort((a, b) => {
        const aAlpha = startsWithAToZ(basename(a.path));
        const bAlpha = startsWithAToZ(basename(b.path));
        if (aAlpha !== bAlpha) {
            // A-z names first, everything else behind.
            return aAlpha ? -1 : 1;
        }
        return a.path.localeCompare(b.path, undefined, { numeric: true, sensitivity: 'base' });
    });
}
