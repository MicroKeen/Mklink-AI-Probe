import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  listUartPorts: vi.fn(),
  toastError: vi.fn(),
  toastInfo: vi.fn(),
}))

vi.mock('../../composables/useMklinkApi', () => ({
  useMklinkApi: () => ({ listUartPorts: mocks.listUartPorts }),
}))

vi.mock('../../composables/useToast', () => ({
  useToast: () => ({ error: mocks.toastError, success: vi.fn(), info: mocks.toastInfo }),
}))

import ModbusTab from './ModbusTab.vue'

describe('ModbusTab prerequisites', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    const storage = new Map<string, string>()
    vi.stubGlobal('localStorage', { getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => storage.set(key, value) })
    vi.stubGlobal('EventSource', class { close() {} })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      running: false,
      loop: { revision: 0, running: false, completed: 0, errors: 0 },
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })))
    mocks.listUartPorts.mockResolvedValue([{
      device: 'SERIAL_PORT', description: 'Virtual serial', manufacturer: 'test', vid: null, pid: null,
    }])
  })

  it.each([7, 22, 23])('renders a shared FC%d diagnostic without inventing a register value', async fc => {
    let stream: { onmessage?: (event: { data: string }) => void } = {}
    vi.stubGlobal('EventSource', class {
      constructor() { stream = this }
      close() {}
    })
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      running: true, loop: { revision: 0, running: false },
    }))))
    const wrapper = mount(ModbusTab)
    await flushPromises()
    stream.onmessage?.({ data: JSON.stringify({ event: 'transaction', id: 1, fc, slave: 8,
      start: fc === 7 ? null : 4, values: fc === 22 ? [] : [165], duration_ms: 1,
      and_mask: 65280, or_mask: 85, write_start: 20,
    }) })
    await flushPromises()
    expect(wrapper.text()).toContain(`FC${String(fc).padStart(2, '0')}`)
    expect(wrapper.text()).not.toContain('NaN')
    expect(wrapper.text()).not.toContain('等待响应数据')
    expect(wrapper.find('.result-meta').text()).toContain('从站 8')
    if (fc === 7) {
      expect(wrapper.find('.result-table').text()).toContain('异常状态')
      expect(wrapper.find('.result-meta').text()).not.toContain('地址')
    } else if (fc === 22) {
      expect(wrapper.find('.mask-result').text()).toContain('掩码写入已确认')
      expect(wrapper.find('.mask-result').text()).toContain('FF00')
      expect(wrapper.find('.result-table').exists()).toBe(false)
    } else {
      expect(wrapper.find('.result-meta').text()).toContain('写地址 20')
      expect(wrapper.find('.result-table').text()).toContain('165')
    }
    wrapper.unmount()
  })

  it('shows serial controls without an MKLink Device prerequisite', async () => {
    const wrapper = mount(ModbusTab)
    await flushPromises()

    expect(wrapper.text()).not.toContain('请先连接设备')
    expect(wrapper.find('select').element.value).toBe('SERIAL_PORT')
    expect(wrapper.findAll('button').some(button => button.text() === '连接')).toBe(true)
    const baud = wrapper.get('[data-testid="modbus-baudrate"]')
    expect(baud.element.tagName).toBe('SELECT')
    expect(baud.findAll('option')).toHaveLength(34)
    expect(baud.findAll('option').map(item => item.attributes('value'))).toEqual([
      '300', '600', '1200', '2400', '4800', '9600', '14400', '19200', '38400',
      '56000', '57600', '115200', '128000', '230400', '256000', '460800',
      '512000', '750000', '921600', '1000000', '1500000', '2000000', '2500000',
      '3000000', '3500000', '4000000', '4500000', '5000000', '6000000', '7000000',
      '7500000', '8000000', '9000000', '10000000',
    ])
    wrapper.unmount()
  })

  it.each(['mklink_uart', 'mklink_rs485'])('reads the %s subset, selects 10M and sends its exact value', async kind => {
    const port = { device: 'PROBE_PORT', uart_kind: kind, command_port: 'CMD', usb_serial: 'one' }
    mocks.listUartPorts.mockResolvedValue([port])
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/uart-baudrates')) {
        expect(JSON.parse(String(init?.body))).toEqual({ port: 'PROBE_PORT' })
        return new Response(JSON.stringify({ ...port, uart_baud: { profile: 1, source: 'firmware', rates: [300, 10000000] } }))
      }
      return new Response(JSON.stringify({ running: false }))
    })
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mount(ModbusTab)
    await flushPromises()
    expect(fetchMock.mock.calls.every(([url]) => !url.endsWith('/uart-baudrates'))).toBe(true)
    await wrapper.get('[data-testid="modbus-read-baudrates"]').trigger('click')
    await flushPromises()
    const baud = wrapper.get('[data-testid="modbus-baudrate"]')
    expect(baud.findAll('option').map(item => item.attributes('value'))).toEqual(['300', '10000000'])
    expect((baud.element as HTMLSelectElement).value).toBe('300')
    expect(baud.attributes('title')).toContain(kind === 'mklink_uart' ? 'UART' : 'RS485')
    await baud.setValue('10000000')
    await wrapper.get('.connection-action').trigger('click')
    await flushPromises()
    const start = fetchMock.mock.calls.find(([url]) => url.endsWith('/modbus/start'))
    expect(JSON.parse(String(start?.[1]?.body)).baudrate).toBe(10000000)
    expect(baud.attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it('preserves an active custom baud rate outside the presets', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ running: true,
      connection: { port: 'SERIAL_PORT', baudrate: 250000, bytesize: 8, parity: 'N', stopbits: 1 },
    }))))
    const wrapper = mount(ModbusTab)
    await flushPromises()
    const baud = wrapper.get('[data-testid="modbus-baudrate"]')
    expect((baud.element as HTMLSelectElement).value).toBe('250000')
    expect(baud.attributes('disabled')).toBeDefined()
    expect(baud.text()).toContain('当前会话')
    wrapper.unmount()
  })

  it('ignores a late capability response after unmount', async () => {
    const port = { device: 'RS485', uart_kind: 'mklink_rs485', command_port: 'CMD' }
    mocks.listUartPorts.mockResolvedValue([port])
    let respond!: (response: Response) => void
    vi.stubGlobal('fetch', vi.fn((url: string) => url.endsWith('/uart-baudrates')
      ? new Promise<Response>(resolve => { respond = resolve })
      : Promise.resolve(new Response(JSON.stringify({ running: false })))))
    const wrapper = mount(ModbusTab)
    await flushPromises()
    await wrapper.get('[data-testid="modbus-read-baudrates"]').trigger('click')
    expect(wrapper.get('.connection-action').attributes('disabled')).toBeDefined()
    wrapper.unmount()
    respond(new Response(JSON.stringify({ detail: 'old reply' }), { status: 409 }))
    await flushPromises()
    expect(mocks.toastError).not.toHaveBeenCalled()
  })

  it('surfaces the backend serial-port conflict instead of entering running state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({
      detail: { conflict: 'user:dashboard:serial', resource: 'serial_port' },
    }), {
      status: 409,
      headers: { 'Content-Type': 'application/json' },
    }))))
    const wrapper = mount(ModbusTab)
    await flushPromises()

    await wrapper.findAll('button').find(button => button.text() === '连接')!.trigger('click')
    await flushPromises()

    expect(mocks.toastError).toHaveBeenCalledWith(expect.stringContaining('user:dashboard:serial'))
    expect(wrapper.findAll('button').some(button => button.text() === '连接')).toBe(true)
  })
  it('keeps stop pending visible and permits retry after a failed disconnect', async () => {
    let stopping = false
    const fetch = vi.fn(async (url: string) => {
      if (url.endsWith('/stop')) {
        stopping = true
        return new Response(JSON.stringify({ detail: 'worker still active' }), { status: 409 })
      }
      return new Response(JSON.stringify({ running: !stopping, stopping, loop: { revision: 0, running: false } }))
    })
    vi.stubGlobal('fetch', fetch)
    const wrapper = mount(ModbusTab)
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === '断开连接')!.trigger('click')
    await flushPromises()
    expect(mocks.toastError).toHaveBeenCalledWith(expect.stringContaining('worker still active'))
    expect(mocks.toastInfo).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('等待停止')
    expect(wrapper.findAll('button').some(button => button.text() === '连接')).toBe(false)
    expect(wrapper.find('.send-button').attributes('disabled')).toBeDefined()
    expect(wrapper.find('select').attributes('disabled')).toBeDefined()
    expect(wrapper.findAll('button').find(button => button.text() === '断开连接')!.attributes('disabled')).toBeUndefined()
    wrapper.unmount()
  })

  it('does not claim the loop stopped when the backend times out', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url.endsWith('/loop/stop')
      ? new Response(JSON.stringify({ detail: 'loop still active' }), { status: 409 })
      : new Response(JSON.stringify({ running: true, loop: { revision: 0, running: true, completed: 1, errors: 0 } }))))
    const wrapper = mount(ModbusTab)
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === '停止循环')!.trigger('click')
    await flushPromises()
    expect(mocks.toastError).toHaveBeenCalledWith(expect.stringContaining('loop still active'))
    expect(wrapper.findAll('button').some(button => button.text() === '停止循环')).toBe(true)
    wrapper.unmount()
  })

  it('restores the backend connection instead of showing this browser saved selection', async () => {
    mocks.listUartPorts.mockResolvedValue([{ device: 'UART_BACKEND', description: '' }])
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ running: true,
      slave: 7, connection: { port: 'UART_BACKEND', baudrate: 57600, bytesize: 8, parity: 'E',
        stopbits: 2, timeout: 1, retries: 0, local_echo: false }, loop: { revision: 0, running: false } }))))
    const wrapper = mount(ModbusTab)
    await flushPromises()
    expect(wrapper.find('.connection-summary').text()).toContain('UART_BACKEND')
    expect(wrapper.find('.connection-summary').text()).toContain('57600')
    expect(wrapper.find('.connection-summary').text()).toContain('8E2')
    wrapper.unmount()
  })

  it.each(['start', 'stop'] as const)('ignores a late loop %s response after a newer SSE state', async action => {
    let stream: { onmessage?: (event: { data: string }) => void } = {}
    vi.stubGlobal('EventSource', class {
      constructor() { stream = this }
      close() {}
    })
    let respond!: (response: Response) => void
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (url.endsWith(`/loop/${action}`)) return new Promise<Response>(resolve => { respond = resolve })
      return Promise.resolve(new Response(JSON.stringify({ running: true,
        loop: { revision: 1, running: action === 'stop', completed: 0, errors: 0 } })))
    }))
    const wrapper = mount(ModbusTab)
    try {
      await flushPromises()
      await wrapper.findAll('button').find(button => button.text() === (action === 'start' ? '循环发送' : '停止循环'))!.trigger('click')
      stream.onmessage!({ data: JSON.stringify({ event: 'loop', revision: 3,
        running: action === 'stop', completed: 7, errors: 0 }) })
      await flushPromises()
      respond(new Response(JSON.stringify({ revision: 2, running: action === 'start', completed: 0, errors: 0 })))
      await flushPromises()
      expect(wrapper.findAll('button').some(button => button.text() === (action === 'start' ? '循环发送' : '停止循环'))).toBe(true)
      expect(wrapper.find('.loop-summary').text()).toContain('7')
    } finally {
      wrapper.unmount()
    }
  })

})
