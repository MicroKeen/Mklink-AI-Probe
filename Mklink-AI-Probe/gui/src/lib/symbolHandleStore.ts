import type { BrowserFirmwareFileHandle } from './filePicker'
import type { UploadedFileSource } from '../types/mklink'

export interface SavedSymbolHandle {
  handle: BrowserFirmwareFileHandle
  source: UploadedFileSource
  lastModified: number
}

// IndexedDB can retain a browser-granted handle without copying ELF contents.
// Scope it to the Web GUI endpoint (including a remote window behind a proxy).
const storeName = 'selected'
function endpointKey(): string {
  return new URL('./', window.location.href).pathname + '?' + (new URLSearchParams(window.location.search).get('remote') || '')
}

async function access(record?: SavedSymbolHandle | null): Promise<SavedSymbolHandle | undefined> {
  if (typeof indexedDB === 'undefined') return
  const db = await new Promise<IDBDatabase>((resolve, reject) => {
    const open = indexedDB.open('mklink-symbol-file-handles', 1)
    open.onupgradeneeded = () => open.result.createObjectStore(storeName)
    open.onerror = () => reject(open.error)
    open.onsuccess = () => resolve(open.result)
  })
  try {
    return await new Promise<SavedSymbolHandle | undefined>((resolve, reject) => {
      const tx = db.transaction(storeName, record === undefined ? 'readonly' : 'readwrite')
      const store = tx.objectStore(storeName)
      const key = endpointKey()
      const request = record === undefined ? store.get(key) : record === null ? store.delete(key) : store.put(record, key)
      tx.oncomplete = () => resolve(record === undefined ? request.result : undefined)
      tx.onabort = () => reject(tx.error)
    })
  } finally { db.close() }
}

export const readSymbolHandle = () => access()
export const saveSymbolHandle = (record: SavedSymbolHandle | null) => access(record).catch(() => undefined)
