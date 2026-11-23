import { mount } from '@vue/test-utils'
import { afterEach, expect, it, vi } from 'vitest'
import WorkbenchMeter from './WorkbenchMeter.vue'
import { createNumericSamples } from '../../lib/numericValue'
import { createControl, validateControl } from '../../lib/workbenchControls'
import { setTheme } from '../../composables/useTheme'

vi.mock('vue-echarts', () => ({ default: { name: 'VChart', props: ['option', 'autoresize', 'initOptions', 'updateOptions'], template: '<div class="test-chart" />' } }))
afterEach(() => { vi.useRealTimers(); setTheme('dark') })

it.each(['gauge', 'bar-meter'])('%s shares sample validity, freshness and lifecycle with numeric values', async type => {
  vi.useFakeTimers(); vi.setSystemTime(10000)
  const widget = createControl([], type, 'Pressure')
  widget.options = { min: -10, max: 10, unit: 'kPa', precision: 1, valid_path: 'signal:valid', stale_ms: 1000 }
  const source = createNumericSamples()
  const read = (connected = true, replay = false) => {
    const values = source.read(['value', 'valid'], connected, replay)
    return { sample: values['signal:value']!, validity: values['signal:valid']! }
  }
  source.accept(1n, { value: -5, valid: 1 })
  const wrapper = mount(WorkbenchMeter, { props: { widget, value: read() } })
  const chart = () => wrapper.getComponent({ name: 'VChart' })
  const plotted = () => { const value = chart().props('option').series[0].data[0]; return typeof value === 'number' ? value : value.value }
  expect(plotted()).toBe(-5)
  expect(chart().props('autoresize')).toEqual({ throttle: 100 })
  expect(chart().props('initOptions')).toEqual({ renderer: 'svg' })
  expect(wrapper.get('output').text()).toBe('-5.0')
  source.accept(2n, { value: 25, valid: 1 }); await wrapper.setProps({ value: read() })
  expect(plotted()).toBe(10)
  expect(wrapper.get('output').text()).toBe('25.0')
  expect(wrapper.text()).toContain('超出量程')
  const darkColor = chart().props('option').series[0].itemStyle.color
  setTheme('light'); await wrapper.vm.$nextTick()
  expect(chart().props('option').series[0].itemStyle.color).not.toBe(darkColor)
  source.accept(3n, { value: 0, valid: 1 }); await wrapper.setProps({ value: read() })
  expect(plotted()).toBe(0); expect(wrapper.text()).not.toContain('超出量程')
  for (const value of [read(false), read(true, true)]) {
    await wrapper.setProps({ value }); expect(wrapper.find('.test-chart').exists()).toBe(false)
  }
  source.accept(4n, { value: 0, valid: 0 }); await wrapper.setProps({ value: read() })
  expect(wrapper.text()).toContain('信号无效'); expect(wrapper.find('.test-chart').exists()).toBe(false)
  source.accept(5n, { value: 0, valid: 1 }); await wrapper.setProps({ value: read() })
  await vi.advanceTimersByTimeAsync(750)
  source.accept(6n, { value: 0, valid: 1 }); await wrapper.setProps({ value: read() })
  await vi.advanceTimersByTimeAsync(750); expect(plotted()).toBe(0)
  await vi.advanceTimersByTimeAsync(250); expect(wrapper.find('.test-chart').exists()).toBe(false)
  expect(wrapper.text()).toContain('过期')
  const timers = vi.getTimerCount()
  wrapper.unmount(); expect(vi.getTimerCount()).toBe(timers - 1)
})

it.each(['gauge', 'bar-meter'])('%s validates ranges at the configuration boundary', type => {
  const widget = createControl([], type, 'Range')
  for (const options of [{ min: 1, max: 1 }, { min: 2, max: 1 }, { min: true }, { max: Infinity }, { min: NaN }, { min: -1e13 }, { script: 'run()' }]) {
    expect(() => validateControl({ ...widget, options } as any)).toThrow()
  }
  expect(validateControl({ ...widget, options: { min: -10, max: 0 } }).options).toEqual({ min: -10, max: 0 })
  expect(() => validateControl({ ...createControl([], 'numeric', 'Number'), options: { min: 0 } })).toThrow()
})
