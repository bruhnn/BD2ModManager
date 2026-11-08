import { createApp } from "vue";
import "@fontsource/cinzel/700.css";
import "@fontsource-variable/inter/wght.css";
import App from "./App.vue";
import router from "./router";
import "./styles/main.css";
import { createPinia } from "pinia";
import { i18n } from './i18n'
import ConfirmPlugin from "./plugins/ConfirmPlugin";
import { useSettingsStore } from "./stores/settings";
import { useThemesStore } from "./stores/themes";

const pinia = createPinia()

const app = createApp(App)
app.use(router)
.use(pinia)
.use(i18n)
.use(ConfirmPlugin)

// The theme is applied on the first render, so the settings and user themes have to be ready before mounting.
Promise.all([useSettingsStore().loadSettings(), useThemesStore().loadUserThemes()])
    .catch(error => console.error("Failed to load settings:", error))
    .finally(() => app.mount("#app"));
