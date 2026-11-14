import { API_BASE } from './runtimeEndpoint'
import { guiControl } from './guiControls'

export type GuiFile = { url: string; name: string; size: number; path?: string }
export const guiFileState = { state: 'idle', name: '', error: '' }
let pendingFile: File | string | null = null
let pendingDirectory: string | null = null
export function takeGuiDirectory(): string | null {
  const directory = pendingDirectory; pendingDirectory = null; return directory
}
export function selectGuiDirectory(id: string, path: string) {
  const el = guiControl(id)
  if (!el.hasAttribute('data-gui-directory-picker')) throw new Error('Choose a declared directory picker')
  pendingDirectory = path
  try { el.click(); if (pendingDirectory) throw new Error('Directory picker did not accept the supplied path') }
  finally { pendingDirectory = null }
}
export function takeGuiFile(): File | string | null {
  const file = pendingFile
  pendingFile = null
  return file
}
export function selectGuiFile(id: string, file: GuiFile, current: () => boolean) {
  if (guiFileState.state === 'loading') throw new Error('A file import is pending')
  const el = guiControl(id)
  if (!(el instanceof HTMLInputElement && el.type === 'file') && !el.hasAttribute('data-gui-file-picker')) {
    throw new Error('Choose a file input or a declared file picker')
  }
  if (!file || !file.url.startsWith('/api/runtime/control/gui-files/')) throw new Error('Invalid file delivery')
  guiFileState.state = 'loading'; guiFileState.name = file.name; guiFileState.error = ''
  void (async () => {
    try {
      const response = await fetch(`${API_BASE}${file.url}`, { signal: AbortSignal.timeout(60_000) })
      if (!response.ok) throw new Error('File delivery failed or expired')
      const blob = await response.blob()
      if (blob.size !== file.size) throw new Error('File changed during delivery')
      if (!current() || guiControl(id) !== el) throw new Error('Page/target/control changed during import')
      const selected = new File([blob], file.name)
      if (el instanceof HTMLInputElement) {
        const extensions = el.accept.split(',').filter(x => x.startsWith('.'))
        if (extensions.length && !extensions.some(x => file.name.toLowerCase().endsWith(x.toLowerCase()))) throw new Error('File type does not match this input')
        const transfer = new DataTransfer(); transfer.items.add(selected); el.files = transfer.files
        el.dispatchEvent(new Event('change', { bubbles: true }))
      } else {
        // A backend-local picker must retain the original symbol/firmware path:
        // sidecar settings and same-path rebuild detection depend on it.
        pendingFile = file.path || selected
        try { el.click(); if (pendingFile) throw new Error('File picker did not accept the supplied file') }
        finally { pendingFile = null }
      }
      // Existing component parsing may still be running; inspect panel state/errors.
      guiFileState.state = 'delivered'
    } catch (error) { guiFileState.state = 'failed'; guiFileState.error = String(error) }
  })()
}
