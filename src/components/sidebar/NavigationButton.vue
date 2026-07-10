<script setup lang="ts">
import { computed } from 'vue';
import router from '../../router';

const props = defineProps<{
    icon?: any
    iconSrc?: string
    label: string
    value: string
}>()

defineEmits(["click"])

const active = computed(() => {
    return router.currentRoute.value.name === props.value
})
</script>
<template>
    <RouterLink :to="value" 
        :class="{ 
            'bg-accent! text-text-on-accent!': active, 
            'text-text-secondary': !active 
        }" 
        class="
        w-full px-3 py-2 gap-3 rounded-full 
        cursor-pointer capitalize
        transition-colors duration-200 transform active:scale-98
        flex items-center 
        text-sm font-medium
        hover:bg-state-hover hover:text-text-primary">
        <img v-if="iconSrc" :src="iconSrc" class="w-[1.75em] h-[1.75em] object-contain" />
        <component v-else :is="icon" class="w-[1.75em] h-[1.75em] text-text-primary transition-colors duration-200" :class="{'text-text-on-accent!': active}" />
        {{ label }}
        
    </RouterLink>
</template>
<style scoped></style>