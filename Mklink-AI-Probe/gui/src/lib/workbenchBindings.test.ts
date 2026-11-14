import { describe, expect, it, vi } from 'vitest'
import { objectSchema } from './frontendControl'
import { invokeBinding, makeBinding, readBoundValue, type BindingHost } from './workbenchBindings'

function fixture() {
  const action = { name: 'view.set', effect: 'view', description: 'Configure view', args: objectSchema({ value: { type: 'integer', minimum: 0, maximum: 5 } }) }
  const target = { id: 'wave', title: 'Wave', type: 'watch', surface: { catalog: () => [action], read: () => ({ view: { value: 2 } }), execute: vi.fn() } }
  let available = true
  const host: BindingHost = { targets: () => available ? [target] : [], invoke: vi.fn(async (_id, _action, args) => args) }
  return { host, action, unavailable: () => { available = false } }
}
describe('declared component bindings', () => {
  it('validates saved and submitted arguments against the actual action and keeps the original target', async () => {
    const { host } = fixture()
    expect(() => makeBinding(host, 'button', { panel_id: 'wave', action: 'view.set', args: {} })).toThrow()
    const binding = makeBinding(host, 'form', { panel_id: 'wave', action: 'view.set', args: {} })
    await expect(invokeBinding(host, binding, { value: 8 })).rejects.toThrow()
    expect(host.invoke).not.toHaveBeenCalled()
    expect(await invokeBinding(host, binding, { value: 3 })).toEqual({ value: 3 })
    expect(host.invoke).toHaveBeenCalledWith('wave', 'view.set', { value: 3 }, undefined)
  })
  it('refuses removed targets and changed effects until explicit rebinding', async () => {
    const { host, action, unavailable } = fixture()
    const binding = makeBinding(host, 'button', { panel_id: 'wave', action: 'view.set', args: { value: 2 } })
    action.effect = 'device'
    await expect(invokeBinding(host, binding)).rejects.toThrow('contract changed')
    unavailable()
    await expect(invokeBinding(host, binding)).rejects.toThrow('target is unavailable')
    expect(host.invoke).not.toHaveBeenCalled()
  })
  it('reads only an existing public field and refuses prototype paths or recursive control targets', () => {
    const { host } = fixture()
    expect(readBoundValue(host, makeBinding(host, 'value', { panel_id: 'wave', state_path: 'view.value' }))).toBe(2)
    expect(() => readBoundValue(host, { panel_id: 'wave', state_path: 'view.missing' })).toThrow('unavailable')
    expect(() => readBoundValue(host, { panel_id: 'wave', state_path: 'constructor.name' })).toThrow('Invalid')
    const control = host.targets()[0]!
    control.type = 'controls'
    expect(() => makeBinding(host, 'button', { panel_id: 'wave', action: 'view.set', args: { value: 2 } })).toThrow('unavailable')
  })
})
