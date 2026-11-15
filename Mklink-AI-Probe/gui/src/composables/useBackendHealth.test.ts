import { afterEach, describe, expect, it, vi } from 'vitest'

describe('useBackendHealth startup lifecycle', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  it('marks the backend dead after the initial fast-poll window expires', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 503 })))
    const { useBackendHealth } = await import('./useBackendHealth')
    const health = useBackendHealth()

    health.startHealthPolling(5000)
    await vi.advanceTimersByTimeAsync(15_000)

    expect(health.backendState.value).toBe('dead')
    health.stopHealthPolling()
  })

  it('uses the backend-reported listener port for a proxied health response', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Response.json({ status: 'ok', backend_port: 8766 })))
    const { useBackendHealth } = await import('./useBackendHealth')
    const health = useBackendHealth()

    await health.refreshHealth()

    expect(health.backendState.value).toBe('alive')
    expect(health.backendPort.value).toBe(8766)
  })

  it('distinguishes expired authorization from lost connectivity and recovers after authentication', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(Response.json({ shared_runtime: true }))
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(new Response('', { status: 401 }))
      .mockResolvedValueOnce(Response.json({ shared_runtime: true }))
    vi.stubGlobal('fetch', fetchMock)
    const health = (await import('./useBackendHealth')).useBackendHealth()
    await health.refreshHealth()
    expect(health.backendState.value).toBe('alive')
    await health.refreshHealth()
    expect(health.backendState.value).toBe('dead')
    expect(health.authenticationRequired.value).toBe(false)
    expect(health.sharedRuntime.value).toBe(true)
    await health.refreshHealth()
    expect(health.backendState.value).toBe('dead')
    expect(health.authenticationRequired.value).toBe(true)
    await health.refreshHealth()
    expect(health.backendState.value).toBe('alive')
    expect(health.authenticationRequired.value).toBe(false)
  })

  it('shows authorization failure immediately on initial load', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 401 })))
    const health = (await import('./useBackendHealth')).useBackendHealth()
    await health.refreshHealth()
    expect(health.backendState.value).toBe('dead')
    expect(health.authenticationRequired.value).toBe(true)
  })

  it('shares slow startup polls and manual checks without overlapping requests', async () => {
    vi.useFakeTimers()
    let resolve!: (response: Response) => void
    const fetchMock = vi.fn(() => new Promise<Response>(done => { resolve = done }))
    vi.stubGlobal('fetch', fetchMock)
    const health = (await import('./useBackendHealth')).useBackendHealth()
    health.startHealthPolling()
    await vi.advanceTimersByTimeAsync(2000)
    const manual = health.refreshHealth()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    resolve(Response.json({ status: 'ok', shared_runtime: true }))
    await manual
    expect(health.backendState.value).toBe('alive')
    health.stopHealthPolling()
  })

  it('ignores a late failure after polling has been replaced', async () => {
    let fail!: (error: Error) => void
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => new Promise((_resolve, reject) => { fail = reject }))
      .mockResolvedValueOnce(Response.json({ status: 'ok', shared_runtime: true }))
    vi.stubGlobal('fetch', fetchMock)
    const health = (await import('./useBackendHealth')).useBackendHealth()
    const old = health.refreshHealth()
    health.stopHealthPolling()
    await health.refreshHealth()
    fail(new Error('late timeout'))
    await old
    expect(health.backendState.value).toBe('alive')
    expect(health.sharedRuntime.value).toBe(true)
  })

  it('does not accept an old response after the desktop endpoint changes', async () => {
    let resolve!: (response: Response) => void
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(done => { resolve = done })))
    const health = (await import('./useBackendHealth')).useBackendHealth()
    const old = health.refreshHealth()
    const runtime = await import('../lib/runtimeEndpoint')
    runtime.applyBackendEndpoint({ port: 8976, instanceId: 'new' })
    resolve(Response.json({ status: 'ok', backend_port: 8876, shared_runtime: true }))
    await old
    expect(health.backendState.value).toBe('starting')
    expect(health.backendPort.value).toBe(8976)
    expect(health.sharedRuntime.value).toBe(false)
  })
})
