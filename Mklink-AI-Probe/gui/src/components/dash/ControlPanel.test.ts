import { mount, flushPromises } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import ControlPanel from './ControlPanel.vue'
import { bindingHostKey, type BindingHost } from '../../lib/workbenchBindings'
import { objectSchema } from '../../lib/frontendControl'
import { controlStateKey, createControlState, type ControlState, type ControlWidget } from '../../lib/workbenchControls'

function fixture(commit?: (widgets: ControlWidget[]) => void, transient?: ControlState) {
  const state = { paused: false, interval: 1 }
  const actions = [
    { name: 'waveform.pause', description: 'Pause this view', effect: 'view', args: objectSchema({ paused: { type: 'boolean' } }) },
    { name: 'sample.interval', description: 'Set interval', effect: 'device', args: objectSchema({ interval: { type: 'number', minimum: 0.01, maximum: 10 } }) },
  ]
  const invoke = vi.fn(async (_id: string, action: string, args: any) => { if (action === 'waveform.pause') state.paused = args.paused; else state.interval = args.interval; return { ...state } })
  const host: BindingHost = { targets: () => [{ id: 'wave', title: 'Wave A', type: 'watch', surface: { catalog: () => actions, read: () => ({ view: { ...state } }), execute: (action, args) => invoke('wave', action, args) } }], invoke }
  const wrapper = mount(ControlPanel, { props: { panelId: 'controls', widgets: [], commitWidgets: commit }, global: { provide: { [bindingHostKey as symbol]: host, ...(transient ? { [controlStateKey as symbol]: transient } : {}) } } })
  return { wrapper, host, state, invoke, actions }
}
it('manual controls and Agent invocation dispatch the same declared business action', async () => {
  const { wrapper, invoke, state } = fixture()
  const widget = await wrapper.vm.execute('component.add', { type: 'button', title: 'Pause Wave' }) as ControlWidget
  await wrapper.vm.execute('component.bind', { component_id: widget.id, panel_id: 'wave', action: 'waveform.pause', args_json: '{"paused":true}' })
  await wrapper.get(`[data-component-id="${widget.id}"] .control-body > button`).trigger('click')
  await flushPromises()
  expect(state.paused).toBe(true)
  await wrapper.vm.execute('component.invoke', { component_id: widget.id, args_json: '{"paused":false}' })
  expect(state.paused).toBe(false)
  expect(invoke.mock.calls.map(call => call[2])).toEqual([{ paused: true }, { paused: false }])
  wrapper.unmount()
})
it('forms use typed schema controls without publishing or saving transient input', async () => {
  const { wrapper, invoke, state } = fixture()
  const widget = await wrapper.vm.execute('component.add', { type: 'form', title: 'Sampling' }) as ControlWidget
  await wrapper.vm.execute('component.bind', { component_id: widget.id, panel_id: 'wave', action: 'sample.interval', args_json: '{}' })
  await wrapper.get('input[aria-label="interval"]').setValue('0.125')
  expect(JSON.stringify(wrapper.vm.read())).not.toContain('0.125')
  await wrapper.get('.control-body form').trigger('submit')
  await flushPromises()
  expect(state.interval).toBe(0.125)
  expect(invoke).toHaveBeenCalledTimes(1)
  expect(wrapper.vm.read().widgets[0].binding.args).toEqual({})
  wrapper.unmount()
})
it('preserves explicitly empty optional strings from the UI, Agent input and saved arguments', async () => {
  const { wrapper, actions, invoke } = fixture()
  actions.push({ name: 'signals.alias', description: 'Set optional alias', effect: 'view', args: objectSchema({ alias: { type: 'string', maxLength: 100 } }, []) })
  let alias = 'Old'
  invoke.mockImplementation(async (_id, _action, args) => { if (Object.hasOwn(args, 'alias')) alias = args.alias; return { paused: false, interval: 1 } })
  const widget = await wrapper.vm.execute('component.add', { type: 'form', title: 'Alias' }) as ControlWidget
  await wrapper.vm.execute('component.bind', { component_id: widget.id, panel_id: 'wave', action: 'signals.alias', args_json: '{"alias":"Old"}' })
  await wrapper.get('input[aria-label="alias"]').setValue('')
  await wrapper.get('.control-body form').trigger('submit'); await flushPromises()
  expect(alias).toBe('')
  expect(invoke.mock.calls.at(-1)?.[2]).toEqual({ alias: '' })
  await wrapper.vm.execute('component.input', { component_id: widget.id, args_json: '{"alias":"New"}' })
  await wrapper.vm.execute('component.invoke', { component_id: widget.id })
  expect(alias).toBe('New')
  await wrapper.vm.execute('component.input', { component_id: widget.id, args_json: '{"alias":""}' })
  await wrapper.vm.execute('component.invoke', { component_id: widget.id })
  expect(alias).toBe('')
  expect(wrapper.vm.read().widgets[0].binding.args).toEqual({ alias: 'Old' })
  await wrapper.vm.execute('component.configure', { component_id: widget.id, args_json: '{"alias":""}' })
  await wrapper.vm.execute('component.invoke', { component_id: widget.id })
  expect(invoke.mock.calls.at(-1)?.[2]).toEqual({ alias: '' })
  await wrapper.vm.execute('component.configure', { component_id: widget.id, args_json: '{}' })
  await wrapper.vm.execute('component.invoke', { component_id: widget.id })
  expect(invoke.mock.calls.at(-1)?.[2]).toEqual({})
  wrapper.unmount()
})
it('global transaction rejection leaves the local model unchanged', async () => {
  const { wrapper } = fixture(() => { throw new Error('Workspace component limit') })
  await expect(wrapper.vm.execute('component.add', { type: 'button', title: 'Rejected' })).rejects.toThrow('Workspace component limit')
  expect(wrapper.vm.read().widgets).toEqual([])
  wrapper.unmount()
})
it('failed or uncertain mutations are visible and uncertain results are not invoked twice', async () => {
  const { wrapper, invoke } = fixture()
  const widget = await wrapper.vm.execute('component.add', { type: 'button', title: 'Pause' }) as ControlWidget
  await wrapper.vm.execute('component.bind', { component_id: widget.id, panel_id: 'wave', action: 'waveform.pause', args_json: '{"paused":true}' })
  invoke.mockRejectedValue(Object.assign(new Error('Response lost'), { unknown: true }))
  await expect(wrapper.vm.execute('component.invoke', { component_id: widget.id })).rejects.toThrow('Response lost')
  await expect(wrapper.vm.execute('component.invoke', { component_id: widget.id })).rejects.toThrow('unknown')
  expect(invoke).toHaveBeenCalledTimes(1)
  expect(wrapper.vm.read().statuses[widget.id]).toMatchObject({ status: 'unknown', message: 'Error: Response lost' })
  wrapper.unmount()
})
it('does not attach a previous successful result to a new uncertain operation', async () => {
  const { wrapper, invoke } = fixture()
  const widget = await wrapper.vm.execute('component.add', { type: 'button', title: 'Pause' }) as ControlWidget
  await wrapper.vm.execute('component.bind', { component_id: widget.id, panel_id: 'wave', action: 'waveform.pause', args_json: '{"paused":true}' })
  await wrapper.vm.execute('component.invoke', { component_id: widget.id })
  const successful = wrapper.vm.read().statuses[widget.id]
  expect(successful.result_summary).toContain('paused')
  invoke.mockRejectedValue(Object.assign(new Error('Lost new response'), { unknown: true }))
  await expect(wrapper.vm.execute('component.invoke', { component_id: widget.id })).rejects.toThrow('Lost new response')
  const current = wrapper.vm.read().statuses[widget.id]
  expect(current.status).toBe('unknown')
  expect(current.operation_id).not.toBe(successful.operation_id)
  expect(current).not.toHaveProperty('result_summary')
  expect(wrapper.find('.control-result').exists()).toBe(false)
  wrapper.unmount()
})
it('keeps an unknown operation after applying unchanged editor binding and rejects replacement or unbinding', async () => {
  const { wrapper, invoke } = fixture()
  const widget = await wrapper.vm.execute('component.add', { type: 'button', title: 'Pause' }) as ControlWidget
  await wrapper.vm.execute('component.bind', { component_id: widget.id, panel_id: 'wave', action: 'waveform.pause', args_json: '{"paused":true}' })
  invoke.mockRejectedValue(Object.assign(new Error('Response lost'), { unknown: true }))
  await expect(wrapper.vm.execute('component.invoke', { component_id: widget.id })).rejects.toThrow('Response lost')
  const original = wrapper.vm.read().statuses[widget.id]
  await wrapper.vm.execute('component.editor', { component_id: widget.id, open: true })
  await wrapper.get('.component-editor').trigger('submit')
  await flushPromises()
  expect(wrapper.vm.read().statuses[widget.id]).toEqual(original)
  await wrapper.vm.execute('component.configure', { component_id: widget.id, title: 'Still awaiting result', x: 4 })
  expect(wrapper.vm.read().statuses[widget.id]).toEqual(original)
  await expect(wrapper.vm.execute('component.configure', { component_id: widget.id, args_json: '{"paused":false}' })).rejects.toThrow('binding cannot be replaced')
  await expect(wrapper.vm.execute('component.unbind', { component_id: widget.id })).rejects.toThrow('binding cannot be replaced')
  await expect(wrapper.vm.execute('component.invoke', { component_id: widget.id })).rejects.toThrow('unknown')
  expect(invoke).toHaveBeenCalledTimes(1)
  expect(wrapper.vm.read().widgets[0].binding.args).toEqual({ paused: true })
  wrapper.unmount()
})
it('preserves a running action when display settings change and rejects changing its binding', async () => {
  const { wrapper, invoke } = fixture()
  const widget = await wrapper.vm.execute('component.add', { type: 'button', title: 'Pause' }) as ControlWidget
  await wrapper.vm.execute('component.bind', { component_id: widget.id, panel_id: 'wave', action: 'waveform.pause', args_json: '{"paused":true}' })
  let finish!: (value: { paused: boolean; interval: number }) => void
  invoke.mockImplementation(() => new Promise(resolve => { finish = resolve }))
  const pending = wrapper.vm.execute('component.invoke', { component_id: widget.id })
  const original = wrapper.vm.read().statuses[widget.id]
  await wrapper.vm.execute('component.configure', { component_id: widget.id, title: 'Running', panel_id: 'wave', action: 'waveform.pause', args_json: '{"paused":true}' })
  expect(wrapper.vm.read().statuses[widget.id]).toEqual(original)
  await expect(wrapper.vm.execute('component.bind', { component_id: widget.id, panel_id: 'wave', action: 'waveform.pause', args_json: '{"paused":false}' })).rejects.toThrow('running or unknown')
  finish({ paused: true, interval: 1 }); await pending
  expect(wrapper.vm.read().statuses[widget.id]).toMatchObject({ status: 'completed', operation_id: original.operation_id })
  expect(invoke).toHaveBeenCalledTimes(1)
  wrapper.unmount()
})
it('keeps transient form input and uncertain status when a component moves between windows', async () => {
  const transient = createControlState()
  const { wrapper: left, host, invoke } = fixture(undefined, transient)
  const right = mount(ControlPanel, { props: { panelId: 'right', widgets: [] }, global: { provide: { [bindingHostKey as symbol]: host, [controlStateKey as symbol]: transient } } })
  const widget = await left.vm.execute('component.add', { type: 'form', title: 'Sampling' }) as ControlWidget
  await left.vm.execute('component.bind', { component_id: widget.id, panel_id: 'wave', action: 'sample.interval', args_json: '{}' })
  await left.vm.execute('component.input', { component_id: widget.id, args_json: '{"interval":0.125}' })
  expect(left.get('input[aria-label="interval"]').element.value).toBe('0.125')
  invoke.mockRejectedValue(Object.assign(new Error('Lost original result'), { unknown: true }))
  await expect(left.vm.execute('component.invoke', { component_id: widget.id })).rejects.toThrow('Lost original result')
  const moved = left.vm.read().widgets[0]
  await left.setProps({ widgets: [] }); await right.setProps({ widgets: [moved] })
  expect(right.get('input[aria-label="interval"]').element.value).toBe('0.125')
  expect(right.vm.read().statuses[widget.id]).toMatchObject({ status: 'unknown' })
  await expect(right.vm.execute('component.invoke', { component_id: widget.id })).rejects.toThrow('unknown')
  expect(invoke).toHaveBeenCalledTimes(1)
  expect(left.vm.read().statuses).toEqual({})
  left.unmount(); right.unmount()
})
it('applies partial binding configuration and exposes the configuration editor semantically', async () => {
  const { wrapper, state } = fixture()
  const widget = await wrapper.vm.execute('component.add', { type: 'button', title: 'Pause' }) as ControlWidget
  await wrapper.vm.execute('component.bind', { component_id: widget.id, panel_id: 'wave', action: 'waveform.pause', args_json: '{"paused":true}' })
  await wrapper.vm.execute('component.configure', { component_id: widget.id, args_json: '{"paused":false}' })
  await wrapper.vm.execute('component.invoke', { component_id: widget.id })
  expect(state.paused).toBe(false)
  await wrapper.vm.execute('component.editor', { component_id: widget.id, open: true })
  expect(wrapper.find('.component-editor').exists()).toBe(true)
  expect(wrapper.vm.read().editing).toBe(widget.id)
  await wrapper.vm.execute('component.editor', { component_id: widget.id, open: false })
  expect(wrapper.find('.component-editor').exists()).toBe(false)
  wrapper.unmount()
})
it('automatically refreshes bound state without business calls or report changes and pauses hidden panels', async () => {
  vi.useFakeTimers()
  const { wrapper, state, invoke } = fixture()
  try {
    const widget = await wrapper.vm.execute('component.add', { type: 'value', title: 'Interval' }) as ControlWidget
    await wrapper.vm.execute('component.bind', { component_id: widget.id, panel_id: 'wave', state_path: 'view.interval' })
    expect(wrapper.get('output').text()).toBe('1')
    const before = wrapper.vm.read()
    state.interval = 2.5
    await vi.advanceTimersByTimeAsync(1000)
    expect(wrapper.get('output').text()).toBe('2.5')
    expect(wrapper.vm.read()).toEqual(before)
    await wrapper.setProps({ active: false }); state.interval = 4
    await vi.advanceTimersByTimeAsync(1000)
    expect(wrapper.get('output').text()).toBe('2.5')
    await wrapper.setProps({ active: true })
    expect(wrapper.get('output').text()).toBe('4')
    expect(invoke).not.toHaveBeenCalled()
  } finally { wrapper.unmount(); vi.useRealTimers() }
})
it('state components read on demand and do not create live-state revision churn', async () => {
  const { wrapper, state, invoke } = fixture()
  const widget = await wrapper.vm.execute('component.add', { type: 'value', title: 'Interval' }) as ControlWidget
  await wrapper.vm.execute('component.bind', { component_id: widget.id, panel_id: 'wave', state_path: 'view.interval' })
  const before = wrapper.vm.read()
  state.interval = 3.5
  expect(await wrapper.vm.execute('component.read', { component_id: widget.id })).toEqual({ component_id: widget.id, value: 3.5 })
  expect(wrapper.vm.read()).toEqual(before)
  expect(invoke).not.toHaveBeenCalled()
  wrapper.unmount()
})
