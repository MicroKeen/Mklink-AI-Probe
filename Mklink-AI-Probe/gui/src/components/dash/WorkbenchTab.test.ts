import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import WorkbenchTab from './WorkbenchTab.vue'

vi.mock('./WorkbenchPanel.vue', () => ({ default: {
  props: ['panel'], template: '<div class="panel-fixture"/>',
  setup: (props: any, { expose }: any) => { expose({ catalog: () => [], read: () => ({ view: props.panel.view || { paused: false } }), execute: vi.fn() }) },
} }))
let saved: any, failLoad = false
const writes: { url: string; body: any }[] = []
beforeEach(() => {
  saved = { version: 1, revision: 1, panels: [] }; failLoad = false; writes.length = 0
  vi.stubGlobal('fetch', vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith('/rtt/status')) return new Response(JSON.stringify({ running: false }))
    if (options?.method === 'PUT') {
      const body = JSON.parse(String(options.body)); writes.push({ url, body })
      if (body.revision !== saved.revision) return new Response(JSON.stringify({ detail: 'Layout changed in another window' }), { status: 409 })
      saved = { ...body, revision: body.revision + 1 }; return new Response(JSON.stringify(saved))
    }
    if (failLoad) return new Response(JSON.stringify({ detail: 'Unavailable' }), { status: 503 })
    return new Response(JSON.stringify(saved))
  }))
})
afterEach(() => vi.unstubAllGlobals())

it('creates first-use cards from shared groups using reads only and leaves saved empty layouts empty', async () => {
  saved.revision = 0
  const workspace = { version: 2, defaultGroup: 'motor', groups: [{ id: 'motor', name: 'Motor', collapsed: false, height: 200 }, { id: 'sensor', name: 'Sensor', collapsed: false, height: 200 }], panes: [{ id: 'motor' }, { id: 'sensor' }], signals: { rpm: { group: 'motor', pane: 'motor', alias: '', emphasis: false }, volts: { group: 'sensor', pane: 'sensor', alias: '', emphasis: false } } }
  const request = vi.fn(async (url: string, _options?: RequestInit) => new Response(JSON.stringify(
    url.endsWith('/workspace') ? { workspace, revision: 'original' } : url.endsWith('/items') ? { items: [{ name: 'rpm' }, { name: 'volts' }] } : url.endsWith('/rtt/status') ? { running: false } : saved,
  )))
  vi.stubGlobal('fetch', request)
  const wrapper = mount(WorkbenchTab, { props: { deviceConnected: false, symbolLoaded: false } })
  await flushPromises()
  expect(wrapper.vm.entries().map(panel => panel.id)).toEqual(['legacy_variables', 'legacy_watch_motor', 'legacy_watch_sensor'])
  expect(wrapper.text()).toContain('尚未保存')
  expect(saved.panels).toEqual([])
  expect(request.mock.calls.every(([, options]) => !options?.method || options.method === 'GET')).toBe(true)
  saved = { version: 1, revision: 1, panels: [] }
  await wrapper.vm.execute('layout.restore', {})
  expect(wrapper.vm.entries()).toEqual([])
  wrapper.unmount()
})

it('composes duplicate sources, saves views and restores them without hardware mutation', async () => {
  const wrapper = mount(WorkbenchTab, { props: { deviceConnected: false, symbolLoaded: false } })
  await flushPromises()
  const a = await wrapper.vm.execute('panel.add', { type: 'watch', title: 'First', signals: ['counter'] }) as any
  const b = await wrapper.vm.execute('panel.add', { type: 'watch', title: 'Second', signals: ['counter'] }) as any
  await flushPromises()
  expect(a.id).not.toBe(b.id)
  await wrapper.vm.execute('panel.move', { panel_id: b.id, x: 6, y: 0, w: 6, h: 4 })
  await wrapper.vm.execute('layout.save', {})
  expect(saved.panels[0].view).toEqual({ paused: false })
  await wrapper.vm.execute('panel.remove', { panel_id: a.id })
  await wrapper.vm.execute('layout.restore', {})
  expect(wrapper.vm.entries().map(panel => panel.id)).toEqual([a.id, b.id])
  expect(writes.map(entry => entry.url)).toEqual(['/api/runtime/frontend/layout'])
  wrapper.unmount()
})

it('keeps edits after a save conflict or failed restore', async () => {
  const wrapper = mount(WorkbenchTab, { props: { deviceConnected: false, symbolLoaded: false } })
  await flushPromises()
  await wrapper.vm.execute('panel.add', { type: 'serial', title: 'Draft', port: 'COM3' })
  saved.revision = 2
  await expect(wrapper.vm.execute('layout.save', {})).rejects.toThrow('Layout changed')
  failLoad = true
  await expect(wrapper.vm.execute('layout.restore', {})).rejects.toThrow('Unavailable')
  expect(wrapper.vm.entries()).toHaveLength(1)
  expect(wrapper.vm.entries()[0]?.title).toBe('Draft')
  wrapper.unmount()
})
