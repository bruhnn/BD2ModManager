import { ref, provide, inject, isRef, watch, onMounted, onActivated, onDeactivated, onUnmounted, type MaybeRef, Ref, ComputedRef } from 'vue'

const headerSymbol = Symbol('header')

interface HeaderButton {
  label?: MaybeRef<string>
  icon?: any
  class?: string
  action?: () => void | Promise<void>
  render?: () => any
  labelClass?: string
  variant?: 'default' | 'primary' | 'danger' | 'text'
}

interface HeaderContext {
  title: Ref<string>
  subtitle: Ref<string>
  buttons: Ref<HeaderButton[]>
  setTitle: (val: MaybeRef<string>) => void
  setSubtitle: (val: MaybeRef<string>) => void
  setButtons: (val: MaybeRef<HeaderButton[]>) => void
  restoreDefault: () => void
}

interface UseHeaderOptions {
  title?: MaybeRef<string>
  subtitle?: MaybeRef<string> | ComputedRef<string>
  buttons?: MaybeRef<HeaderButton[]>
}

export function provideHeader() {
  const title = ref<string>('')
  const subtitle = ref<string>('')
  const buttons = ref<HeaderButton[]>([])

  const setTitle = (val: MaybeRef<string>) => {
    title.value = isRef(val) ? val.value : val
  }
  const setSubtitle = (val: MaybeRef<string>) => {
    subtitle.value = isRef(val) ? val.value : val
  }
  const setButtons = (val: MaybeRef<HeaderButton[]>) => {
    buttons.value = isRef(val) ? val.value : val
  }
  const restoreDefault = () => {
    title.value = ''
    subtitle.value = ''
    buttons.value = []
  }

  provide(headerSymbol, {
    title,
    subtitle,
    buttons,
    setTitle,
    setSubtitle,
    setButtons,
    restoreDefault
  })

  return { title, subtitle, buttons, setTitle, setSubtitle, setButtons, restoreDefault }
}

export function useHeader(): HeaderContext
export function useHeader(options: UseHeaderOptions): void
export function useHeader(options?: UseHeaderOptions): HeaderContext | void {
  const header = inject<HeaderContext>(headerSymbol)
  if (!header) {
    throw new Error('useHeader must be used within provideHeader')
  }

  if (!options) return header

  const { title = '', subtitle = '', buttons = [] } = options
  const { setTitle, setSubtitle, setButtons, restoreDefault } = header

  const isActive = ref(false)
  const resolve = <T>(val: MaybeRef<T>): T => isRef(val) ? val.value : val

  const setup = () => {
    isActive.value = true
    setTitle(resolve(title))
    setSubtitle(resolve(subtitle))
    setButtons(resolve(buttons))
  }

  const teardown = () => {
    isActive.value = false
    restoreDefault()
  }

  if (isRef(title)) watch(title, (val) => { if (isActive.value) setTitle(val) })
  if (isRef(subtitle)) watch(subtitle, (val) => { if (isActive.value) setSubtitle(val) })
  if (isRef(buttons)) watch(buttons, (val) => { if (isActive.value) setButtons(val) }, { deep: true })

  onMounted(setup)
  onActivated(setup)
  onUnmounted(teardown)
  onDeactivated(teardown)
}