import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import SerialPortPanel from './SerialPortPanel.vue'

const mocks = vi.hoisted(() => ({ streams: [] as any[], append: vi.fn(), clear: vi.fn() }))
vi.mock('../../composables/useBinaryStream', () => ({ useBinaryStream: (_name: string, options: any) => {
  const stream = { options, serialLines: ref(null), serialTerminal: ref(null), telemetry: ref(null), error: ref(null), start: vi.fn(), stop: vi.fn(), selectSerialPort: vi.fn() }
  mocks.streams.push(stream)
  return stream
} }))
vi.mock('./VirtualLogPanel.vue', () => ({ default: { template: '<div/>', setup: (_: unknown, { expose }: any) => { expose({ append: mocks.append, clear: mocks.clear, retainedCount: 0 }) } } }))
vi.mock('./RttTerminalPanel.vue', () => ({ default: { template: '<div/>', setup: (_: unknown, { expose }: any) => { expose({ write: vi.fn(), clear: vi.fn(), activate: vi.fn() }) } } }))
vi.mock('./RttTransmitBar.vue', () => ({ default: { props: ['enabled', 'idPrefix'], template: '<div/>' } }))

beforeEach(() => {
  mocks.streams.length = 0; mocks.append.mockClear(); mocks.clear.mockClear()
  vi.stubGlobal('localStorage', { getItem: () => null, setItem: vi.fn() })
})
afterEach(() => vi.unstubAllGlobals())

it('binds independent consumers to existing ports and restores views without starting hardware', async () => {
  const request = vi.fn(async (_url: string) => ({ ok: true, json: async () => ({ running: true, ports: { COM3: 'open', COM4: 'open' } }) }))
  vi.stubGlobal('fetch', request)
  const left = mount(SerialPortPanel, { props: { port: 'COM3', panelId: 'serial-left' } })
  const right = mount(SerialPortPanel, { props: { port: 'COM4', panelId: 'serial-right' } })
  await flushPromises()
  expect(mocks.streams[0].selectSerialPort).toHaveBeenCalledWith('COM3')
  expect(mocks.streams[2].selectSerialPort).toHaveBeenCalledWith('COM4')
  left.vm.restore({ mode: 'terminal', paused: true, format: 'hex' })
  expect(left.vm.read().view).toMatchObject({ mode: 'terminal', paused: true, format: 'hex' })
  expect(right.vm.read().view).toMatchObject({ mode: 'log', paused: false, format: 'text' })
  expect(request.mock.calls.every(([url]) => String(url).endsWith('/status'))).toBe(true)
  mocks.streams[2].serialLines.value = { port: 'COM3', session: 'session', lines: [{ direction: 'RX', timestampNs: 1n, ascii: 'wrong port', rawHex: '61' }] }
  await flushPromises()
  expect(mocks.append).not.toHaveBeenCalled()
  left.unmount(); right.unmount()
})

it('sends exactly once, surfaces uncertain failure, and refuses closed or YMODEM-owned ports', async () => {
  let mode = 'open'
  const request = vi.fn(async (url: string, _init?: RequestInit) => ({ ok: !url.endsWith('/send'), status: 502, json: async () => url.endsWith('/send')
    ? { detail: 'Write outcome unknown; no retry' }
    : { running: true, ports: { COM3: mode }, ymodem: { active: mode === 'ymodem', port: 'COM3' } } }))
  vi.stubGlobal('fetch', request)
  const wrapper = mount(SerialPortPanel, { props: { port: 'COM3' } })
  await flushPromises()
  await expect(wrapper.vm.execute('serial.send', { data: 'ping', lineEnding: '\n' })).rejects.toThrow('outcome unknown')
  const sends = request.mock.calls.filter(([url]) => url.endsWith('/send'))
  expect(sends).toHaveLength(1)
  expect(JSON.parse(String(sends[0][1]?.body))).toEqual({ port: 'COM3', data: '70696e670a', hex: true })
  mode = 'closed'; await wrapper.vm.execute('serial.refresh')
  await expect(wrapper.vm.execute('serial.send', { data: 'ping' })).rejects.toThrow('not writable')
  mode = 'ymodem'; await wrapper.vm.execute('serial.refresh')
  await expect(wrapper.vm.execute('serial.send', { data: 'ping' })).rejects.toThrow('not writable')
  expect(request.mock.calls.filter(([url]) => url.endsWith('/send'))).toHaveLength(1)
  wrapper.unmount()
})
