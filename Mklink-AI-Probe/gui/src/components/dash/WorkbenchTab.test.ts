import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { inject } from 'vue'
import { controlStateKey, type ControlState } from '../../lib/workbenchControls'
import WorkbenchTab from './WorkbenchTab.vue'

vi.mock('./WorkbenchPanel.vue', () => ({ default: {
  props: ['panel'], template: '<div class="panel-fixture"/>',
  setup: (props: any, { expose }: any) => { expose({ catalog: () => [], read: () => ({ view: props.panel.view || { paused: false } }), execute: vi.fn(), transient: inject(controlStateKey) }) },
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

it('uses the same dock state for semantic commands and tab controls and persists v2', async () => {
  const wrapper = mount(WorkbenchTab, { props: { deviceConnected: false, symbolLoaded: false } })
  await flushPromises()
  const a = await wrapper.vm.execute('panel.add', { type: 'watch', title: 'Wave' }) as any
  const b = await wrapper.vm.execute('panel.add', { type: 'controls', title: 'Control' }) as any
  await wrapper.vm.execute('panel.dock', { panel_id: a.id, target_panel_id: b.id })
  await flushPromises()
  const card = wrapper.get(`[data-panel-id="${a.id}"]`)
  expect(card.isVisible()).toBe(true)
  await card.get('.dock-tabs button').trigger('click')
  expect(wrapper.vm.read().layout.docks?.[0]?.active).toBe(b.id)
  await wrapper.vm.execute('panel.focus', { panel_id: a.id })
  await wrapper.vm.execute('layout.save', {})
  expect(saved.version).toBe(2)
  expect(saved.docks[0].active).toBe(a.id)
  await wrapper.vm.execute('panel.remove', { panel_id: b.id })
  expect(wrapper.vm.entries().map(panel => panel.id)).toEqual([a.id])
  await wrapper.vm.execute('layout.restore', {})
  expect(wrapper.vm.read().layout.docks?.[0]?.active).toBe(a.id)
  wrapper.unmount()
})

it('transfers a control without running its binding and keeps state after invalid geometry', async () => {
  const wrapper = mount(WorkbenchTab, { props: { deviceConnected: false, symbolLoaded: false } })
  await flushPromises()
  const a = await wrapper.vm.execute('panel.add', { type: 'controls', title: 'A' }) as any
  const b = await wrapper.vm.execute('panel.add', { type: 'controls', title: 'B' }) as any
  saved = { ...wrapper.vm.read().layout, panels: wrapper.vm.read().layout.panels.map(panel => panel.id === a.id ? { ...panel, widgets: [{ id: 'control_one', type: 'button', version: 1, title: 'Run', x: 0, y: 0, w: 4, h: 1, binding: {} }] } : panel) }
  await wrapper.vm.execute('layout.restore', {})
  await wrapper.vm.execute('component.transfer', { component_id: 'control_one', target_panel_id: b.id })
  expect(wrapper.vm.read().layout.panels.find(panel => panel.id === a.id)?.widgets).toEqual([])
  expect(wrapper.vm.read().layout.panels.find(panel => panel.id === b.id)?.widgets?.[0]?.id).toBe('control_one')
  const before = JSON.stringify(wrapper.vm.read().layout)
  await expect(wrapper.vm.execute('panel.move', { panel_id: a.id, x: 0, y: 0, w: 1, h: 1 })).rejects.toThrow()
  expect(JSON.stringify(wrapper.vm.read().layout)).toBe(before)
  expect(writes).toEqual([])
  wrapper.unmount()
})

function savedControls() {
  return { version: 2, revision: 1, docks: [], panels: [{ id: 'controls', type: 'controls', title: 'Controls', source: {}, x: 0, y: 0, w: 6, h: 6, widgets: ['first', 'second'].map((id, index) => ({
    id, type: 'form', version: 1, title: id, x: 0, y: index * 3, w: 6, h: 3,
    binding: { panel_id: 'wave', action: 'sample.interval', args: {}, contract: '{}' },
  })) }] }
}

it('clears draft and completed result when restoring a different binding with the same component ID', async () => {
  saved = savedControls()
  const wrapper = mount(WorkbenchTab, { props: { deviceConnected: false, symbolLoaded: false } })
  await flushPromises()
  const transient = (wrapper.vm.entries()[0]!.surface as any).transient as ControlState
  transient.drafts.first = { interval: '0.25' }; transient.results.first = { done: true }; transient.operations.first = 'old-operation'; transient.statuses.first = { status: 'completed' }
  transient.drafts.second = { interval: '0.5' }
  saved.panels[0].widgets[0].binding.panel_id = 'other_wave'
  await wrapper.vm.execute('layout.restore', {})
  expect(transient.drafts.first).toBeUndefined()
  expect(transient.results.first).toBeUndefined()
  expect(transient.operations.first).toBeUndefined()
  expect(transient.drafts.second).toEqual({ interval: '0.5' })
  expect(wrapper.vm.read().layout.panels[0]?.widgets?.[0]?.binding.panel_id).toBe('other_wave')
  expect(writes).toEqual([])
  wrapper.unmount()
})

it.each(['running', 'unknown'])('refuses an entire restore that would discard a %s binding', async status => {
  saved = savedControls()
  const wrapper = mount(WorkbenchTab, { props: { deviceConnected: false, symbolLoaded: false } })
  await flushPromises()
  const transient = (wrapper.vm.entries()[0]!.surface as any).transient as ControlState
  transient.drafts.first = { interval: '0.25' }; transient.operations.second = 'original-operation'; transient.statuses.second = { status }
  const before = JSON.stringify(wrapper.vm.read().layout)
  saved.panels[0].widgets[0].binding.panel_id = 'other_wave'
  saved.panels[0].widgets.pop()
  await expect(wrapper.vm.execute('layout.restore', {})).rejects.toThrow('original receipt')
  expect(JSON.stringify(wrapper.vm.read().layout)).toBe(before)
  expect(transient.drafts.first).toEqual({ interval: '0.25' })
  expect(transient.operations.second).toBe('original-operation')
  saved = JSON.parse(before)
  await wrapper.vm.execute('layout.restore', {})
  expect(transient.statuses.second).toEqual({ status })
  expect(transient.operations.second).toBe('original-operation')
  wrapper.unmount()
})
