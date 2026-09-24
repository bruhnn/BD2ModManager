import { defineStore } from "pinia";
import { readonly, ref } from "vue";

export interface Notification {
    id: number,
    type: "info" | "success" | "error" | "warn" ,
    title?: string,
    message?: string,
    duration?: number,
    closable?: boolean,
    action?: {
        label: string,
        onClick: () => void
    }
}

const DEFAULT_DURATION = {
    error: 10000,
    warn: 8000,
    info: 5000,
    success: 5000,
}

export const useNotificationStore = defineStore("notification", () => {
    const notifications = ref<Notification[]>([]);

    function add(notification: Omit<Notification, "id">) {
        const id = Date.now()
        const duration = notification.duration ?? DEFAULT_DURATION[notification.type]
        notifications.value.push({ ...notification, id, duration })
        return id
    }

    function remove(id: number) {
        notifications.value = notifications.value.filter(n => n.id !== id);
    }

    return {
        notifications: readonly(notifications),
        add,
        remove
    }
})