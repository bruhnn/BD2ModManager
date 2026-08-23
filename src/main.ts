import { createApp } from "vue";
import "@fontsource/cinzel/700.css";
import "@fontsource-variable/inter/wght.css";
import App from "./App.vue";
import router from "./router";
import "./styles/main.css";
import { createPinia } from "pinia";
import {createI18n} from 'vue-i18n'
import en_US from './locales/en-US.json'
import pt_BR from './locales/pt-BR.json'
import zh_CN from './locales/zh-CN.json'
import zh_TW from './locales/zh-TW.json'
import ja_JP from './locales/ja-JP.json'
import ko_KR from './locales/ko-KR.json'
import ConfirmPlugin from "./plugins/ConfirmPlugin";
import { useModsIndexStore } from "./stores/modsIndex";

const pinia = createPinia()

const i18n = createI18n({
    legacy: false,
    locale: 'en_US',
    fallbackLocale: 'en_US',
    messages: {
        en_US,
        zh_CN,
        zh_TW,
        ja_JP,
        ko_KR,
        pt_BR
    }
})

const app = createApp(App)
app.use(router)
.use(pinia)
.use(i18n)
.use(ConfirmPlugin)

const modsIndexStore =useModsIndexStore()
modsIndexStore.fetchModsIndex()

app.mount("#app");
