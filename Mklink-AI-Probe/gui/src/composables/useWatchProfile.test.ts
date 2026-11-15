import { beforeEach, expect, it, vi } from 'vitest'
import { flushWatchProfile, useWatchProfile } from './useWatchProfile'

const current = useWatchProfile()
function payload(path: string, bufferPoints = 50000) {
  return { path, available: true, error: '', missing: [],
    viewer: { revision: path + '-viewer', viewer: { bufferPoints, interval: .001, channels: [] } },
    layout: { revision: path + '-layout', layout: { panelWidth: 340, source: 'variables', hidden: [] } } }
}
beforeEach(() => {
  ;(window as any).__waveformViewers = { SuperWatch: { setProfilePreferences: vi.fn(), flushPreferences: vi.fn() } }
})

it('loads the selected ELF preferences and restores the viewer without starting acquisition', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => payload('one.elf', 500000) })))
  await current.load()
  expect((window as any).__waveformViewers.SuperWatch.setProfilePreferences).toHaveBeenCalledWith(
    { bufferPoints: 500000, interval: .001, channels: [] }, 'one.elf')
  expect(vi.mocked(fetch).mock.calls).toEqual([['/api/dash/superwatch/profile']])
})

it('serializes writes with returned revisions and flushes before symbol replacement', async () => {
  const bodies: any[] = []
  vi.stubGlobal('fetch', vi.fn(async (_url, options) => {
    if (!options) return { ok: true, json: async () => payload('two.axf') }
    const body = JSON.parse(options.body as string); bodies.push(body)
    return { ok: true, json: async () => ({ viewer: body.value, revision: 'saved-' + bodies.length }) }
  }))
  await current.load()
  const first = current.save('viewer', { bufferPoints: 100000, interval: .001, channels: [] })
  const second = current.save('viewer', { bufferPoints: 200000, interval: .001, channels: [] })
  await flushWatchProfile()
  await Promise.all([first, second])
  expect(bodies.map(b => b.revision)).toEqual(['two.axf-viewer', 'saved-1'])
  expect(current.profile.value?.viewer.viewer.bufferPoints).toBe(200000)
  expect(current.saving.value).toBe(false)
})

it('reports a stale-source conflict without retrying or overwriting another ELF', async () => {
  vi.stubGlobal('fetch', vi.fn(async (_url, options) => options
    ? { ok: false, json: async () => ({ detail: 'AXF changed' }) }
    : { ok: true, json: async () => payload('three.axf') }))
  await current.load()
  await current.save('viewer', { bufferPoints: 100000 })
  expect(current.error.value).toContain('AXF changed')
  expect(current.profile.value?.viewer.viewer.bufferPoints).toBe(50000)
  expect(vi.mocked(fetch)).toHaveBeenCalledTimes(2)
})

it('coalesces rapid layout edits and flushes the final size before leaving', async () => {
  const bodies: any[] = []
  vi.stubGlobal('fetch', vi.fn(async (_url, options) => {
    if (!options) return { ok: true, json: async () => payload('layout.axf') }
    const body = JSON.parse(options.body as string); bodies.push(body)
    return { ok: true, json: async () => ({ layout: body.value, revision: 'saved-layout' }) }
  }))
  await current.load()
  for (let width = 350; width <= 450; width++)
    current.scheduleLayout({panelWidth: width, source: 'variables', hidden: []})
  expect(bodies).toHaveLength(0)
  await flushWatchProfile()
  expect(bodies).toHaveLength(1)
  expect(bodies[0].value.panelWidth).toBe(450)
})
