import { afterEach, expect, it, vi } from 'vitest'

vi.mock('./runtimeEndpoint', () => ({ API_BASE: '', IS_REMOTE: false }))
afterEach(() => { vi.unstubAllGlobals(); vi.resetModules() })

it('retains the first failure through backend loss and exports both transitions', async () => {
  const fetch = vi.fn().mockRejectedValue(new Error('offline'))
  vi.stubGlobal('fetch', fetch)
  const diagnostics = await import('./connectionDiagnostics')
  diagnostics.recordStatusFailure(new Error('HTTP 503'))
  await diagnostics.flushConnectionDiagnostics()
  diagnostics.recordStatusFailure(new Error('secondary failure'))
  fetch.mockResolvedValue({ ok: true })
  diagnostics.recordStatusRestored()
  await diagnostics.flushConnectionDiagnostics()
  const body = JSON.parse(fetch.mock.lastCall![1].body)
  expect(body.events.map((entry: { event: string }) => entry.event)).toEqual(['status_failed', 'status_restored'])
  expect(body.events[0].message).toBe('Error: HTTP 503')
  const count = fetch.mock.calls.length
  await diagnostics.flushConnectionDiagnostics()
  expect(fetch).toHaveBeenCalledTimes(count)
})
