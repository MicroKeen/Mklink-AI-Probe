import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import WorkbenchPanel from './WorkbenchPanel.vue'
import { setLanguage } from '../../composables/useLanguage'

const api = vi.hoisted(() => ({ readMemory: vi.fn(), writeMemory: vi.fn() }))
vi.mock('../../composables/useDashboard', () => ({ useDeviceApi: () => api }))
vi.mock('../../composables/useDashboardSetup', () => ({ useDashboardSetup: () => ({ connecting: false, quickConnect: vi.fn() }) }))
const mounted: ReturnType<typeof mount>[] = []
async function memory(id: string) {
  setLanguage('zh')
  const host = document.createElement('div'); document.body.append(host)
  const wrapper = mount(WorkbenchPanel, { attachTo: host, props: { panel: { id, type: 'tool', title: id, source: { tool: 'memory' }, x: 0, y: 0, w: 12, h: 8 }, deviceConnected: true, symbolLoaded: true, latestValues: {}, rtt: {} } })
  mounted.push(wrapper); await vi.dynamicImportSettled(); await flushPromises()
  return wrapper
}
afterEach(() => { mounted.splice(0).forEach(wrapper => wrapper.unmount()); document.body.innerHTML = ''; vi.clearAllMocks() })
describe('complete GUI inside flexible panels', () => {
  it('renders real memory bytes after human and Agent operations, including original write/read-back behavior', async () => {
    api.readMemory.mockResolvedValue({ address: '0x20001000', data_hex: '41424344' })
    api.writeMemory.mockResolvedValue({})
    const wrapper = await memory('memory_one')
    await wrapper.get('.mem-controls .addr-input').setValue('0x20001000')
    await wrapper.get('.mem-controls button').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('ABCD')
    expect(api.readMemory).toHaveBeenCalledWith('0x20001000', 64)
    const controls = () => wrapper.vm.execute('view.controls', {}).then((value: any) => value.controls)
    let items = await controls()
    const writeAddress = items.find((item: any) => item.label === '地址')
    await wrapper.vm.execute('view.control.set', { control_id: writeAddress.id, value: '0x20001001' })
    items = await controls()
    await wrapper.vm.execute('view.control.set', { control_id: items.find((item: any) => item.label.startsWith('十六进制数据')).id, value: 'A1B2' })
    items = await controls()
    const receipt = await wrapper.vm.execute('view.control.click', { control_id: items.find((item: any) => item.label === '写入').id }) as any
    expect(receipt.status).toBe('dispatched')
    await flushPromises()
    expect(api.writeMemory).toHaveBeenCalledWith('0x20001001', 'A1B2')
    expect(api.readMemory).toHaveBeenCalledTimes(2)
    expect(wrapper.get('.mem-write .addr-input').element.value).toBe('0x20001001')
    const state = await wrapper.vm.execute('view.read', {}) as any
    expect(state.text).toContain('ABCD')
  })
  it('refuses another panel’s controls, stale fields, hidden controls and ordinary inert surfaces', async () => {
    const left = await memory('left'), right = await memory('right')
    const controls = await left.vm.execute('view.controls', {}) as any
    const address = controls.controls.find((control: any) => control.type === 'text')
    await expect(right.vm.execute('view.control.set', { control_id: address.id, value: '0x20002000' })).rejects.toThrow('outside')
    await left.get('.addr-input').setValue('0x20003000')
    await expect(left.vm.execute('view.control.set', { control_id: address.id, value: '0x20002000' })).rejects.toThrow('changed')
    const fresh = await left.vm.execute('view.controls', {}) as any
    const input = fresh.controls.find((control: any) => control.type === 'text')
    left.element.parentElement!.setAttribute('inert', '')
    await expect(left.vm.execute('view.control.set', { control_id: input.id, value: '0x20002000' })).rejects.toThrow('hidden')
    left.element.parentElement!.setAttribute('data-frontend-busy', 'true')
    await left.vm.execute('view.control.set', { control_id: input.id, value: '0x20002000' })
    expect(left.get('.addr-input').element.value).toBe('0x20002000')
    expect(right.get('.addr-input').element.value).toBe('0x20000000')
    expect(api.writeMemory).not.toHaveBeenCalled()
  })
})
