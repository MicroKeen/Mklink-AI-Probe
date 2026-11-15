import { describe, expect, it, vi } from 'vitest'
import { interaction, objectSchema, withFrontendTarget } from './frontendControl'

function fixture(execute = vi.fn((): unknown => ({ saved: true }))) {
  let value = 0
  const runtime = interaction.create({ session_id: 'session', page_id: 'page', adapter: {
    title: 'Test', catalog: () => ({ panels: [{ id: 'panel' }] }),
    actions: { set: { inputSchema: objectSchema({ value: { type: 'integer', minimum: 0, maximum: 10 } }) } },
    read: () => ({ value }), execute,
  } })
  const command = () => ({ protocol: 'agent-frontend/1', session_id: 'session', page_id: 'page', command_id: 'command', expect_revision: runtime.report().state.revision, deadline: Date.now() + 5000, action: 'set', args: { value: 3 } })
  return { runtime, command, execute, change: () => { value++ } }
}
describe('frontend semantic receipts', () => {
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
      await withFrontendTarget('session', target, () => window.fetch('/api/device/debug-speed', { method: 'POST', body: '{}' }))
      const options = (transport.mock.calls as unknown as [unknown, RequestInit][])[0]![1]
      expect(new Headers(options.headers).get('X-MKLink-Frontend-Session')).toBe('session')
      expect(new Headers(options.headers).get('X-MKLink-Device-Generation')).toBe('4')
      await withFrontendTarget('session', target, async () => {
        expect(await withFrontendTarget('session', target, async () => 'nested', true)).toBe('nested')
        await expect(withFrontendTarget('session', target, async () => 'unrelated')).rejects.toThrow('still running')
        await expect(withFrontendTarget('session', { ...target, device_generation: 5 }, async () => 'wrong target', true)).rejects.toThrow('no longer active')
      })
      transport.mockRejectedValueOnce(new TypeError('Connection lost'))
      await expect(withFrontendTarget('session', target, () => window.fetch('/api/symbols/write', { method: 'POST' }))).rejects.toMatchObject({ unknown: true })
      transport.mockResolvedValueOnce(new Response('{', { headers: { 'Content-Type': 'application/json' } }))
      await expect(withFrontendTarget('session', target, async () => { await window.fetch('/api/symbols/write', { method: 'POST' }); return { ok: true } })).rejects.toMatchObject({ unknown: true })
      const retry = vi.fn()
      transport.mockRejectedValueOnce(new TypeError('Response lost'))
      await expect(withFrontendTarget('session', target, async () => {
        await expect(withFrontendTarget('session', target, () => window.fetch('/api/symbols/write', { method: 'POST' }), true)).rejects.toMatchObject({ unknown: true })
        await expect(withFrontendTarget('session', target, retry, true)).rejects.toMatchObject({ unknown: true })
      })).rejects.toMatchObject({ unknown: true })
      expect(retry).not.toHaveBeenCalled()
    } finally { window.fetch = original }
  })
})
