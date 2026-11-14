import { describe, expect, it, vi } from 'vitest'
import { recoverPendingIntent } from './useFrontendWorkbench'

const pending = { request_id: 'original_request', session_id: 'original_target', page_id: 'original_page',
  revision: 3, object_id: 'panel', intent: 'inspect', message: 'Inspect the captured state' }

describe('pending frontend intent recovery', () => {
  it('reads a persisted original request after the target changes without resubmitting', async () => {
    const saved = { request_id: pending.request_id, request: pending, status: 'pending', revision: 0 }
    const request = vi.fn().mockResolvedValue(saved)
    expect(await recoverPendingIntent(pending, request)).toBe(saved)
    expect(request.mock.calls).toEqual([['intent?request_id=original_request']])
  })
  it('permits explicit abandonment when the original request is absent and its target ended', async () => {
    const request = vi.fn().mockRejectedValueOnce(Object.assign(new Error('Missing'), { status: 404 }))
      .mockResolvedValueOnce({ session_id: 'new_target', pages: [] })
    await expect(recoverPendingIntent(pending, request)).rejects.toMatchObject({ pending, canDiscard: true })
    expect(request.mock.calls).toEqual([['intent?request_id=original_request'], ['pages']])
  })
  it('only retries the exact original request when its original page is still live', async () => {
    const request = vi.fn().mockRejectedValueOnce(Object.assign(new Error('Missing'), { status: 404 }))
      .mockResolvedValueOnce({ session_id: pending.session_id, pages: [{ page_id: pending.page_id, online: true }] })
      .mockResolvedValueOnce({ request_id: pending.request_id, status: 'pending' })
    await recoverPendingIntent(pending, request)
    expect(request).toHaveBeenLastCalledWith('intent', pending)
    expect(request.mock.calls[2]![1]).toBe(pending)
  })
  it('keeps unknown reads unresolved without creating or retrying a request', async () => {
    const request = vi.fn().mockRejectedValue(new TypeError('Connection lost'))
    await expect(recoverPendingIntent(pending, request)).rejects.toThrow('Connection lost')
    expect(request).toHaveBeenCalledTimes(1)
  })
})
