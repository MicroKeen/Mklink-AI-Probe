import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import HpmIspOtpPanel from './HpmIspOtpPanel.vue'

describe('UART OTP settings', () => {
  it('renders unknown states and allows a preflight, but no write without a prepared plan', async () => {
    const wrapper = mount(HpmIspOtpPanel, { props: { plan: null, result: '', busy: false, disabled: false, error: '', snapshot: {
      part_number: 'HPM5301', chip_id: 0x11705142, hard_lock: 0, read_at: '2026-10-21T16:30:00+08:00', source: 'rom',
      words: [{ word: 69, current: 5, shadow: null, locked: null }, { word: 72, current: 1, shadow: 1, locked: true }],
    } } })
    expect(wrapper.text()).toContain('0x11705142')
    expect(wrapper.text()).toContain('0x00000005')
    expect(wrapper.findAll('tbody tr')[0].text()).toContain('未知')
    expect(wrapper.findAll('tbody tr')[0].text()).toContain('—')
    expect(wrapper.find('[data-testid="isp-otp-program"]').exists()).toBe(false)
    await wrapper.get('[aria-label="UART OTP desired value"]').setValue('0x7')
    await wrapper.get('[data-testid="isp-otp-plan"]').trigger('click')
    expect(wrapper.emitted('prepare')).toEqual([[{ word: 69, expected: 5, desired: '0x7' }]])
    expect(wrapper.emitted('program')).toBeUndefined()
    await wrapper.get('[aria-label="UART OTP word"]').setValue(72)
    expect(wrapper.get('[data-testid="isp-otp-plan"]').attributes('disabled')).toBeDefined()
  })

  it('blocks read while another operation owns the probe', async () => {
    const wrapper = mount(HpmIspOtpPanel, { props: { plan: null, result: '', busy: false, disabled: true, error: '', snapshot: null } })
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('read')).toBeUndefined()
    await wrapper.setProps({ disabled: false })
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('read')).toHaveLength(1)
    await wrapper.setProps({ busy: true })
    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
  })

  it('requires a new confirmation after a plan changes and consumes confirmation on submit', async () => {
    const plan = { plan_id: 'one', word: 69, expected: 5, desired: 7, delta: 2, expires_in: 60, qualified: true, write_supported: true, before: 5, reason: null }
    const wrapper = mount(HpmIspOtpPanel, { props: { plan, result: '', busy: false, disabled: false, error: '', snapshot: null } })
    await wrapper.get('[data-testid="isp-otp-program"]').trigger('click')
    expect(wrapper.emitted('program')).toBeUndefined()
    await wrapper.get('[data-testid="isp-otp-confirm"]').setValue(true)
    await wrapper.setProps({ plan: { ...plan, plan_id: 'two', desired: 15, delta: 10 } })
    expect(wrapper.get('[data-testid="isp-otp-program"]').attributes('disabled')).toBeDefined()
    await wrapper.get('[data-testid="isp-otp-confirm"]').setValue(true)
    await wrapper.get('[data-testid="isp-otp-program"]').trigger('click')
    expect(wrapper.emitted('program')).toEqual([['two']])
    expect(wrapper.get('[data-testid="isp-otp-program"]').attributes('disabled')).toBeDefined()
  })

  it('shows an unqualified preflight without any write confirmation or button', () => {
    const wrapper = mount(HpmIspOtpPanel, { props: { busy: false, disabled: false, snapshot: null, error: '', result: '', plan: {
      plan_id: null, word: 69, expected: 0, desired: 1, delta: 1, expires_in: 0,
      qualified: false, write_supported: false, before: 0, reason: 'read_semantics_and_locks_unknown',
    } } })
    expect(wrapper.get('[data-testid="isp-otp-unavailable"]').text()).toContain('暂不支持')
    expect(wrapper.find('[data-testid="isp-otp-confirm"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="isp-otp-program"]').exists()).toBe(false)
  })
})
