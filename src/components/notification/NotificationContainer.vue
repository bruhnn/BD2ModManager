<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useNotificationStore } from '../../stores/notification'
import Notification from './Notification.vue'

const notificationStore = useNotificationStore()

const { notifications } = storeToRefs(notificationStore)

const props = withDefaults(
    defineProps<{
        position?:
        | 'top-left'
        | 'top-right'
        | 'bottom-left'
        | 'bottom-right'
        | 'top-center'
        | 'bottom-center'
    }>(),
    {
        position: 'top-right',
    }
)

const config = computed(() => {
    switch (props.position) {
        case 'top-left':
            return {
                classes: 'top-4 left-4 items-start',
                alignment: 'items-start',
                transition: 'notification-left',
            }

        case 'top-right':
            return {
                classes: 'top-4 right-4 items-end',
                alignment: 'items-end',
                transition: 'notification-right',
            }

        case 'bottom-left':
            return {
                classes: 'bottom-4 left-4 items-start',
                alignment: 'items-start',
                transition: 'notification-left',
            }

        case 'bottom-right':
            return {
                classes: 'bottom-4 right-4 items-end',
                alignment: 'items-end',
                transition: 'notification-right',
            }

        case 'top-center':
            return {
                classes: 'top-4 left-1/2 -translate-x-1/2 items-center',
                alignment: 'items-center',
                transition: 'notification-top',
            }

        case 'bottom-center':
            return {
                classes: 'bottom-4 left-1/2 -translate-x-1/2 items-center',
                alignment: 'items-center',
                transition: 'notification-bottom',
            }

        default:
            return {
                classes: 'top-4 right-4 items-end',
                alignment: 'items-end',
                transition: 'notification-right',
            }
    }
})

function onLeave(el: Element) {
    const elem = el as HTMLElement
    elem.style.height = `${elem.offsetHeight}px`
    requestAnimationFrame(() => {
        elem.style.height = '0'
        elem.style.marginTop = '0'
    })
}

// [TODO] fix close/enter animation of others position but bottom-center
// fix order of notifications on top (newest on top instead of bottom)
</script>

<template>
    <div :class="`fixed z-50 ${config.classes}`">
        <TransitionGroup :name="config.transition" tag="div" :class="['relative flex flex-col', config.alignment]" @leave="onLeave">
            <Notification v-for="notification in notifications" :key="notification.id" :notification="notification"
                class="mt-3 first:mt-0" @close="notificationStore.remove" />
        </TransitionGroup>
    </div>
</template>

<style scoped>
.notification-left-move,
.notification-right-move,
.notification-top-move,
.notification-bottom-move {
    transition: transform 200ms ease-in-out;
}

.notification-left-enter-active,
.notification-right-enter-active,
.notification-top-enter-active,
.notification-bottom-enter-active {
    transition: opacity 200ms ease-in-out, transform 200ms ease-in-out;
}

.notification-left-leave-active,
.notification-right-leave-active,
.notification-top-leave-active,
.notification-bottom-leave-active {
    transition: opacity 200ms ease-in-out, transform 200ms ease-in-out, height 200ms ease-in-out, margin 200ms ease-in-out;
    overflow: hidden;
}

.notification-right-enter-from,
.notification-right-leave-to {
    opacity: 0;
    transform: translateY(100%);
}


.notification-left-enter-from,
.notification-left-leave-to {
    opacity: 0;
    transform: translateY(100%);
}

.notification-top-enter-from,
.notification-top-leave-to {
    opacity: 0;
    transform: translateY(-100%);
}

.notification-bottom-enter-from,
.notification-bottom-leave-to {
    opacity: 0;
    transform: translateY(100%);
}
</style>
