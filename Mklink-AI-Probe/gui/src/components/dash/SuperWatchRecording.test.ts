import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import SuperWatchRecording from './SuperWatchRecording.vue'

const environment = vi.hoisted(() => ({ native: true, remote: false, pickDirectory: vi.fn() }))
vi.mock('@tauri-apps/api/core', () => ({ isTauri: () => environment.native }))
vi.mock('../../lib/runtimeEndpoint', () => ({ API_BASE: '', get IS_REMOTE() { return environment.remote } }))
vi.mock('../../lib/filePicker', () => ({ pickDirectory: environment.pickDirectory }))
beforeEach(() => {
  environment.native = true; environment.remote = false; environment.pickDirectory.mockReset()
  vi.stubGlobal('localStorage', { getItem: () => 'F:/logs', setItem: vi.fn() })
  HTMLDialogElement.prototype.showModal = vi.fn()
  HTMLDialogElement.prototype.close = vi.fn()
})
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); document.body.innerHTML = '' })
it('uses one toggle, never starts recording on mount, and stops an existing recording', async () => {
  vi.stubGlobal('localStorage', { getItem: () => null, setItem: vi.fn() })
  const request = vi.fn(async (url: string) => ({ ok: true, json: async () => ({
    active: !url.endsWith('/stop'), state: url.endsWith('/stop') ? 'completed' : 'recording', samples: 3,
  }) }))
  vi.stubGlobal('fetch', request)
  const wrapper = mount(SuperWatchRecording)
  try {
    await flushPromises()
    expect(request.mock.calls.map(call => call[0])).toEqual([expect.stringContaining('/recording/status')])
    expect(wrapper.findAll('[data-testid=sw-record-toggle]')).toHaveLength(1)
    expect(wrapper.get('[data-testid=sw-record-toggle]').text()).toMatch(/停止记录|Stop recording/)
    await wrapper.get('[data-testid=sw-record-toggle]').trigger('click'); await flushPromises()
    expect(request.mock.calls.at(-1)![0]).toContain('/recording/stop')
    expect(wrapper.get('[data-testid=sw-record-toggle]').text()).toMatch(/开始记录|Start recording/)
  } finally { wrapper.unmount() }
})

it('opens the native folder picker and enables recording before any acquisition', async () => {
  environment.pickDirectory.mockResolvedValue('F:/日志')
  const request = vi.fn(async (url: string) => ({ ok: true, json: async () => url.endsWith('/start')
    ? { active: true, state: 'recording', samples: 0, path: 'F:/日志/log.jsonl' }
    : { active: false, state: 'idle' } }))
  vi.stubGlobal('fetch', request)
  const wrapper = mount(SuperWatchRecording)
  try {
    await flushPromises()
    await wrapper.get('[data-testid=sw-record-toggle]').trigger('click'); await flushPromises()
    expect(environment.pickDirectory).toHaveBeenCalledWith(expect.any(String), 'F:/logs')
    expect(HTMLDialogElement.prototype.showModal).not.toHaveBeenCalled()
    expect(request).toHaveBeenLastCalledWith(expect.stringContaining('/recording/start'), expect.objectContaining({ body: JSON.stringify({ directory: 'F:/日志' }) }))
    expect(wrapper.text()).toMatch(/等待数据|Waiting for data/)
    expect(localStorage.setItem).toHaveBeenCalledWith('mklink.superwatch.recordDirectory', 'F:/日志')
  } finally { wrapper.unmount() }
})

it('cancels without starting or browsing and allows retry after a native picker error', async () => {
  environment.pickDirectory.mockResolvedValueOnce(null).mockRejectedValueOnce(new Error('picker failed')).mockResolvedValue(null)
  const request = vi.fn(async () => ({ ok: true, json: async () => ({ active: false, state: 'idle' }) }))
  vi.stubGlobal('fetch', request)
  const wrapper = mount(SuperWatchRecording)
  try {
    await flushPromises()
    const toggle = wrapper.get('[data-testid=sw-record-toggle]')
    await toggle.trigger('click'); await flushPromises()
    expect(request).toHaveBeenCalledTimes(1)
    await toggle.trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('picker failed')
    expect(toggle.attributes('disabled')).toBeUndefined()
    await toggle.trigger('click'); await flushPromises()
    expect(wrapper.text()).not.toContain('picker failed')
    expect(request).toHaveBeenCalledTimes(1)
  } finally { wrapper.unmount() }
})

it('shows a structured admission error and allows recording to be retried', async () => {
  environment.pickDirectory.mockResolvedValue('F:/logs')
  vi.stubGlobal('fetch', vi.fn(async (url: string) => ({
    ok: !url.endsWith('/start'), status: 409,
    json: async () => url.endsWith('/start')
      ? { detail: { code: 'probe_not_selected', message: 'Select a probe before recording' } }
      : { active: false, state: 'idle' },
  })))
  const wrapper = mount(SuperWatchRecording)
  try {
    await flushPromises()
    await wrapper.get('[data-testid=sw-record-toggle]').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('Select a probe before recording')
    expect(wrapper.text()).not.toContain('[object Object]')
    expect(wrapper.get('[data-testid=sw-record-toggle]').attributes('disabled')).toBeUndefined()
    expect(localStorage.setItem).not.toHaveBeenCalled()
  } finally { wrapper.unmount() }
})

it.each([{ native: false, remote: false }, { native: true, remote: true }])('keeps backend directory browsing for $native/$remote windows', async options => {
  Object.assign(environment, options)
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ active: false, state: 'idle', current: 'F:/logs', parent: 'F:/', dirs: [], drives: [] }) })))
  const wrapper = mount(SuperWatchRecording)
  try {
    await flushPromises()
    await wrapper.get('[data-testid=sw-record-toggle]').trigger('click'); await flushPromises()
    expect(environment.pickDirectory).not.toHaveBeenCalled()
    expect(HTMLDialogElement.prototype.showModal).toHaveBeenCalledOnce()
    expect(fetch).toHaveBeenLastCalledWith(expect.stringContaining('/api/project-root/browse?path='), undefined)
  } finally { wrapper.unmount() }
})
