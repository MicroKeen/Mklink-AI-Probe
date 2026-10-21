import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import HpmIspOtpPanel from './HpmIspOtpPanel.vue'

describe('UART OTP readout', () => {
  it('renders values and unknown states without a programming control', () => {
    const wrapper = mount(HpmIspOtpPanel, { props: { busy: false, disabled: false, error: '', snapshot: {
      part_number: 'HPM5301', chip_id: 0x11705142, hard_lock: 0, read_at: '2026-10-21T16:30:00+08:00', source: 'rom',
      words: [{ word: 69, current: 5, shadow: null, locked: null }, { word: 72, current: 1, shadow: 1, locked: true }],
    } } })
    expect(wrapper.text()).toContain('0x11705142')
    expect(wrapper.text()).toContain('0x00000005')
    expect(wrapper.findAll('tbody tr')[0].text()).toContain('未知')
    expect(wrapper.findAll('tbody tr')[0].text()).toContain('—')
    expect(wrapper.findAll('button')).toHaveLength(1)
    expect(wrapper.find('input, select').exists()).toBe(false)
  })

  it('blocks read while another operation owns the probe', async () => {
    const wrapper = mount(HpmIspOtpPanel, { props: { busy: false, disabled: true, error: '', snapshot: null } })
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('read')).toBeUndefined()
    await wrapper.setProps({ disabled: false })
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('read')).toHaveLength(1)
    await wrapper.setProps({ busy: true })
    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
  })
})
