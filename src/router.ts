import { createMemoryHistory, createRouter } from 'vue-router'
import ModsTab from './pages/mods/ModsTab.vue'
import CharactersTab from './pages/characters/CharactersTab.vue'
import SettingsTab from './pages/settings/SettingsTab.vue'
import ProfilesTab from './pages/profiles/ProfilesTab.vue'
import ModLoaderTab from './pages/mod-loader/ModLoaderTab.vue'
import ScenesTab from './pages/scenes/ScenesTab.vue'
import NpcsTab from './pages/npcs/NpcsTab.vue'

const routes = [
    {
        path: '/',
        redirect: '/mods'
    },
    {
        name: 'mods',
        path: '/mods',
        component: ModsTab
    },
    {
        name: 'characters',
        path: '/characters',
        component: CharactersTab
    },
    {
        name: 'scenes',
        path: '/scenes',
        component: ScenesTab
    },
    {
        name: 'npcs',
        path: '/npcs',
        component: NpcsTab
    },
    {
        name: 'profiles',
        path: '/profiles',
        component: ProfilesTab
    },
    {
        name: 'mod-loader',
        path: '/mod-loader',
        component: ModLoaderTab
    },
    {
        name: 'settings',
        path: '/settings',
        component: SettingsTab,
        meta: { title: 'Settings' }
    }
]

const router = createRouter({
    history: createMemoryHistory(),
    routes
})

export default router   