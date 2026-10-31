import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import AcquisitionClockControl from './AcquisitionClockControl.vue'

const clocks = [1000, 5000, 10000, 20000, 50000, 100000, 200000, 500000,
  1000000, 2000000, 5000000, 10000000, 20000000, 30000000]
function initial() {
  return { connected: true, device_generation: 7, interface: 'SWD', clocks_hz: clocks,
    clock_source: 'v3-advertised', requested_hz: 10000000, configured_hz: 10000000,
    applied_hz: 10000000 as number | null, apply_state: 'applied', migration: null as null | { from_hz: number; to_hz: number; pending: boolean } }
}
function response(value: unknown, ok = true) { return { ok, statusText: ok ? 'OK' : 'Conflict', json: async () => value } }
let data: ReturnType<typeof initial>
let post: (body: { clock_hz: number; save: boolean }) => Promise<unknown>
let requests: ReturnType<typeof vi.fn>
const wrappers: ReturnType<typeof mount>[] = []
async function setup() {
  const wrapper = mount(AcquisitionClockControl, { props: { deviceConnected: true, deviceGeneration: 7 } })
  wrappers.push(wrapper)
  await flushPromises()
  return wrapper
}
async function apply(wrapper: ReturnType<typeof mount>, hz: number) {
  await wrapper.get('#acquisition-clock-hz').setValue(String(hz))
  await wrapper.get('[data-testid="apply-acquisition-clock"]').trigger('click')
  await flushPromises()
}

beforeEach(() => {
  vi.useFakeTimers()
  data = initial()
  post = async body => {
    data = { ...data, requested_hz: body.clock_hz, configured_hz: body.clock_hz,
      applied_hz: body.clock_hz, apply_state: 'applied', migration: null }
    return response(data)
  }
  requests = vi.fn(async (_url: string, init?: RequestInit) => init?.method === 'POST'
    ? post(JSON.parse(String(init.body))) : response(structuredClone(data)))
  vi.stubGlobal('fetch', requests)
})
afterEach(() => {
  wrappers.splice(0).forEach(w => w.unmount())
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('shared acquisition clock', () => {
  it('uses all advertised V3 clocks, including kHz, without a manual frequency field', async () => {
    const wrapper = await setup()
    expect(wrapper.findAll('input').length).toBe(0)
    expect(wrapper.findAll('option').slice(1).map(o => Number(o.attributes('value')))).toEqual(clocks)
    await apply(wrapper, 5000)
    const request = requests.mock.calls.find(([, init]) => init?.method === 'POST')![1]
    expect(JSON.parse(request.body)).toEqual({ clock_hz: 5000, save: true })
    expect(new Headers(request.headers).get('X-MKLink-Device-Generation')).toBe('7')
    expect(wrapper.get('[data-testid="acquisition-clock-state"]').text()).toBe('已应用：5 kHz')
  })

  it('preserves the old 4 MHz setting until an explicit migration is acknowledged', async () => {
    Object.assign(data, { requested_hz: 4000000, configured_hz: 4000000, applied_hz: 4000000,
      migration: { from_hz: 4000000, to_hz: 2000000, pending: true } })
    const wrapper = await setup()
    expect(wrapper.get('[data-testid="clock-migration"]').text()).toContain('请选择 2 MHz')
    expect(wrapper.get<HTMLSelectElement>('#acquisition-clock-hz').element.value).toBe('4000000')
    expect(wrapper.get('[data-testid="acquisition-clock-state"]').text()).toContain('4 MHz')
    expect(requests.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
    expect(wrapper.get('[data-testid="apply-acquisition-clock"]').attributes('disabled')).toBeDefined()
    await apply(wrapper, 2000000)
    expect(wrapper.text()).toContain('已迁移到 2 MHz')
    expect(wrapper.find('[data-testid="clock-migration"]').exists()).toBe(false)
  })

  it('does not describe a configured clock as applied or retry it automatically', async () => {
    post = async body => {
      data = { ...data, configured_hz: body.clock_hz, requested_hz: body.clock_hz, applied_hz: null, apply_state: 'configured' }
      return response(data)
    }
    const wrapper = await setup()
    await apply(wrapper, 2000000)
    await vi.advanceTimersByTimeAsync(3000)
    expect(wrapper.get('[data-testid="acquisition-clock-state"]').text()).toBe('已保存，待应用：2 MHz')
    expect(wrapper.text()).toContain('退出 Keil 调试')
    expect(requests.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
  })

  it.each(['busy', 'lost', 'unconfirmed'])('preserves truthful status after %s and never stops or repeats a request', async failure => {
    post = async () => {
      if (failure === 'lost') throw new TypeError('Response lost')
      return failure === 'busy' ? response({ detail: { busy: ['rtt', 'systemview'] } }, false)
        : response({ clock_hz: 2000000 })
    }
    const wrapper = await setup()
    await apply(wrapper, 2000000)
    await vi.advanceTimersByTimeAsync(3000)
    expect(wrapper.get('[data-testid="acquisition-clock-state"]').text()).toBe('已应用：10 MHz')
    expect(wrapper.get<HTMLSelectElement>('#acquisition-clock-hz').element.value).toBe('2000000')
    expect(requests.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
    expect(requests.mock.calls.every(([url]) => !url.includes('/stop'))).toBe(true)
    if (failure === 'busy') expect(wrapper.text()).toContain('原任务保持运行')
  })

  it('tracks external changes without overwriting an unapplied choice', async () => {
    const wrapper = await setup()
    // Another client may apply without changing the persisted default.
    data = { ...data, configured_hz: 30000000, applied_hz: 30000000 }
    await vi.advanceTimersByTimeAsync(1000)
    expect(wrapper.get<HTMLSelectElement>('#acquisition-clock-hz').element.value).toBe('30000000')
    await wrapper.get('#acquisition-clock-hz').setValue('2000000')
    await vi.advanceTimersByTimeAsync(1000)
    expect(wrapper.get<HTMLSelectElement>('#acquisition-clock-hz').element.value).toBe('2000000')
    expect(wrapper.get('[data-testid="acquisition-clock-state"]').text()).toContain('30 MHz')
  })

  it('clears a transient polling failure after status becomes available again', async () => {
    requests.mockRejectedValueOnce(new Error('Temporary status failure'))
    const wrapper = await setup()
    expect(wrapper.text()).toContain('Temporary status failure')
    await vi.advanceTimersByTimeAsync(1000)
    expect(wrapper.text()).not.toContain('Temporary status failure')
    expect(wrapper.get('[data-testid="acquisition-clock-state"]').text()).toContain('10 MHz')
  })

  it('does not apply a late old-device result to a new HPM selection', async () => {
    let finish!: (value: unknown) => void
    post = () => new Promise(resolve => { finish = resolve })
    const wrapper = await setup()
    await apply(wrapper, 2000000)
    Object.assign(data, { device_generation: 8, interface: 'JTAG', clock_source: 'hpm-profiles',
      clocks_hz: [4000000, 10000000, 20000000, 30000000], configured_hz: 4000000, applied_hz: 4000000, requested_hz: 4000000 })
    await wrapper.setProps({ deviceGeneration: 8 })
    await flushPromises()
    finish(response({ ...initial(), configured_hz: 2000000 }))
    await flushPromises()
    expect(wrapper.get<HTMLSelectElement>('#acquisition-clock-hz').element.value).toBe('4000000')
    expect(wrapper.findAll('option').map(o => o.attributes('value'))).not.toContain('2000000')
    expect(wrapper.get('[data-testid="acquisition-clock-state"]').text()).toContain('4 MHz')
  })

  it('does not invent a confirmed clock from a saved request or after disconnecting', async () => {
    Object.assign(data, { configured_hz: null, applied_hz: null, apply_state: 'unknown' })
    const wrapper = await setup()
    expect(wrapper.get('[data-testid="acquisition-clock-state"]').text()).toContain('未确认')
    await wrapper.setProps({ deviceConnected: false })
    await flushPromises()
    expect(wrapper.get('[data-testid="acquisition-clock-state"]').text()).toBe('未连接')
    expect(wrapper.get('[data-testid="apply-acquisition-clock"]').attributes('disabled')).toBeDefined()
  })
})
