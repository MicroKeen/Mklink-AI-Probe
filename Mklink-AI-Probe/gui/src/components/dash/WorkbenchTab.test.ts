import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { inject, nextTick } from 'vue'
import { language, setLanguage } from '../../composables/useLanguage'
import type { GridStack } from 'gridstack'
import { controlStateKey, type ControlState } from '../../lib/workbenchControls'
import WorkbenchTab from './WorkbenchTab.vue'

vi.mock('./WorkbenchPanel.vue', () => ({ default: {
  props: ['panel'], template: '<div class="panel-fixture"/>',
  setup: (props: any, { expose }: any) => { expose({ catalog: () => [], read: () => ({ view: props.panel.view || { paused: false } }), execute: vi.fn(), transient: inject(controlStateKey) }) },
} }))
let saved: any, failLoad = false, library: Record<string, any>
const writes: { url: string; body: any }[] = []
beforeEach(() => {
  saved = { version: 1, revision: 1, panels: [] }; failLoad = false; writes.length = 0
  library = {}
  vi.stubGlobal('fetch', vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith('/rtt/status')) return new Response(JSON.stringify({ running: false }))
    if (url.includes('/layouts')) {
      if (failLoad) return new Response(JSON.stringify({ detail: 'Unavailable' }), { status: 503 })
      if (options?.method === 'POST') {
        const value = JSON.parse(String(options.body)); writes.push({ url, body: value })
        if (value.revision !== (library[value.name]?.revision || 0)) return new Response(JSON.stringify({ detail: 'Saved layout changed' }), { status: 409 })
        library[value.name] = { ...value, revision: value.revision + 1, updated_at: 1, panel_count: value.layout.panels.length }
        return new Response(JSON.stringify(library[value.name]))
      }
      const parsed = new URL(url, 'http://localhost')
      if (parsed.pathname.endsWith('/item')) return new Response(JSON.stringify(library[parsed.searchParams.get('name')!]))
      return new Response(JSON.stringify({ layouts: Object.values(library).filter((entry: any) => entry.name.includes(parsed.searchParams.get('query') || '')) }))
    }
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

it('updates panel choices and open geometry labels without losing the draft on language change', async () => {
  const previous = language.value
  setLanguage('zh')
  const wrapper = mount(WorkbenchTab, { props: { deviceConnected: false, symbolLoaded: false }, attachTo: document.body })
  try {
    await flushPromises()
    await wrapper.vm.execute('panel.add', { type: 'watch', title: 'Scope' })
    await wrapper.get('.workbench-actions button').trigger('click')
    await wrapper.get('button[aria-label="配置面板"]').trigger('click')
    const draft = document.querySelector<HTMLInputElement>('dialog input')!
    draft.value = 'Draft'
    draft.dispatchEvent(new Event('input', { bubbles: true }))
    setLanguage('en')
    await nextTick()
    expect(wrapper.get('option[value="variables"]').text()).toBe('Variables')
    expect(document.querySelector('dialog .geometry-fields label')?.textContent).toBe('Column')
    expect(draft.value).toBe('Draft')
  } finally {
    wrapper.unmount()
    setLanguage(previous)
  }
})

it('shares named save/search/load with the dialog and preserves the current-layout revision', async () => {
  const wrapper = mount(WorkbenchTab, { props: { deviceConnected: false, symbolLoaded: false }, attachTo: document.body })
  await flushPromises()
  const a = await wrapper.vm.execute('panel.add', { type: 'watch', title: 'Motor' }) as any
  await flushPromises()
  const context = { frontendGuarded: true as const, fetch: vi.fn(fetch) }
  const stored = await wrapper.vm.execute('layout.save', { name: '电机波形' }, context)
  expect(stored.revision).toBe(1)
  expect(context.fetch).toHaveBeenCalled()
  expect(saved.panels).toEqual([])
  expect((await wrapper.vm.execute('layout.search', { query: '电机' })).layouts).toHaveLength(1)
  await wrapper.vm.execute('panel.remove', { panel_id: a.id })
  await wrapper.get('[data-testid="load-layout"]').trigger('click')
  await flushPromises()
  const dialog = document.querySelector('dialog')!
  ;(dialog.querySelector('.layout-results button') as HTMLButtonElement).click()
  await flushPromises()
  dialog.querySelector('.layout-submit')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
  await flushPromises()
  expect(wrapper.vm.entries().map(panel => panel.id)).toEqual([a.id])
  expect(wrapper.vm.read().layout.revision).toBe(1)
  expect(document.querySelector('dialog')).toBeNull()
  await wrapper.vm.execute('layout.save', {})
  expect(saved.revision).toBe(2)
  expect(saved.panels[0].id).toBe(a.id)
  await expect(wrapper.vm.execute('layout.save', { name: '电机波形' })).rejects.toThrow('Saved layout changed')
  await wrapper.vm.execute('layout.save', { name: '电机波形', revision: 1 })
  expect(library['电机波形'].revision).toBe(2)
  await wrapper.vm.execute('layout.save', { name: '全局波形', scope: 'global' })
  expect(writes.at(-1)?.body.scope).toBe('global')
  await expect(wrapper.vm.execute('layout.load', { name: '' })).rejects.toThrow('nonempty')
  await expect(wrapper.vm.execute('layout.save', { scope: 'global' })).rejects.toThrow('requires a layout name')
  const before = JSON.stringify(wrapper.vm.read().layout)
  failLoad = true
  await expect(wrapper.vm.execute('layout.load', { name: '电机波形' })).rejects.toThrow('Unavailable')
  expect(JSON.stringify(wrapper.vm.read().layout)).toBe(before)
  wrapper.unmount()
})

it('moves and resizes while viewing or editing without remounting business views', async () => {
  const wrapper = mount(WorkbenchTab, { props: { deviceConnected: false, symbolLoaded: false } })
  await flushPromises()
  const a = await wrapper.vm.execute('panel.add', { type: 'watch', title: 'Wave' }) as any
  const b = await wrapper.vm.execute('panel.add', { type: 'controls', title: 'Control' }) as any
  await flushPromises()
  const grid = (wrapper.get('.workbench-grid').element as HTMLElement & { gridstack: GridStack }).gridstack
  const surface = wrapper.vm.entries()[0]!.surface
  expect(grid.opts.disableDrag).toBeFalsy()
  expect(grid.opts.disableResize).toBeFalsy()
  expect(wrapper.findAll('button[aria-label="关闭面板"]')).toHaveLength(2)
  expect(wrapper.find('[aria-label="配置面板"]').exists()).toBe(false)
  await wrapper.get('[aria-pressed="false"]').trigger('click')
  expect(grid.opts.disableDrag).toBeFalsy()
  expect(grid.opts.disableResize).toBeFalsy()
  grid.update(grid.engine.nodes.find(node => node.id === b.id)!.el!, { x: 0, y: 0 })
  await flushPromises()
  const pointerLayout = JSON.parse(JSON.stringify(wrapper.vm.read().layout))
  expect(pointerLayout.panels.find((panel: any) => panel.id === b.id).y).toBe(0)
  expect(pointerLayout.panels.find((panel: any) => panel.id === a.id).y).toBe(4)
  expect(wrapper.vm.entries()[0]!.surface).toBe(surface)
  await wrapper.vm.execute('layout.save', {})
  expect(saved.panels).toEqual(pointerLayout.panels.map((panel: any) => ({ ...panel, view: { paused: false } })))
  await wrapper.vm.execute('panel.move', { panel_id: a.id, x: 0, y: 0, w: 6, h: 4 })
  await flushPromises()
  expect(grid.engine.nodes.find(node => node.id === a.id)?.y).toBe(0)
  expect(grid.engine.nodes.find(node => node.id === b.id)?.y).toBe(4)
  expect(wrapper.vm.entries()[0]!.surface).toBe(surface)
  wrapper.unmount()
})

it('rolls back an out-of-range grid gesture and retains the last valid layout', async () => {
  const wrapper = mount(WorkbenchTab, { props: { deviceConnected: false, symbolLoaded: false } })
  await flushPromises()
  await wrapper.vm.execute('panel.add', { type: 'watch', title: 'Wave' })
  await flushPromises()
  const before = JSON.stringify(wrapper.vm.read().layout)
  const grid = (wrapper.get('.workbench-grid').element as HTMLElement & { gridstack: GridStack }).gridstack
  grid.update(grid.engine.nodes[0]!.el!, { y: 201 })
  await flushPromises()
  expect(JSON.stringify(wrapper.vm.read().layout)).toBe(before)
  expect(grid.engine.nodes[0]?.y).toBe(0)
  expect(wrapper.get('[role="alert"]').text()).not.toBe('')
  wrapper.unmount()
})

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

it('resizes a tall variable panel with the single-column separator and closes it in viewing mode', async () => {
  const wrapper = mount(WorkbenchTab, { props: { deviceConnected: false, symbolLoaded: true } })
  try {
    await flushPromises()
    const panel = await wrapper.vm.execute('panel.add', { type: 'variables', title: 'Variables' }) as any
    await wrapper.vm.execute('panel.move', { panel_id: panel.id, x: 0, y: 0, w: 6, h: 12 })
    const card = wrapper.get('article[data-panel-id]')
    await card.get('.narrow-panel-resize').trigger('keydown', { key: 'ArrowDown' })
    expect(wrapper.vm.read().layout.panels[0]).toMatchObject({ x: 0, w: 6, h: 13 })
    await wrapper.vm.execute('layout.save', {})
    expect(saved.panels[0].h).toBe(13)
    await card.get('button[aria-label="关闭面板"]').trigger('click')
    expect(wrapper.vm.entries()).toHaveLength(1)
    document.querySelector<HTMLButtonElement>('[data-testid="confirm-close-panel"]')!.click()
    await nextTick()
    expect(wrapper.vm.entries()).toHaveLength(0)
    expect(wrapper.vm.read().dirty).toBe(true)
    expect(saved.panels).toHaveLength(1)
  } finally { wrapper.unmount() }
})

it('shares split and enlarged views with the Agent without changing a panel identity', async () => {
  const wrapper = mount(WorkbenchTab, { attachTo: document.body, props: { deviceConnected: false, symbolLoaded: false } })
  try {
    await flushPromises()
    const first = await wrapper.vm.execute('panel.add', { type: 'watch', title: 'Wave' }) as any
    const second = await wrapper.vm.execute('panel.add', { type: 'variables', title: 'Variables' }) as any
    await wrapper.vm.execute('panel.split', { panel_id: first.id, target_panel_id: second.id, columns: 7 })
    const surface = wrapper.vm.entries()[0]!.surface
    await wrapper.vm.execute('panel.enlarge', { panel_id: first.id, open: true })
    expect(wrapper.vm.read().enlarged).toBe(first.id)
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await nextTick()
    expect(wrapper.vm.read().enlarged).toBe('')
    expect(wrapper.vm.entries()[0]!.surface).toBe(surface)
    expect(wrapper.vm.read().layout.panels.map(p => p.w)).toEqual([7, 5])
  } finally { wrapper.unmount() }
})

it('tracks save, revert and restore through the same user and Agent layout', async () => {
  const wrapper = mount(WorkbenchTab, { props: { deviceConnected: false, symbolLoaded: false } })
  try {
    await flushPromises()
    const save = wrapper.get('[data-testid="save-layout"]')
    expect(save.attributes('disabled')).toBeDefined()
    const a = await wrapper.vm.execute('panel.add', { type: 'variables', title: 'A' }) as any
    const b = await wrapper.vm.execute('panel.add', { type: 'rtt', title: 'B' }) as any
    expect(save.attributes('disabled')).toBeUndefined()
    await wrapper.vm.execute('panel.dock', { panel_id: a.id, target_panel_id: b.id })
    await wrapper.vm.execute('layout.save', {})
    expect(save.attributes('disabled')).toBeDefined()
    await wrapper.vm.execute('panel.configure', { panel_id: b.id, title: 'B2', channel: 1 })
    expect(wrapper.vm.read().dirty).toBe(true)
    await wrapper.vm.execute('panel.configure', { panel_id: b.id, title: 'B', channel: 0 })
    expect(wrapper.vm.read().dirty).toBe(false)
    await wrapper.vm.execute('panel.remove', { panel_id: a.id })
    expect(wrapper.vm.read().layout.closed?.[0]).toMatchObject({ id: a.id, dockWith: b.id })
    await wrapper.vm.execute('layout.save', {})
    await wrapper.vm.execute('layout.restore', {})
    await wrapper.vm.execute('panel.reopen', { panel_id: a.id })
    expect(wrapper.vm.read().layout.docks?.[0]?.panels).toEqual([b.id, a.id])
    expect(wrapper.vm.read().layout.closed).toBeUndefined()
    expect(wrapper.vm.read().dirty).toBe(true)
  } finally { wrapper.unmount() }
})

it('keeps changes made during a save pending, including after a rejected save', async () => {
  const wrapper = mount(WorkbenchTab, { props: { deviceConnected: false, symbolLoaded: false } })
  try {
    await flushPromises()
    const a = await wrapper.vm.execute('panel.add', { type: 'variables', title: 'A' }) as any
    let finish!: () => void
    const gate = new Promise<void>(r => { finish = r })
    const normal = fetch
    const context = { frontendGuarded: true as const, fetch: vi.fn(async (...args: Parameters<typeof fetch>) => { await gate; return normal(...args) }) }
    const writing = wrapper.vm.execute('layout.save', {}, context)
    await wrapper.vm.execute('panel.configure', { panel_id: a.id, title: 'After request', signals: [] })
    finish()
    await writing
    expect(saved.panels[0].title).toBe('A')
    expect(wrapper.vm.read().dirty).toBe(true)
    saved.revision++
    await expect(wrapper.vm.execute('layout.save', {})).rejects.toThrow()
    expect(wrapper.vm.read().dirty).toBe(true)
    expect(wrapper.vm.entries()[0]?.title).toBe('After request')
  } finally { wrapper.unmount() }
})

it('places each Agent message at its owning panel without moving keyboard focus', async () => {
  const wrapper = mount(WorkbenchTab, { props: { deviceConnected: false, symbolLoaded: false }, attachTo: document.body })
  try {
    await flushPromises()
    const chart = await wrapper.vm.execute('panel.add', { type: 'chart', title: 'Results' }) as { id: string }
    const other = await wrapper.vm.execute('panel.add', { type: 'chart', title: 'Other' }) as { id: string }
    const article = wrapper.get(`[data-panel-id="${chart.id}"]`)
    const button = wrapper.get(`[data-panel-id="${other.id}"] button`).element as HTMLButtonElement
    button.focus()
    const update = { id: 'done', target: chart.id, title: 'Updated Results', detail: '' }
    const rejection = { ...update, id: 'declined', title: 'Update declined', detail: 'The layout changed' }
    await wrapper.setProps({ agentFeedback: {
      updates: new Map([[chart.id, update]]), rejections: new Map([[chart.id, rejection]]),
    } })
    expect(article.get('header [role="status"]').attributes('aria-label')).toBe('Updated Results')
    expect(article.get('header + [role="alert"]').text()).toContain('Update declined')
    expect(wrapper.findAll('[data-testid="agent-update"]')).toHaveLength(1)
    expect(wrapper.findAll('[data-testid="agent-rejection"]')).toHaveLength(1)
    expect(document.activeElement).toBe(button)
    await wrapper.setProps({ agentFeedback: { updates: new Map(), rejections: new Map([['', { ...rejection, target: '' }]]) } })
    expect(wrapper.get('.workbench-toolbar + [role="alert"]').text()).toContain('Update declined')
    expect(article.find('[role="alert"]').exists()).toBe(false)
  } finally { wrapper.unmount() }
})
