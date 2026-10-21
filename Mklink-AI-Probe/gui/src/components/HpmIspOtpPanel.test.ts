import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import HpmIspOtpPanel from './HpmIspOtpPanel.vue'
const snapshot = { part_number: 'HPM5301', chip_id: 0x11705142, hard_lock: 0, read_at: 'now', source: 'rom',
  words: [{ word: 69, current: 5, shadow: null, locked: null }, { word: 70, current: 0, shadow: null, locked: null }, { word: 72, current: 1, shadow: 1, locked: true }] }
const props = { plan: null, result: '', busy: false, disabled: false, error: '', snapshot }
async function setup(extra = {}) {
  const wrapper = mount(HpmIspOtpPanel, { props: { ...props, ...extra }, global: { stubs: { teleport: true } } })
  await wrapper.get('[data-testid=isp-otp-open]').trigger('click'); await flushPromises()
  return wrapper
}
async function add(wrapper: Awaited<ReturnType<typeof setup>>, word = 69, count = 2, value = '00000007,00000001') {
  await wrapper.get('[data-testid=isp-otp-write-view]').trigger('click')
  await wrapper.get('[data-testid=isp-otp-add]').trigger('click')
  await wrapper.get('[aria-label="OTP start word"]').setValue(word)
  await wrapper.get('[aria-label="OTP word count"]').setValue(count)
  await wrapper.get('[aria-label="OTP word values"]').setValue(value)
  await wrapper.get('form').trigger('submit')
}
describe('UART OTP manufacturing-tool layout', () => {
  it('shows indexed grids and unknown locks without fabricating unavailable words', async () => {
    const wrapper = await setup()
    expect(wrapper.text()).toContain('OTP Readable Words')
    expect(wrapper.get('[aria-label="Word 69"]').attributes('title')).toContain('锁定: 未知')
    expect(wrapper.find('[aria-label="Word 68"]').exists()).toBe(false)
    await wrapper.get('[aria-label="OTP columns"]').setValue('8')
    expect(wrapper.findAll('.otp-grid thead th')).toHaveLength(9)
    expect(wrapper.emitted('read')).toBeUndefined()
    wrapper.unmount()
  })
  it('opens with a read and prevents reads while the probe is occupied', async () => {
    const wrapper = await setup({ snapshot: null, disabled: true })
    expect(wrapper.emitted('read')).toBeUndefined()
    expect(wrapper.get('[data-testid=isp-otp-read]').attributes('disabled')).toBeDefined()
    await wrapper.setProps({ disabled: false })
    await wrapper.get('[data-testid=isp-otp-read]').trigger('click')
    expect(wrapper.emitted('read')).toHaveLength(1)
    wrapper.unmount()
  })
  it('prepares every changed word from the current snapshot', async () => {
    const wrapper = await setup(); await add(wrapper)
    await wrapper.get('[data-testid=isp-otp-plan]').trigger('click')
    expect(wrapper.emitted('prepare')).toEqual([[[{ word: 69, expected: 5, desired: '0x00000007' }, { word: 70, expected: 0, desired: '0x00000001' }]]])
    expect(wrapper.emitted('program')).toBeUndefined()
    await add(wrapper, 69, 1, '00000001')
    expect(wrapper.get('[data-testid=isp-otp-plan]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })
  it('blocks locked words, invalid ranges and missing snapshots', async () => {
    const wrapper = await setup(); await add(wrapper, 72, 1, '00000003')
    expect(wrapper.get('[data-testid=isp-otp-plan]').attributes('disabled')).toBeDefined()
    await add(wrapper, 79, 2, '00000001,00000002')
    expect(wrapper.get('[role=alert]').text()).toContain('69–79')
    await wrapper.setProps({ snapshot: null })
    expect(wrapper.get('[data-testid=isp-otp-plan]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })
  it('requires confirmation of differences, clears it on new plans, and drops submitted drafts', async () => {
    const wrapper = await setup(); await add(wrapper)
    const plan = { plan_id: 'one', qualified: true, write_supported: true, expires_in: 60,
      changes: [{ plan_id: null, word: 69, expected: 5, desired: 7, delta: 2, qualified: true, write_supported: true, expires_in: 0, before: 5, reason: null }] }
    await wrapper.setProps({ plan })
    await wrapper.get('[data-testid=isp-otp-program]').trigger('click')
    expect(wrapper.emitted('program')).toBeUndefined()
    await wrapper.get('[data-testid=isp-otp-confirm]').setValue(true)
    await wrapper.setProps({ plan: { ...plan, plan_id: 'two' } })
    expect(wrapper.get('[data-testid=isp-otp-program]').attributes('disabled')).toBeDefined()
    await wrapper.get('[data-testid=isp-otp-confirm]').setValue(true)
    await wrapper.get('[data-testid=isp-otp-program]').trigger('click')
    expect(wrapper.emitted('program')).toEqual([['two']])
    expect(wrapper.get('[data-testid=isp-otp-remove-all]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid=isp-otp-program]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })
})
