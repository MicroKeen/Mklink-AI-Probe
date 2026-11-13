import { afterEach, describe, expect, it, vi } from 'vitest'
import { reserveHostUpdate } from './updateCoordination'

vi.mock('./runtimeEndpoint', () => ({ API_BASE: 'http://fixture' }))
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

describe('desktop update reservation', () => {
  it('reserves, renews and releases without sending hardware commands', async () => {
    vi.useFakeTimers()
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ token: 'lease' }) })
    vi.stubGlobal('fetch', fetch)
    const release = await reserveHostUpdate()
    expect(fetch.mock.calls[0][0]).toBe('http://fixture/api/runtime/host-update/prepare')
    await vi.advanceTimersByTimeAsync(30000)
    expect(fetch.mock.calls[1][0]).toContain('/renew')
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toBe('lease')
    await release()
    expect(fetch.mock.calls[2][0]).toContain('/release')
    await vi.advanceTimersByTimeAsync(60000)
    expect(fetch).toHaveBeenCalledTimes(3)
  })
  it('rejects missing/old backend support and malformed reservations', async () => {
    const fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 404 })
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) })
    vi.stubGlobal('fetch', fetch)
    await expect(reserveHostUpdate()).rejects.toThrow('暂不能安装更新')
    await expect(reserveHostUpdate()).rejects.toThrow('未能确认')
  })
})
