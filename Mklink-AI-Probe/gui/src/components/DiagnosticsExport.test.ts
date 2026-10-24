import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import DiagnosticsExport from './DiagnosticsExport.vue'

const mocks = vi.hoisted(() => ({ save: vi.fn(), success: vi.fn(), error: vi.fn(), flush: vi.fn() }))
vi.mock('../lib/runtimeEndpoint', () => ({ API_BASE: '', IS_REMOTE: false }))
vi.mock('../lib/downloadTextFile', () => ({ saveBlobFile: mocks.save }))
vi.mock('../lib/connectionDiagnostics', () => ({ flushConnectionDiagnostics: mocks.flush }))
vi.mock('../composables/useToast', () => ({ useToast: () => mocks }))
beforeEach(() => { vi.clearAllMocks(); mocks.save.mockResolvedValue(true) })
afterEach(() => vi.unstubAllGlobals())

it('exports without an active device and restores the button after saving', async () => {
  const blob = new Blob(['fixture'])
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, headers: new Headers({ 'content-type': 'application/zip' }), blob: async () => blob }))
  const wrapper = mount(DiagnosticsExport)
  await wrapper.get('button').trigger('click')
  await flushPromises()
  expect(mocks.flush).toHaveBeenCalledOnce()
  expect(mocks.save).toHaveBeenCalledWith(expect.stringMatching(/^mklink-diagnostics-.*\.zip$/), blob)
  expect(mocks.success).toHaveBeenCalledOnce()
  expect(wrapper.get('button').attributes('disabled')).toBeUndefined()
  wrapper.unmount()
})

it('reports export errors and never saves an HTML error response', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }))
  const wrapper = mount(DiagnosticsExport)
  await wrapper.get('button').trigger('click')
  await flushPromises()
  expect(mocks.save).not.toHaveBeenCalled()
  expect(mocks.error).toHaveBeenCalledWith(expect.stringContaining('503'))
  expect(wrapper.get('button').attributes('disabled')).toBeUndefined()
  wrapper.unmount()
})

it('does not report a successful export when the save dialog is cancelled', async () => {
  mocks.save.mockResolvedValue(false)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, headers: new Headers({ 'content-type': 'application/zip' }), blob: async () => new Blob() }))
  const wrapper = mount(DiagnosticsExport)
  await wrapper.get('button').trigger('click')
  await flushPromises()
  expect(mocks.success).not.toHaveBeenCalled()
  expect(mocks.error).not.toHaveBeenCalled()
  wrapper.unmount()
})
