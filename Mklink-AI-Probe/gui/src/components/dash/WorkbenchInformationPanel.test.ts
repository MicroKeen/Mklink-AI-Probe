import { DOMWrapper, flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
vi.mock('./WorkbenchAnalysisChart.vue', () => ({ __esModule: true, default: { name: 'WorkbenchAnalysisChart', props: ['content'], template: '<div role="img" :aria-label="content.title" />' } }))
import WorkbenchInformationPanel from './WorkbenchInformationPanel.vue'
import WorkbenchLogPanel from './WorkbenchLogPanel.vue'
import { createWorkbenchActivity, emptyContent, workbenchActivityKey } from '../../lib/workbenchActivity'

describe('information, charts and conversation display', () => {
  it('shows the same Agent answer in logs and following information panels', async () => {
    const activity = createWorkbenchActivity()
    const global = { provide: { [workbenchActivityKey as symbol]: activity } }
    const info = mount(WorkbenchInformationPanel, { props: { panelId: 'info' }, global })
    const log = mount(WorkbenchLogPanel, { global })
    await log.vm.execute('log.append', { kind: 'answer', title: 'Capture analysis', text: 'Four requests were rejected; target restored.' })
    await flushPromises()
    expect(info.text()).toContain('Four requests were rejected')
    expect(log.get('[role=log]').text()).toContain('Four requests were rejected')
    await info.vm.execute('content.set', { ...emptyContent(), title: 'Pinned note', text: '<script>danger()</script>' })
    expect(info.find('script').exists()).toBe(false)
    expect(info.vm.read().following).toBe(false)
    expect(info.vm.read().content.text).toContain('<script>')
    info.unmount(); log.unmount()
  })
  it('edits real chart data with ordinary inputs and accepts the same data through the semantic action', async () => {
    const activity = createWorkbenchActivity()
    const info = mount(WorkbenchInformationPanel, { props: { panelId: 'chart', chart: true }, global: { provide: { [workbenchActivityKey as symbol]: activity } } })
    const data = { ...emptyContent(), title: 'Signed values', kind: 'bar', unit: 'V', points: [{ label: 'Low', value: -2 }, { label: 'High', value: 4 }] }
    await info.vm.execute('content.set', data); await flushPromises()
    expect(info.get('[role=img]').attributes('aria-label')).toContain('Signed values')
    expect(info.getComponent({ name: 'WorkbenchAnalysisChart' }).props('content')).toEqual(data)
    expect(info.get('details').text()).toContain('-2')
    await info.findAll('button').find(button => button.text() === '编辑内容')!.trigger('click')
    await new DOMWrapper(document.body.querySelector<HTMLInputElement>('.point-editor input[type=number]')!).setValue('3')
    await new DOMWrapper(document.body.querySelector<HTMLFormElement>('.content-editor')!).trigger('submit'); await flushPromises()
    expect(info.vm.read().content.points[0]?.value).toBe(3)
    await info.vm.execute('content.set', { ...data, kind: 'pie', points: [{ label: 'A', value: 2 }, { label: 'B', value: 4 }] }); await flushPromises()
    expect(info.getComponent({ name: 'WorkbenchAnalysisChart' }).props('content').kind).toBe('pie')
    await info.vm.execute('content.set', { ...data, kind: 'line' }); await flushPromises()
    expect(info.getComponent({ name: 'WorkbenchAnalysisChart' }).props('content').kind).toBe('line')
    expect(info.find('textarea').exists()).toBe(false)
    info.unmount()
  })
})
