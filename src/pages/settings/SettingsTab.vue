<script setup lang="ts">
import { Tab, TabGroup, TabList, TabPanels } from '@headlessui/vue';
import { CircleArrowUp, FlaskConical, Monitor, Settings } from '@lucide/vue';
import { computed, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import GeneralTab from './tabs/GeneralTab.vue';
import InterfaceTab from './tabs/InterfaceTab.vue';
import UpdateTab from './tabs/UpdateTab.vue';
import ExperimentalTab from './tabs/ExperimentalTab.vue';
import { useDev } from '../../composables/useDev.ts';


const { t } = useI18n()

const tabs = computed(() => [{
    label: t(`settingsTab.general.label`),
    value: 'general',
    icon: Settings,
}, {
    label: t('settingsTab.interface.label'),
    value: 'interface',
    icon: Monitor
}, {
    label: t('settingsTab.updates.label'),
    value: 'updates',
    icon: CircleArrowUp
}, {
    label: t('settingsTab.experimental.label'),
    value: 'experimental',
    icon: FlaskConical
}
])

const {
    isDev,
    setDevMode
} = useDev()

let pKey = ref('')

onMounted(() => {
    const keys = [
        'i', 'a', 'm', 'b', 'r', 'u', 'h', 'n', 'n'
    ]
    
    document.addEventListener('keydown', (event) => {
        if (event.key === keys[pKey.value.length]) {
            pKey.value += event.key
            if (pKey.value === keys.join('')) {
                setDevMode(!isDev.value)
                pKey.value = ''
            }
        } else {
            pKey.value = ''
        }
    })
})
</script>

<template>
    <div class="text-text-primary h-full overflow-y-auto flex flex-col w-full">
        <TabGroup>
            <div class="relative flex flex-col p-2">
                <TabList class="flex gap-1 transition-all">
                    <Tab v-for="tab in tabs" as="template" :key="tab.value" v-slot="{ selected }">
                        <button class="
                        px-4 py-2
                        text-center 
                        rounded 
                        transition-colors
                        text-md
                        cursor-pointer
                        ring-0 ring-transparent
                        hover:bg-state-hover
                        flex gap-1.5 items-center"
                            :class="{ 'bg-accent-muted! text-text-primary font-medium': selected, 'text-text-secondary': !selected }">
                            <component v-if="tab.icon" :is="tab.icon" :class="['w-[1.25em] h-[1.25em] text-text-primar']" />
                            {{ tab.label }}
                        </button>
                    </Tab>
                </TabList>
            </div>
            <TabPanels class="flex-1 p-4 py-2 w-full">
                <GeneralTab />
                <InterfaceTab />
                <UpdateTab />
                <ExperimentalTab />
            </TabPanels>
        </TabGroup>
    </div>
</template>

<style scoped></style>