import { nextTick, onBeforeUnmount, shallowRef } from 'vue'

interface PictureWindowAPI { requestWindow(options: { width: number; height: number }): Promise<Window> }
export function usePanelFloat() {
  const api = (window as Window & { documentPictureInPicture?: PictureWindowAPI }).documentPictureInPicture
  const current = shallowRef<{ id: string; win: Window; mount: HTMLElement } | null>(null)
  let generation = 0
  let cleanup: (() => void) | undefined
  function close() {
    generation++
    const old = current.value
    current.value = null
    cleanup?.(); cleanup = undefined
    // Let Vue return the live subtree before the browser destroys the document.
    if (old && !old.win.closed) void nextTick(() => old.win.close())
  }
  async function open(id: string, title: string, origin: HTMLElement) {
    if (!api) throw Error('Document Picture-in-Picture is unavailable')
    if (current.value) {
      current.value = { ...current.value, id }
      current.value.win.document.title = title
      current.value.win.focus()
      return
    }
    const token = ++generation
    const win = await api.requestWindow({ width: 680, height: 480 })
    if (token !== generation || !origin.isConnected) { win.close(); return }
    const doc = win.document
    try {
      doc.title = title
      const copied = new Map<Element, Element>()
      function styles() {
        for (const el of document.head.querySelectorAll('style,link[rel="stylesheet"]')) {
          if (!copied.has(el)) {
            const clone = el.cloneNode(true) as HTMLStyleElement | HTMLLinkElement
            if (el instanceof HTMLLinkElement) (clone as HTMLLinkElement).href = el.href
            doc.head.append(clone); copied.set(el, clone)
          }
        }
        for (const [source, clone] of copied) if (!source.isConnected) { clone.remove(); copied.delete(source) }
      }
      const mount = doc.createElement('main')
      mount.className = 'workbench-float-host'
      doc.body.append(mount)
      function appearance() {
        doc.documentElement.dataset.theme = document.documentElement.dataset.theme
        doc.documentElement.lang = document.documentElement.lang
        doc.documentElement.style.colorScheme = document.documentElement.style.colorScheme
        mount.inert = !!origin.closest('[inert]')
      }
      styles(); appearance()
      const styleChanges = new MutationObserver(styles), stateChanges = new MutationObserver(appearance)
      styleChanges.observe(document.head, { childList: true })
      stateChanges.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'lang', 'style'] })
      for (let el: HTMLElement | null = origin; el && el !== document.documentElement; el = el.parentElement)
        stateChanges.observe(el, { attributes: true, attributeFilter: ['inert'] })
      const returned = () => { if (current.value?.win === win) close() }
      win.addEventListener('pagehide', returned, { once: true })
      cleanup = () => { styleChanges.disconnect(); stateChanges.disconnect(); win.removeEventListener('pagehide', returned) }
      current.value = { id, win, mount }
    } catch (error) { win.close(); throw error }
  }
  onBeforeUnmount(close)
  return { supported: !!api, current, open, close }
}
