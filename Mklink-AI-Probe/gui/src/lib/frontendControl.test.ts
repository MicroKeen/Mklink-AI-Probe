import { flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { frontendFetch, frontendRequest, interaction, objectSchema, withFrontendTarget, type FrontendFeedback } from './frontendControl'

function fixture(execute = vi.fn((): unknown => ({ saved: true })), onReceipt?: (event: FrontendFeedback) => void) {
  let value = 0
  const runtime = interaction.create({ session_id: 'session', page_id: 'page', onReceipt, adapter: {
    title: 'Test', catalog: () => ({ panels: [{ id: 'panel' }] }),
    actions: { set: { inputSchema: objectSchema({ value: { type: 'integer', minimum: 0, maximum: 10 } }) } },
    read: () => ({ value }), execute,
  } })
  const command = () => ({ protocol: 'agent-frontend/1', session_id: 'session', page_id: 'page', command_id: 'command', expect_revision: runtime.report().state.revision, deadline: Date.now() + 5000, action: 'set', args: { value: 3 } })
  return { runtime, command, execute, change: () => { value++ } }
}
describe('frontend semantic receipts', () => {
  it('waits for a dispatched GUI request and never gives a queued background request its owner', async () => {
    const original = window.fetch
    let rejectWrite!: (cause: Error) => void
    window.fetch = vi.fn((url: RequestInfo | URL) => String(url).endsWith('/write')
      ? new Promise<Response>((_, reject) => { rejectWrite = reject })
      : Promise.resolve(new Response('{}', { status: 500 })))
    const target = { instance_id: 'instance', probe_id: 'probe', device_generation: 4, project_root: 'project' }
    try {
      const pending = withFrontendTarget('session', target, () => {
        void frontendFetch('/api/dash/superwatch/write', { method: 'POST' }).catch(() => {})
        return { status: 'dispatched' }
      })
      await Promise.resolve()
      await frontendFetch('/api/dash/superwatch/workspace', { method: 'PUT' })
      const options = (window.fetch as ReturnType<typeof vi.fn>).mock.calls[1]![1]
      expect(new Headers(options.headers).has('X-MKLink-Frontend-Session')).toBe(false)
      rejectWrite(new Error('Own response lost'))
      await expect(pending).rejects.toMatchObject({ unknown: true })
    } finally { window.fetch = original }
  })
  it.each(['http', 'network', 'query'] as const)('does not attribute an independent %s failure to the successful write', async failure => {
    const original = window.fetch
    const transport = vi.fn(async (url: RequestInfo | URL) => {
      if (String(url).endsWith('/workspace')) {
        if (failure === 'network') throw new TypeError('Unrelated connection lost')
        return new Response('{}', { status: 500, headers: { 'Content-Type': 'application/json' } })
      }
      return new Response('{"ok":true}', { headers: { 'Content-Type': 'application/json' } })
    })
    window.fetch = transport
    const target = { instance_id: 'instance', probe_id: 'probe', device_generation: 4, project_root: 'project' }
    try {
      const result = await withFrontendTarget('session', target, async context => {
        const result = await (context?.fetch || window.fetch)('/api/dash/superwatch/write', { method: 'POST' })
        await window.fetch('/api/dash/superwatch/workspace', { method: failure === 'query' ? 'GET' : 'PUT' }).catch(() => {})
        return result.json()
      })
      expect(result).toEqual({ ok: true })
      expect(window.fetch).toBe(transport)
      const options = (transport.mock.calls as unknown as [unknown, RequestInit][])[1]![1]
      expect(new Headers(options.headers).has('X-MKLink-Frontend-Session')).toBe(false)
      await expect(withFrontendTarget('session', target, context => context.fetch('/api/dash/superwatch/write', { method: 'POST' }))).resolves.toBeInstanceOf(Response)
    } finally { window.fetch = original }
  })
  it.each([['layout', 'PUT'], ['layouts', 'POST']])('preserves uncertainty when saving %s loses its response', async (path, method) => {
    const original = window.fetch
    const target = { instance_id: 'instance', probe_id: 'probe', device_generation: 4, project_root: 'project' }
    try {
      const transport = vi.fn<typeof fetch>().mockRejectedValue(new TypeError('Lost response'))
      window.fetch = transport
      const send = () => withFrontendTarget('session', target, context => frontendRequest(path, {}, method, context))
      await expect(send()).rejects.toMatchObject({ unknown: true })
      expect(transport).toHaveBeenCalledTimes(1)
      await expect(withFrontendTarget('session', target, context => frontendRequest(path, undefined, 'GET', context))).rejects.toBeInstanceOf(TypeError)
      transport.mockResolvedValueOnce(new Response('{"detail":"Layout changed"}', { status: 409, headers: { 'Content-Type': 'application/json' } }))
      await expect(send()).rejects.toMatchObject({ status: 409 })
    } finally { window.fetch = original }
  })
  it('rejects stale and invalid arguments before dispatch and retains action results', () => {
    const valid = fixture()
    expect(valid.runtime.execute(valid.command())).toMatchObject({ status: 'applied', result: { saved: true } })
    const stale = fixture(), command = stale.command()
    stale.change()
    expect(stale.runtime.execute(command)).toMatchObject({ status: 'rejected', code: 'STALE_REVISION' })
    expect(stale.execute).not.toHaveBeenCalled()
    const invalid = fixture()
    expect(invalid.runtime.execute({ ...invalid.command(), args: { value: 3, injected: 'x' } }).status).toBe('rejected')
    expect(invalid.execute).not.toHaveBeenCalled()
  })
  it('does not repeat an asynchronous action and preserves unknown after disposal', async () => {
    let finish!: (value: unknown) => void
    const test = fixture(vi.fn(() => new Promise(resolve => { finish = resolve })))
    const command = test.command()
    expect(test.runtime.execute(command).status).toBe('accepted')
    expect(test.runtime.execute(command)).toMatchObject({ status: 'accepted', duplicate: true })
    expect(test.execute).toHaveBeenCalledTimes(1)
    test.runtime.dispose(); finish({ completed: true }); await Promise.resolve(); await Promise.resolve()
    expect(test.runtime.receipts()[0]?.status).toBe('unknown')
  })
  it('reports business failures with their actual message', async () => {
    const test = fixture(vi.fn(async () => { throw new Error('Device disconnected') }))
    test.runtime.execute(test.command())
    await Promise.resolve(); await Promise.resolve()
    expect(test.runtime.receipts()[0]).toMatchObject({ status: 'failed', message: 'Device disconnected' })
  })
  it('pins every business request to the original target and fences an unknown mutation', async () => {
    const original = window.fetch
    const transport = vi.fn(async (): Promise<Response> => new Response(JSON.stringify({ ok: true }), { headers: { 'Content-Type': 'application/json' } }))
    window.fetch = transport
    const target = { instance_id: 'instance', probe_id: 'probe', device_generation: 4, project_root: 'project' }
    try {
      await withFrontendTarget('session', target, context => context.fetch('/api/device/debug-speed', { method: 'POST', body: '{}' }))
      const options = (transport.mock.calls as unknown as [unknown, RequestInit][])[0]![1]
      expect(new Headers(options.headers).get('X-MKLink-Frontend-Session')).toBe('session')
      expect(new Headers(options.headers).get('X-MKLink-Device-Generation')).toBe('4')
      await withFrontendTarget('session', target, async context => {
        expect(await withFrontendTarget('session', target, async () => 'nested', context)).toBe('nested')
        await expect(withFrontendTarget('session', target, async () => 'unrelated')).rejects.toThrow('still running')
        await expect(withFrontendTarget('session', { ...target, device_generation: 5 }, async () => 'wrong target', context)).rejects.toThrow('no longer active')
      })
      transport.mockRejectedValueOnce(new TypeError('Connection lost'))
      await expect(withFrontendTarget('session', target, context => context.fetch('/api/symbols/write', { method: 'POST' }))).rejects.toMatchObject({ unknown: true })
      transport.mockResolvedValueOnce(new Response('{', { headers: { 'Content-Type': 'application/json' } }))
      await expect(withFrontendTarget('session', target, async context => { await context.fetch('/api/symbols/write', { method: 'POST' }); return { ok: true } })).rejects.toMatchObject({ unknown: true })
      const retry = vi.fn()
      transport.mockRejectedValueOnce(new TypeError('Response lost'))
      await expect(withFrontendTarget('session', target, async context => {
        await expect(withFrontendTarget('session', target, context => context.fetch('/api/symbols/write', { method: 'POST' }), context)).rejects.toMatchObject({ unknown: true })
        await expect(withFrontendTarget('session', target, retry, context)).rejects.toMatchObject({ unknown: true })
      })).rejects.toMatchObject({ unknown: true })
      expect(retry).not.toHaveBeenCalled()
    } finally { window.fetch = original }
  })
})

it('presents terminal outcomes once and isolates a failed presentation from the command', async () => {
  const notify = vi.fn(() => { throw new Error('Unavailable presentation') })
  const execution = vi.fn(async () => ({ saved: true }))
  const test = fixture(execution, notify)
  const command = test.command()
  expect(test.runtime.execute(command).status).toBe('accepted')
  expect(notify).not.toHaveBeenCalled()
  await flushPromises()
  expect(test.runtime.execute(command).status).toBe('completed')
  expect(notify.mock.calls).toHaveLength(1)
  expect(notify).toHaveBeenCalledWith(expect.objectContaining({ command_id: 'command', status: 'completed' }))
  const stale = { ...command, command_id: 'stale' }
  expect(test.runtime.execute(stale).status).toBe('rejected')
  expect(notify).toHaveBeenLastCalledWith(expect.objectContaining({ command_id: 'stale', status: 'rejected', code: 'STALE_REVISION' }))
  expect(execution).toHaveBeenCalledTimes(1)
})
