import { defineStore } from "pinia";
import { readonly, ref } from "vue";

export interface Notification {
    id: number,
    type: "info" | "success" | "error" | "warn" ,
    title?: string,
    message?: string,
    duration?: number,
    closable?: boolean,
    showProgress?: boolean,
    action?: {
        label: string,
        onClick: () => void
    }
}

const DEFAULT_DURATION = {
    error: 8000,
    warn: 5000,
    info: 3000,
    success: 3000,
}

export const useNotificationStore = defineStore("notification", () => {
    const notifications = ref<Notification[]>([]);

    function add(notification: Omit<Notification, "id">) {
        const id = Date.now()
        const duration = notification.duration ?? DEFAULT_DURATION[notification.type]
        notifications.value.push({ ...notification, id, duration })
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