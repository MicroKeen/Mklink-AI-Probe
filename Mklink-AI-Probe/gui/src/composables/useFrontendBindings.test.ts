import { mount } from '@vue/test-utils'
import { defineComponent, inject, ref } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { bindingHostKey, type BindingHost } from '../lib/workbenchBindings'
import { objectSchema, withFrontendTarget, type SemanticSurface } from '../lib/frontendControl'
import { useFrontendWorkbench } from './useFrontendWorkbench'

const fixture = vi.hoisted(() => ({ options: null as any }))
vi.mock('../lib/frontendControl', async importOriginal => {
  const original = await importOriginal<typeof import('../lib/frontendControl')>()
  return { ...original, connectFrontend: (options: any) => {
    fixture.options = options
    options.ready({ report: () => ({ session_id: 'test-session' }) }, { instance_id: 'instance', probe_id: 'probe', device_generation: 1, project_root: 'project' })
    return () => {}
  } }
})
afterEach(() => { fixture.options = null })

describe('workbench binding dispatch', () => {
  it('routes user controls and Agent controls through the same typed domain action', async () => {
    let host!: BindingHost, paused = false
    const execute = vi.fn(async (_name: string, args: any) => { paused = args.paused; return { paused } })
    const surface: SemanticSurface = {
      catalog: () => [{ name: 'set', description: 'Set display pause', args: objectSchema({ paused: { type: 'boolean' } }), effect: 'view' }],
      read: () => ({ paused }), execute,
    }
    const control: SemanticSurface = { catalog: () => [{ name: 'component.invoke', description: 'Invoke binding', args: objectSchema() }], read: () => ({}), execute: async (_action, _args, context) => { await Promise.resolve(); return host.invoke('superwatch', 'set', { paused: false }, context) } }
    const Child = defineComponent({ setup() { host = inject(bindingHostKey)!; return () => null } })
    const Harness = defineComponent({ components: { Child }, setup() {
      useFrontendWorkbench(ref('workbench'), ref(surface), ref({ ...surface, entries: () => [{ id: 'controls', title: 'Controls', type: 'controls', surface: control }] }))
      return {}
    }, template: '<Child />' })
    const wrapper = mount(Harness)
    expect(await host.invoke('superwatch', 'set', { paused: true })).toEqual({ paused: true })
    const action = Object.entries(fixture.options.adapter.actions).find(([, d]: any) => d.panel_id === 'controls')![0]
    const agentExecute = async () => {
      fixture.options.busy(true)
      try { return await withFrontendTarget('test-session', { instance_id: 'instance', probe_id: 'probe', device_generation: 1, project_root: 'project' }, () => fixture.options.adapter.execute(action, {})) }
      finally { fixture.options.busy(false) }
    }
    expect(await agentExecute()).toEqual({ paused: false })
    expect(execute).toHaveBeenCalledTimes(2)
    let finish!: (value: { paused: boolean }) => void
    execute.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    const pending = agentExecute()
    await Promise.resolve(); await Promise.resolve()
    await expect(host.invoke('superwatch', 'set', { paused: true })).rejects.toThrow('already running')
    expect(execute).toHaveBeenCalledTimes(3)
    finish({ paused: false }); await pending
    await expect(host.invoke('superwatch', 'set', { paused: 'false' })).rejects.toThrow()
    await expect(host.invoke('missing', 'set', { paused: true })).rejects.toThrow('unavailable')
    expect(execute).toHaveBeenCalledTimes(3)
    wrapper.unmount()
  })
})
