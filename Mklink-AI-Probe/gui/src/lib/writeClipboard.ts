import { invoke, isTauri } from '@tauri-apps/api/core'

export async function writeClipboard(text: string, restoreFocus?: () => void): Promise<void> {
  if (isTauri()) {
    try { await invoke('clipboard_write_text', { text }); return }
    catch { /* A WebView may still have a browser clipboard. */ }
  }
  try {
    if (navigator.clipboard?.writeText) { await navigator.clipboard.writeText(text); return }
  } catch { /* Try a selection-based copy when permission is denied. */ }

  const previous = document.activeElement as HTMLElement | null
  const field = document.createElement('textarea')
  field.value = text
  field.readOnly = true
  field.style.cssText = 'position:fixed;opacity:0;pointer-events:none'
  // A modal makes the rest of the document inert, including an external selection.
  ;(previous?.closest('dialog[open]') || document.body).append(field)
  try {
    field.select()
    if (!document.execCommand?.('copy')) throw new Error('Clipboard write is unavailable')
  } finally {
    field.remove()
    if (restoreFocus) restoreFocus()
    else if (previous?.isConnected) previous.focus({ preventScroll: true })
  }
}
