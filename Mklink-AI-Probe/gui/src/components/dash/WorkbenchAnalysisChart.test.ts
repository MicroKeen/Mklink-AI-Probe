import { mount } from '@vue/test-utils'
import { afterEach, expect, it, vi } from 'vitest'
import WorkbenchAnalysisChart from './WorkbenchAnalysisChart.vue'
import { emptyContent } from '../../lib/workbenchActivity'
import { setTheme } from '../../composables/useTheme'
vi.mock('vue-echarts', () => ({ default: { name: 'VChart', props: ['option', 'autoresize', 'initOptions', 'updateOptions'], template: '<div class="test-chart" />' } }))
afterEach(() => setTheme('dark'))

it('keeps signed values, duplicate/full labels and safe tooltips while changing chart types', async () => {
  const content = { ...emptyContent(), title: 'Analysis', kind: 'bar', unit: 'V', points: [{ label: '<img src=x onerror=alert(1)>'.repeat(3), value: -2 }, { label: 'Same', value: 0 }, { label: 'Same', value: 4 }] }
  const wrapper = mount(WorkbenchAnalysisChart, { props: { content } })
  const chart = wrapper.getComponent({ name: 'VChart' })
  const option = () => chart.props('option')
  expect(option().series[0].data.map((point: any) => point.value)).toEqual([-2, 0, 4])
  expect(option().xAxis.data).toEqual(content.points.map(point => point.label))
  expect(option().tooltip.renderMode).toBe('richText')
  expect(option().tooltip.valueFormatter(-2, 0)).toBe('-2 V')
  expect(wrapper.find('img').exists()).toBe(false)
  expect(chart.attributes('aria-label')).toContain(content.points[0]!.label)
  await wrapper.setProps({ content: { ...content, kind: 'line' } })
  expect(option().series[0].type).toBe('line')
  expect(chart.props('updateOptions')).toEqual({ notMerge: true })
  const dark = option().yAxis.axisLabel.color
  setTheme('light'); await wrapper.vm.$nextTick()
  expect(option().yAxis.axisLabel.color).not.toBe(dark)
  wrapper.unmount()
})

it.each([1e308, 1e-308])('keeps finite extreme inputs renderable without losing original values (%s)', async value => {
  const content = { ...emptyContent(), kind: 'bar', points: [{ label: 'negative', value: -value }, { label: 'positive', value }] }
  const wrapper = mount(WorkbenchAnalysisChart, { props: { content } })
  const option = () => wrapper.getComponent({ name: 'VChart' }).props('option')
  expect(option().series[0].data.map((point: any) => point.value)).toEqual([-1, 1])
  expect(wrapper.text()).toContain('纵轴缩放')
  expect(option().tooltip.valueFormatter(1, 1).trim()).toBe(String(value))
  await wrapper.setProps({ content: { ...content, kind: 'pie', points: [{ label: 'A', value }, { label: 'B', value }] } })
  expect(option().series[0].data.map((point: any) => point.value)).toEqual([1, 1])
  expect(option().xAxis).toBeUndefined()
  expect(wrapper.text()).not.toContain('纵轴缩放')
  wrapper.unmount()
})

it('uses a bounded category slider for dense data and removes it for a small chart', async () => {
  const content = { ...emptyContent(), kind: 'line', points: Array.from({ length: 100 }, (_, i) => ({ label: 'Long channel label ' + i, value: i })) }
  const wrapper = mount(WorkbenchAnalysisChart, { props: { content } })
  const chart = wrapper.getComponent({ name: 'VChart' })
  expect(chart.props('option').dataZoom).toMatchObject([{ type: 'slider', start: 0, end: 100 }])
  expect(chart.props('option').series[0].data).toHaveLength(100)
  expect(chart.props('autoresize')).toEqual({ throttle: 100 })
  await wrapper.setProps({ content: { ...content, points: [{ label: 'Zero', value: 0 }] } })
  expect(chart.props('option').dataZoom).toEqual([])
  expect(chart.props('option').series[0].data[0].value).toBe(0)
  wrapper.unmount()
})
