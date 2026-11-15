import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import CapabilityPanel from './CapabilityPanel.vue'
import { bindingHostKey } from '../../lib/workbenchBindings'
import { saveTextFile } from '../../lib/downloadTextFile'

vi.mock('../../lib/downloadTextFile', () => ({ saveTextFile: vi.fn(async () => true) }))
const capabilities = ['device_status', 'write_memory'].map(name => ({ name, available: true, description: name, revision: name + '-1', effect: name === 'device_status' ? 'view' : 'device',
  ...(name === 'write_memory' ? { requestBody: { content: { 'application/json': { schema: { type: 'object', properties: {
    address: { type: 'string' }, data_hex: { type: 'string' }, verify: { type: 'boolean', default: false },
  }, required: ['address', 'data_hex'] } } } } } : {}),
}))
beforeEach(() => vi.stubGlobal('fetch', vi.fn(async (_url, options) => ({ ok: true, json: async () => options?.method === 'POST' ? { connected: false } : { capabilities } }))))
afterEach(() => vi.unstubAllGlobals())
async function panel() {
  let wrapper: ReturnType<typeof mount>
  const invoke = vi.fn(async (_panel, action, args) => wrapper.vm.execute(action, args))
  wrapper = mount(CapabilityPanel, { props: { panelId:'cap_one' }, global: { provide: { [bindingHostKey as symbol]: { invoke } } } })
  await flushPromises()
  return { wrapper, invoke }
}
it('selects without executing, reuses the bound action for mouse execution, and exports without replaying', async () => {
  const { wrapper, invoke } = await panel()
  await wrapper.get('select').setValue('device_status')
  await flushPromises()
  expect(vi.mocked(fetch).mock.calls).toHaveLength(1)
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(invoke).toHaveBeenLastCalledWith('cap_one', 'mklink.device_status', { arguments_json:'{}' })
  expect(wrapper.vm.read()).toMatchObject({ status:'completed', result:{ connected:false } })
  expect(wrapper.vm.read()).not.toHaveProperty('draft')
  await wrapper.vm.execute('capability.export', {})
  expect(saveTextFile).toHaveBeenCalledWith(expect.stringContaining('mklink-device_status-'), expect.stringContaining('"connected": false'))
  expect(vi.mocked(fetch).mock.calls).toHaveLength(2)
  wrapper.unmount()
})
it('keeps drafts/results independent and restoring a view never runs a device operation', async () => {
  const first = await panel(), second = await panel()
  first.wrapper.vm.restore({ capability:'write_memory' })
  second.wrapper.vm.restore({ capability:'device_status' })
  await flushPromises()
  await first.wrapper.findAll('input[type=text]')[0]!.setValue('0x20000000')
  expect(second.wrapper.findAll('input[type=text]')).toHaveLength(0)
  expect(first.wrapper.findAll('input[type=text]')[0]!.element.value).toBe('0x20000000')
  expect(first.wrapper.vm.read().view).toEqual({ capability:'write_memory' })
  expect(vi.mocked(fetch).mock.calls).toHaveLength(2)
  first.wrapper.unmount(); second.wrapper.unmount()
})

it('uses labeled fields and readable results/logs without exposing a JSON editor or dump', async () => {
  const { wrapper, invoke } = await panel()
  await wrapper.vm.execute('capability.select', { name:'write_memory' })
  await flushPromises()
  const inputs = wrapper.findAll('input[type=text]')
  await inputs[0]!.setValue('0x20000014')
  await inputs[1]!.setValue('01000000')
  await wrapper.findAll('select')[1]!.setValue('false')
  vi.mocked(fetch).mockResolvedValueOnce({ ok:true, json:async () => ({ rows:[{ name:'g_demo.page', value:1, type:'uint32_t' }] }) } as Response)
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(invoke).toHaveBeenLastCalledWith('cap_one', 'mklink.write_memory', { arguments_json:JSON.stringify({ address:'0x20000014', data_hex:'01000000', verify:false }) })
  expect(wrapper.get('table').text()).toContain('g_demo.page')
  expect(wrapper.get('[aria-label="操作记录"]').text()).toContain('已完成')
  expect(wrapper.find('pre').exists()).toBe(false)
  expect(wrapper.find('textarea').exists()).toBe(false)
  expect(wrapper.text()).not.toContain('JSON')
  wrapper.unmount()
})

it('keeps structured validation failures readable and records failure without replay', async () => {
  const { wrapper } = await panel()
  await wrapper.vm.execute('capability.select', { name:'device_status' })
  vi.mocked(fetch).mockResolvedValueOnce({ ok:false, status:409, json:async () => ({ detail:{ busy:['superwatch'], hint:'请先停止采样' } }) } as Response)
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(wrapper.get('[role=alert]').text()).toBe('请先停止采样')
  expect(wrapper.get('[aria-label="操作记录"]').text()).toContain('失败')
  expect(wrapper.text()).not.toContain('"busy"')
  expect(vi.mocked(fetch).mock.calls).toHaveLength(2)
  wrapper.unmount()
})
it('marks a lost response unknown and prevents replay until explicit selection; known failures remain failures', async () => {
  const { wrapper } = await panel()
  await wrapper.vm.execute('capability.select', { name:'write_memory' })
  vi.mocked(fetch).mockRejectedValueOnce(new TypeError('connection lost'))
  await expect(wrapper.vm.execute('mklink.write_memory', { arguments_json:'{}' })).rejects.toMatchObject({ unknown:true })
  expect(wrapper.vm.read().status).toBe('unknown')
  const count = vi.mocked(fetch).mock.calls.length
  await expect(wrapper.vm.execute('mklink.write_memory', { arguments_json:'{}' })).rejects.toThrow('Query the original')
  expect(vi.mocked(fetch).mock.calls).toHaveLength(count)
  await wrapper.vm.execute('capability.select', { name:'write_memory' })
  vi.mocked(fetch).mockResolvedValueOnce({ ok:false, status:409, json:async () => ({ detail:'Device busy' }) } as Response)
  await expect(wrapper.vm.execute('mklink.write_memory', {})).rejects.toThrow('Device busy')
  expect(wrapper.vm.read().status).toBe('failed')
  wrapper.unmount()
})
it('rejects stale selection and invalid JSON, and bounds large result reports', async () => {
  const { wrapper } = await panel()
  await wrapper.vm.execute('capability.select', { name:'device_status' })
  await expect(wrapper.vm.execute('mklink.write_memory', {})).rejects.toThrow('Capability changed')
  await expect(wrapper.vm.execute('mklink.device_status', { arguments_json:'[]' })).rejects.toThrow('JSON object')
  vi.mocked(fetch).mockResolvedValueOnce({ ok:true, json:async () => ({ records:'x'.repeat(50000) }) } as Response)
  await wrapper.vm.execute('mklink.device_status', {})
  expect(wrapper.vm.read().result).toMatchObject({ truncated:true, characters:50014 })
  expect(JSON.stringify(wrapper.vm.read()).length).toBeLessThan(12000)
  wrapper.unmount()
})

it('retains the original job identity and distinguishes submission from its terminal state', async () => {
  const { wrapper } = await panel()
  await wrapper.vm.execute('capability.select', { name:'device_status' })
  for (const state of ['running', 'succeeded', 'failed', 'unknown']) {
    vi.mocked(fetch).mockResolvedValueOnce({ ok:true, json:async () => ({ job_id:'same-job', state }) } as Response)
    await wrapper.vm.execute('mklink.device_status', {})
    expect(wrapper.vm.read()).toMatchObject({ status:state, result:{ job_id:'same-job', state } })
  }
  wrapper.unmount()
})

it.each(['server', 'json'])('does not turn a %s failure into success or automatically replay it', async kind => {
  const { wrapper } = await panel()
  await wrapper.vm.execute('capability.select', { name:'write_memory' })
  vi.mocked(fetch).mockResolvedValueOnce(kind === 'server'
    ? { ok:false, status:500, json:async () => ({ detail:'Lost acknowledgement' }) } as Response
    : { ok:true, json:async () => { throw new SyntaxError('Truncated response') } } as unknown as Response)
  await expect(wrapper.vm.execute('mklink.write_memory', {})).rejects.toMatchObject({ unknown:true })
  expect(wrapper.vm.read().status).toBe('unknown')
  expect(vi.mocked(fetch).mock.calls).toHaveLength(2)
  wrapper.unmount()
})
