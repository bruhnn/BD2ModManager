<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import type { Notification } from '../../stores/notification'
import { AlertOctagon, AlertTriangle, Check, X } from '@lucide/vue'

const props = defineProps<{
    notification: Notification
}>()

const emit = defineEmits<{
    close: [id: number]
}>()

const progress = ref(100)

onMounted(() => {
    startProgress()
})

onUnmounted(() => {
    stopProgress()
})

function close() {
    stopProgress()
    emit('close', props.notification.id)
}

let stopped = false

function startProgress() {
    if (!props.notification.duration) return

    const duration = props.notification.duration
    const start = performance.now()

    function animate(time: number) {
        if (stopped) return

        const percent = Math.min((time - start) / duration, 1)
        progress.value = 100 * (1 - percent)

        if (percent < 1) {
            requestAnimationFrame(animate)
        } else {
            progress.value = 0
            close()
        }
    }

    requestAnimationFrame(animate)
}

function stopProgress() {
    stopped = true
}

</script>

<template>
    <div class="w-80 rounded-md border border-border-default bg-surface-popover shadow-lg text-sm overflow-hidden">
        <div class="flex items-start gap-3 p-3">
            <span v-if="notification.severity === 'success'" class="relative w-4 h-4 shrink-0 mt-0.5">
                <Check class="absolute inset-0 text-text-secondary w-4 h-4" />
                <svg class="absolute inset-0 w-0 h-0 overflow-visible" aria-hidden="true">
                    <defs>
                        <clipPath :id="`clip-success-${notification.id}`" clipPathUnits="objectBoundingBox">
                            <rect x="0" y="0" :width="Math.min(Math.max(progress / 100 + 0.08, 0), 1)" height="1" />
                        </clipPath>
                    </defs>
                </svg>
                <Check class="absolute inset-0 text-success w-4 h-4"
                    :style="{ clipPath: `url(#clip-success-${notification.id})` }" />
            </span>
            <span v-else-if="notification.severity === 'error'" class="relative w-4 h-4 shrink-0 mt-0.5">
                <AlertOctagon class="absolute inset-0 text-text-secondary w-4 h-4" />
                <svg class="absolute inset-0 w-0 h-0 overflow-visible" aria-hidden="true">
                    <defs>
                        <clipPath :id="`clip-error-${notification.id}`" clipPathUnits="objectBoundingBox">
                            <rect x="0" y="0" :width="Math.min(Math.max(progress / 100 + 0.08, 0), 1)" height="1" />
                        </clipPath>
                    </defs>
                </svg>
                <AlertOctagon class="absolute inset-0 text-error w-4 h-4"
                    :style="{ clipPath: `url(#clip-error-${notification.id})` }" />
            </span>

            <span v-else class="relative w-4 h-4 shrink-0 mt-0.5">
                <AlertTriangle class="absolute inset-0 text-text-secondary w-4 h-4" />
                <svg class="absolute inset-0 w-0 h-0 overflow-visible" aria-hidden="true">
                    <defs>
                        <clipPath :id="`clip-warn-${notification.id}`" clipPathUnits="objectBoundingBox">
                            <rect x="0" y="0" :width="Math.min(Math.max(progress / 100 + 0.08, 0), 1)" height="1" />
                        </clipPath>
                    </defs>
                </svg>
                <AlertTriangle class="absolute inset-0 text-warning w-4 h-4"
                    :style="{ clipPath: `url(#clip-warn-${notification.id})` }" />
            </span>

            <div class="flex-1 min-w-0">
                <p class="font-medium text-text-primary">
                    {{ notification.title }}
                </p>

                <p v-if="notification.message" class="text-text-secondary text-xs mt-0.5">
                    {{ notification.message }}
                </p>
            </div>

            <button @click="close"
                class="text-text-secondary hover:text-text-primary transition-colors shrink-0 cursor-pointer">
                <X class="w-4 h-4" />
            </button>
        </div>

        <!-- <div v-if="notification.duration" class="h-1 bg-border-default">
            <div class="h-full bg-accent" :style="{ width: `${progress}%` }" />
        </div> -->
    </div>
</template>