import { defineStore } from "pinia";
import { ref } from "vue";

export interface LogMessage {
    level: 'success' | 'info' | 'warn' | 'error' | 'debug';
    scope: "All" | "BepInEx" | "BrownDustX" | "Configuration Manager";
    message: string;
    timestamp: string;
}

export const useModLoaderLogsStore = defineStore('modLoaderLogs', () => {
    const logs = ref([] as LogMessage[])

    return {
        logs
    }
})