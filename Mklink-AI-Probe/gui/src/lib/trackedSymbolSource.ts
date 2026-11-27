import type { SemanticExecutionContext } from './frontendControl'
import { ref } from 'vue'
import { fileContentStamp } from './fileContent'
import { readSymbolHandle, saveSymbolHandle, type SavedSymbolHandle } from './symbolHandleStore'
import { symbolFileHandle } from './filePicker'
import { isSameFileSourcePath, loadDesktopSettings, saveDesktopSettings } from './desktopSettings'
import type { UploadedFileSource } from '../types/mklink'

export const trackedSymbolPath = ref('')
export const trackedSymbolError = ref('')
export const trackedSymbolPending = ref(0)
let revision = 0
let selection = 0
let cancel: (() => void) | undefined
let reload: ((context?: SemanticExecutionContext) => Promise<void>) | undefined

interface SymbolTrackingActions {
  upload(file: File, context?: SemanticExecutionContext): Promise<UploadedFileSource>
  reload(path: string, expectedPath: string, context?: SemanticExecutionContext): Promise<{ state?: string; rtt_addr?: string }>
}

export async function reloadTrackedSymbolSource(context?: SemanticExecutionContext): Promise<boolean> {
  if (!trackedSymbolPending.value || !reload) return false
  await reload(context)
  return true
}

export async function restoreSymbolSource(actions: SymbolTrackingActions): Promise<void> {
  const before = selection
  const saved = await readSymbolHandle().catch(() => undefined)
  if (before !== selection || !saved || !isSameFileSourcePath(loadDesktopSettings(window.localStorage).symbolPath, saved.source.path)) return
  startTracking(saved, actions)
}

export function trackSymbolSource(file: File, source: UploadedFileSource, actions: SymbolTrackingActions): void {
  ++selection
  cancel?.()
  trackedSymbolPath.value = ''
  trackedSymbolError.value = ''
  trackedSymbolPending.value = 0
  reload = undefined
  const handle = symbolFileHandle(file)
  const record = handle ? { handle, source, lastModified: file.lastModified } : null
  void saveSymbolHandle(record)
  if (record) startTracking(record, actions)
}

function startTracking({ handle, source, lastModified }: SavedSymbolHandle, actions: SymbolTrackingActions): void {
  cancel?.()
  let stopped = false
  let busy = false
  let timer: ReturnType<typeof setTimeout> | undefined
  let path = source.path
  let stamp = `${source.sha256}:${lastModified}`
  let observed = stamp
  let stableSince = 0
  let readError = ''
  let pending: { stamp: string } | undefined
  const current = () => !stopped && isSameFileSourcePath(loadDesktopSettings(window.localStorage).symbolPath, path)
  const clear = () => {
    trackedSymbolPath.value = ''
    trackedSymbolPending.value = 0
    reload = undefined
  }
  cancel = () => { stopped = true; if (timer !== undefined) clearTimeout(timer) }
  trackedSymbolPath.value = path
  reload = async context => {
    if (busy) throw new Error('Symbol reload is already in progress')
    if (!current() || !pending) { clear(); throw new Error('The selected symbol source changed') }
    busy = true
    const selected = pending
    try {
      const latest = await handle.getFile()
      const freshStamp = `${await fileContentStamp(latest)}:${latest.lastModified}`
      if (freshStamp !== selected.stamp) throw new Error('文件已再次更新，请等待编译完成后重新解析 / File changed again; retry when the build is complete.')
      const uploaded = await actions.upload(latest, context)
      if (!current()) throw new Error('The selected symbol source changed')
      const result = await actions.reload(uploaded.path, path, context)
      if (result.state !== 'applied') throw new Error('Symbols were not reloaded')
      if (!current()) return
      const settings = loadDesktopSettings(window.localStorage)
      path = uploaded.path
      saveDesktopSettings(window.localStorage, { ...settings, symbolPath: path,
        symbolDisplayPath: uploaded.name || latest.name, rttAddress: result.rtt_addr || '' })
      trackedSymbolPath.value = path
      void saveSymbolHandle({ handle, source: uploaded, lastModified: latest.lastModified })
      stamp = selected.stamp
      if (pending === selected) { pending = undefined; trackedSymbolPending.value = 0 }
      trackedSymbolError.value = ''
    } catch (error) {
      if (current()) trackedSymbolError.value = error instanceof Error ? error.message : String(error)
      throw error
    } finally { busy = false }
  }
  const poll = async () => {
    if (!current()) { if (!stopped) clear(); return }
    try {
      const next = await handle.getFile()
      const nextStamp = `${await fileContentStamp(next)}:${next.lastModified}`
      if (!current()) return
      if (readError && trackedSymbolError.value === readError) trackedSymbolError.value = ''
      readError = ''
      if (nextStamp === stamp && pending) { pending = undefined; trackedSymbolPending.value = 0 }
      if (nextStamp !== observed) { observed = nextStamp; stableSince = Date.now() }
      if (nextStamp !== stamp && nextStamp !== pending?.stamp && Date.now() - stableSince >= 2000) {
        pending = { stamp: nextStamp }
        trackedSymbolPending.value = ++revision
      }
    } catch (error) {
      readError = error instanceof DOMException && error.name === 'NotAllowedError'
        ? '请重新选择原 ELF / AXF 以恢复读取权限。 / Select the original file again to restore read access.'
        : error instanceof Error ? error.message : String(error)
      if (current()) trackedSymbolError.value = readError
    } finally {
      if (current()) timer = setTimeout(poll, 1000)
    }
  }
  timer = setTimeout(poll, 1000)
}
