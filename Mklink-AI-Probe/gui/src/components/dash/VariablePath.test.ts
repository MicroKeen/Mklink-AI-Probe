import { mount } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'
import VariablePath from './VariablePath.vue'

describe('VariablePath', () => {
  it('keeps the full path in one row without an expander', () => {
    vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
    const path = 'app_motor_instances[0].runtime.control.reference.iq_ref_a'
    const wrapper = mount(VariablePath, { props: { path } })
    expect(wrapper.text()).toBe(path)
    expect(wrapper.attributes('title')).toBe(path)
    expect(wrapper.find('details').exists()).toBe(false)
    wrapper.unmount()
    vi.unstubAllGlobals()
  })
  it('drags overflowing text and releases capture without affecting adjacent controls', async () => {
    vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
    const wrapper = mount(VariablePath, { props: { path: 'long.variable.member' } })
    const el = wrapper.element as HTMLElement
    Object.defineProperties(el, { scrollWidth: { value: 500 }, clientWidth: { value: 160 } })
    el.setPointerCapture = vi.fn()
    el.hasPointerCapture = vi.fn(() => true)
    el.releasePointerCapture = vi.fn()
    await wrapper.trigger('pointerdown', { button: 0, pointerId: 1, clientX: 150 })
    await wrapper.trigger('pointermove', { pointerId: 1, clientX: 50 })
    expect(el.scrollLeft).toBe(100)
    await wrapper.trigger('pointerup', { pointerId: 1 })
    expect(el.releasePointerCapture).toHaveBeenCalledWith(1)
    await wrapper.trigger('pointermove', { pointerId: 1, clientX: 0 })
    expect(el.scrollLeft).toBe(100)
    await wrapper.setProps({ path: 'short' })
    expect(el.scrollLeft).toBe(0)
    wrapper.unmount()
    vi.unstubAllGlobals()
  })
})
