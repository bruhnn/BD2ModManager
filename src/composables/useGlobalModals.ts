import { readonly, ref } from 'vue'

// import type { BD2ModExtended  } from '../stores/mods'
import type { Error as StructuredError } from '../utils/errors'

const activeModal = ref<symbol | null>(null)
const closeHandlers = new Map<symbol, (openNext: boolean) => void>()
const queue: Array<{ id: symbol, open: () => void }> = []

function openNextModal() {
  if (activeModal.value !== null) return
  queue.shift()?.open()
}

function createModal<T = void>(options?: { force?: boolean }) {
  const id = Symbol()
  const isOpen = ref(false)
  const params = ref<T | null>(null)

  function openNow(value?: T) {
    params.value = value ?? null
    isOpen.value = true
    activeModal.value = id
  }

  function close(openNext: boolean) {
    if (!isOpen.value) return

    isOpen.value = false
    params.value = null
    if (activeModal.value === id) {
      activeModal.value = null
    }

    if (openNext) openNextModal()
  }

  function closeModal() {
    close(true)
  }

  function showModal(value?: T) {
    console.log(`showModal called for modal id: ${id.toString()}, activeModal: ${activeModal.value?.toString()}`)

    if (activeModal.value === id) {
      params.value = value ?? null
      return
    }

    if (activeModal.value !== null) {
      if (options?.force) {
        const queuedIndex = queue.findIndex((item) => item.id === id)
        if (queuedIndex !== -1) queue.splice(queuedIndex, 1)

        const closeCurrent = closeHandlers.get(activeModal.value)
        closeCurrent?.(false)
        openNow(value)
        return
      }

      const queuedModal = queue.find((item) => item.id === id)
      const open = () => openNow(value)

      if (queuedModal) {
        queuedModal.open = open
      } else {
        queue.push({ id, open })
      }
      return
    }

    openNow(value)
  }

  closeHandlers.set(id, close)

  return { isOpen: readonly(isOpen), params: readonly(params), showModal, closeModal }
}

export const globalModals = {
  welcome: createModal(),
  logs: createModal(),
  sync: createModal(),
  modsDeleteFailed: createModal<{
    failed: Record<string, Omit<StructuredError, 'parent'>>
    onRetry?: () => boolean | Promise<boolean>
  }>(),
  // conflict: createModal<{ mod?: BD2ModExtended }>(),
}
