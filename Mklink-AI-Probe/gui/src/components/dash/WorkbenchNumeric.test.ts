import { mount } from '@vue/test-utils'
import { afterEach, expect, it, vi } from 'vitest'
import WorkbenchNumeric from './WorkbenchNumeric.vue'
import { createNumericSamples, numericStatus, type NumericReading } from '../../lib/numericValue'
import { createControl, validateControl } from '../../lib/workbenchControls'

afterEach(() => vi.useRealTimers())
function fixture() {
  const source = createNumericSamples()
  const widget = createControl([], 'numeric', '温度')
  widget.options = { unit: '°C', precision: 2, stale_ms: 2000, valid_path: 'signal:sensor.valid', note: '测试探头' }
  const read = (connected = true, replay = false): NumericReading => {
    const values = source.read(['sensor.temperature', 'sensor.valid'], connected, replay)
    return { sample: values['signal:sensor.temperature']!, validity: values['signal:sensor.valid']! }
  }
  return { source, widget, read }
}
it('formats zero and negative numbers and masks invalid, disconnected, replay and stale values', async () => {
  vi.useFakeTimers(); vi.setSystemTime(10000)
  const { source, widget, read } = fixture()
  source.accept(1n, { 'sensor.temperature': 0, 'sensor.valid': 1 })
  const wrapper = mount(WorkbenchNumeric, { props: { widget, value: read() } })
  expect(wrapper.get('output').text()).toBe('0.00')
  expect(wrapper.text()).toContain('°C')
  source.accept(2n, { 'sensor.temperature': -12.345, 'sensor.valid': 1 })
  await wrapper.setProps({ value: read() }); expect(wrapper.get('output').text()).toBe('-12.35')
  await wrapper.setProps({ value: read(false) }); expect(wrapper.text()).toContain('已断开')
  expect(wrapper.get('output').classes()).toContain('is-unavailable')
  await wrapper.setProps({ value: read(true, true) }); expect(wrapper.text()).toContain('回放中')
  source.accept(3n, { 'sensor.temperature': 99, 'sensor.valid': 0 })
  await wrapper.setProps({ value: read() }); expect(wrapper.text()).toContain('信号无效')
  source.accept(4n, { 'sensor.temperature': NaN, 'sensor.valid': 1 })
  await wrapper.setProps({ value: read() }); expect(wrapper.text()).toContain('数值无效')
  source.accept(5n, { 'sensor.temperature': 10, 'sensor.valid': 1 })
  await wrapper.setProps({ value: read() })
  await vi.advanceTimersByTimeAsync(2000); expect(wrapper.text()).toContain('已过期')
  const timers = vi.getTimerCount()
  wrapper.unmount(); expect(vi.getTimerCount()).toBe(timers - 1)
})
it('constant new samples stay fresh; duplicate, older and merely reread samples do not', () => {
  const { source, widget, read } = fixture()
  source.accept(1n, { 'sensor.temperature': 5, 'sensor.valid': 1 }, 1000)
  source.accept(2n, { 'sensor.temperature': 5, 'sensor.valid': 1 }, 2500)
  expect(numericStatus(read(), widget.options!, 4000)).toBe('')
  source.accept(2n, { 'sensor.temperature': 8, 'sensor.valid': 1 }, 4000)
  source.accept(1n, { 'sensor.temperature': 8, 'sensor.valid': 1 }, 4400)
  expect(read().sample.value).toBe(5)
  expect(numericStatus(read(), widget.options!, 4500)).toContain('过期')
  const old = read().validity
  source.reset(); expect(numericStatus(read(), widget.options!, 4600)).toContain('等待采样')
  source.accept(1n, { 'sensor.temperature': 5, 'sensor.valid': 1 }, 4700)
  expect(numericStatus({ ...read(), validity: old }, widget.options!, 4700)).toContain('信号无效')
  expect(numericStatus(read(), widget.options!, 4700)).toBe('')
})
it.each([{ precision: 7 }, { precision: true }, { stale_ms: 0 }, { stale_ms: 60001 }, { unit: 'x'.repeat(33) }, { note: 'x'.repeat(201) }, { valid_path: 'a.__proto__.value' }, { script: 'run()' }])('rejects unsafe numeric options %j', options => {
  expect(() => validateControl({ ...createControl([], 'numeric', 'Value'), options } as any)).toThrow()
})
it('keeps existing component schemas strict', () => {
  expect(() => validateControl({ ...createControl([], 'value', 'Value'), options: {} })).toThrow()
})
