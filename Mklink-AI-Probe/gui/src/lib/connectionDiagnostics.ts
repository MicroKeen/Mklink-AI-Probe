import { API_BASE, IS_REMOTE } from './runtimeEndpoint'

type Entry = { event: 'status_failed' | 'status_restored'; time: string; message: string }
const pending: Entry[] = []
let failed = false
let flushing: Promise<void> | null = null

export function recordStatusFailure(error: unknown) {
  if (IS_REMOTE || failed) return
  failed = true
  pending.push({ event: 'status_failed', time: new Date().toISOString(),
    message: (error instanceof Error ? `${error.name}: ${error.message}` : 'Status request failed').slice(0, 512) })
  if (pending.length > 25) pending.shift()
  void flushConnectionDiagnostics()
}

export function recordStatusRestored() {
  if (IS_REMOTE) return
  if (failed) {
    failed = false
    pending.push({ event: 'status_restored', time: new Date().toISOString(), message: '' })
    if (pending.length > 25) pending.shift()
  }
  void flushConnectionDiagnostics()
}

export function flushConnectionDiagnostics(): Promise<void> {
  if (IS_REMOTE || !pending.length) return Promise.resolve()
  if (flushing) return flushing
  const batch = pending.slice()
  flushing = (async () => {
    try {
      const response = await fetch(`${API_BASE}/api/runtime/diagnostics/events`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ events: batch }), signal: AbortSignal.timeout(3000),
      })
      if (response.ok) {
        for (const entry of batch) {
          const index = pending.indexOf(entry)
          if (index >= 0) pending.splice(index, 1)
        }
      }
    } catch { /* Retain bounded evidence until recovery or explicit export. */ }
    finally { flushing = null }
  })()
  return flushing
}
