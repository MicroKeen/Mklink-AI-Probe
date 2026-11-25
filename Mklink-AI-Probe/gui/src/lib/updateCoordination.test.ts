import { afterEach, describe, expect, it, vi } from 'vitest'
import { invoke } from '@tauri-apps/api/core'
import { reserveHostUpdate } from './updateCoordination'

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }))
afterEach(() => { vi.resetAllMocks(); vi.unstubAllGlobals() })

describe('desktop update reservation', () => {
  it('works with an unreachable backend and releases the native reservation', async () => {
    const fetch = vi.fn().mockRejectedValue(new Error('offline'))
    vi.stubGlobal('fetch', fetch)
    vi.mocked(invoke).mockResolvedValueOnce(true)
    const release = await reserveHostUpdate()
    await release!()
    expect(vi.mocked(invoke).mock.calls).toEqual([['begin_desktop_install'], ['end_desktop_install']])
    expect(fetch).not.toHaveBeenCalled()
  })
  it('distinguishes a real update conflict from an operating system error', async () => {
    vi.mocked(invoke).mockResolvedValueOnce(false).mockRejectedValueOnce(new Error('access denied'))
    expect(await reserveHostUpdate()).toBeUndefined()
    await expect(reserveHostUpdate()).rejects.toThrow('access denied')
  })
})
