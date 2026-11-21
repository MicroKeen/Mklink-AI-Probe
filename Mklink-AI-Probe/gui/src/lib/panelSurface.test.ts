import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, provide, ref } from 'vue'
import { expect, it } from 'vitest'
import { guiPanelScopeKey, useGuiPanel, useGuiId, createGuiAutomation } from './guiAutomation'
import { panelSurface } from './panelSurface'
import { createMemoryHistory, createRouter } from 'vue-router'

it('keeps same-channel replay and trace snapshots/actions separate and out of the original page registry', async () => {
  const Child = defineComponent({ setup() {
    const value = ref(0), id = useGuiId()
    useGuiPanel('rtt.replay.0', { snapshot: () => ({ cursor: value.value }), actions: { 'replay.next': () => { value.value++ } } })
    return () => h('label', { for: id('channel') }, [h('input', { id: id('channel') }), String(value.value)])
  } })
  const Host = defineComponent({ props: ['panelId'], setup(props, { expose }) {
    const root = ref<HTMLElement | null>(null), scope = { id: props.panelId, panels: new Map() }
    provide(guiPanelScopeKey, scope)
    expose(panelSurface(root, scope, ref(null)))
    return () => h('div', { ref: root }, [h(Child)])
  } })
  const first = mount(Host, { props: { panelId: 'first' }, attachTo: document.body })
  const second = mount(Host, { props: { panelId: 'second' }, attachTo: document.body })
  await flushPromises()
  const field = (await (first.vm as any).execute('view.controls', {})).controls[0]
  const updated = await (first.vm as any).execute('view.control.set', { control_id: field.id, value: 'test' })
  expect(updated.operation).toBe(field.label)
  const revisionState = (first.vm as any).read()
  await (first.vm as any).execute('view.action', { name: 'replay.next' })
  expect((first.vm as any).read()).toEqual(revisionState)
  expect((await (first.vm as any).execute('view.read', {})).states['rtt.replay.0'].cursor).toBe(1)
  expect((await (second.vm as any).execute('view.read', {})).states['rtt.replay.0'].cursor).toBe(0)
  expect(first.get('label').attributes('for')).toBe(first.get('input').attributes('id'))
  expect(first.get('input').attributes('id')).not.toBe(second.get('input').attributes('id'))
  const global = createGuiAutomation(createRouter({ history: createMemoryHistory(), routes: [] }), () => ({}))
  expect(global.snapshot().panels).not.toHaveProperty('rtt.replay.0')
  first.unmount()
  await (second.vm as any).execute('view.action', { name: 'replay.next' })
  expect((await (second.vm as any).execute('view.read', {})).states['rtt.replay.0'].cursor).toBe(1)
  second.unmount()
})
