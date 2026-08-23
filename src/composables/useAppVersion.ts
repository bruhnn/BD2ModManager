import { ref } from "vue"
import { getVersion } from "@tauri-apps/api/app"

const appVersion = ref("0.0.0")

getVersion().then((version) => {
    appVersion.value = version
})

export function useAppVersion() {
    return { appVersion }
}
