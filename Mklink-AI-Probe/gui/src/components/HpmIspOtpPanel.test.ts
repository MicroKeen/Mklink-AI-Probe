import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import HpmIspOtpPanel from './HpmIspOtpPanel.vue'
const snapshot = { part_number: 'HPM5301', chip_id: 0x11705142, hard_lock: 0, read_at: 'now', source: 'rom',
  words: [{ word: 69, current: 5, shadow: null, locked: null }, { word: 70, current: 0, shadow: null, locked: null }, { word: 72, current: 1, shadow: 1, locked: true }] }
const props = { plan: null, result: '', busy: false, disabled: false, error: '', snapshot }
async function setup(extra = {}) {
  const wrapper = mount(HpmIspOtpPanel, { props: { ...props, ...extra }, global: { stubs: { teleport: true } } })
  await flushPromises()
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
  it.each(['HPM5301', 'HPM6280', 'HPM6360', 'HPM6450', 'HPM6750', 'HPM6880', 'HPM6E80', 'HPM6P81', 'HPM5E31'])('allows all 128 deployment words for %s', async partNumber => {
    const wrapper = await setup({ deployment: true, partNumber,
      snapshot: { ...snapshot, part_number: partNumber, chip_id: 0xFFFFFFFF, capability: 'profile_v1', rom_version: 0, soc_revision: 0,
        words: Array.from({ length: 128 }, (_, word) => ({ word, current: 0, shadow: null, locked: null })) } })
    await add(wrapper, 0, 128, Array(128).fill('00000001').join(','))
    await wrapper.get('[data-testid=isp-otp-deploy-confirm]').setValue(true)
    const config = wrapper.emitted('configuration')!.at(-1)![0] as { words: { word: number }[] }
    expect(config.words).toHaveLength(128)
    expect(config.words.some(item => item.word === 64)).toBe(true)
    wrapper.unmount()
  })
  it('preserves confirmed deployment across tabs but invalidates it after editing or refreshing', async () => {
    const wrapper = await setup({ deployment: true, active: true,
      snapshot: { ...snapshot, capability: 'profile_v1', rom_version: 1, soc_revision: 2 } })
    await add(wrapper, 69, 1, '00000007')
    await wrapper.get('[data-testid=isp-otp-deploy-confirm]').setValue(true)
    expect(wrapper.emitted('configuration')!.at(-1)![0]).toMatchObject({ words: [{ word: 69, expected: 5, desired: 7 }] })
    await wrapper.setProps({ active: false })
    await wrapper.setProps({ active: true })
    expect(wrapper.get<HTMLInputElement>('[data-testid=isp-otp-deploy-confirm]').element.checked).toBe(true)
    await wrapper.get('[data-testid=isp-otp-add]').trigger('click')
    expect(wrapper.emitted('configuration')!.at(-1)![0]).toBeUndefined()
    await wrapper.setProps({ snapshot: null })
    expect(wrapper.emitted('configuration')!.at(-1)![0]).toBeUndefined()
    expect(wrapper.find('[data-testid=isp-otp-program]').exists()).toBe(false)
    wrapper.unmount()
  })
  it('shows indexed grids and unknown locks without fabricating unavailable words', async () => {
    const wrapper = await setup()
    expect(wrapper.text()).toContain('OTP Readable Words')
    expect(wrapper.get('[aria-label="Word 69"]').attributes('title')).toContain('锁定: 未知')
    expect(wrapper.get('[aria-label="Word 68"]').text()).toBe('—')
    expect(wrapper.get('[aria-label="Word 1"]').attributes('class')).toContain('SECURE')
    await wrapper.get('[aria-label="OTP columns"]').setValue('8')
    expect(wrapper.findAll('.otp-grid thead th')).toHaveLength(9)
    expect(wrapper.emitted('read')).toBeUndefined()
    wrapper.unmount()
  })
  it('loads with a read and prevents reads while the probe is occupied', async () => {
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
    await add(wrapper, 127, 2, '00000001,00000002')
    expect(wrapper.get('[role=alert]').text()).toContain('0–127')
    await wrapper.setProps({ snapshot: null })
    expect(wrapper.get('[data-testid=isp-otp-plan]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })
  it('keeps drafts across workspace tabs but invalidates confirmation and never reads while hidden', async () => {
    const wrapper = await setup({ active: false, snapshot: null })
    expect(wrapper.emitted('read')).toBeUndefined()
    await wrapper.setProps({ active: true }); expect(wrapper.emitted('read')).toHaveLength(1)
    await wrapper.setProps({ snapshot }); await add(wrapper)
    await wrapper.setProps({ active: false })
    expect(wrapper.emitted('invalidate')).toBeDefined()
    await wrapper.setProps({ active: true })
    expect(wrapper.get('[aria-label="Word 69"]').text()).toBe('0x00000007')
    expect(wrapper.emitted('read')).toHaveLength(1)
    wrapper.unmount()
  })
  it('loads family-specific fields and can prepare non-user words only from real snapshot values', async () => {
    const wrapper = await setup({ partNumber: 'HPM6750', snapshot: { ...snapshot, part_number: 'HPM6750', words: [{ word: 24, current: 0x10000, shadow: null, locked: null }] } })
    await wrapper.get('[data-testid=isp-otp-write-view]').trigger('click')
    await wrapper.get('[data-testid=otp-template-toggle]').trigger('click')
    expect(wrapper.get('[aria-label="OTP key template"]').text()).toContain('EXIP1_KEK')
    await wrapper.get('input[type=checkbox][value="24:XPI_FREQ_OPTION"]').setValue(true)
    await wrapper.get('[aria-label="24:XPI_FREQ_OPTION"]').setValue('3')
    await wrapper.get('[data-testid=otp-template-add]').trigger('click')
    await wrapper.get('[data-testid=isp-otp-plan]').trigger('click')
    expect(wrapper.emitted('prepare')).toEqual([[[{ word: 24, expected: 0x10000, desired: '0x00010003' }]]])
    await wrapper.setProps({ snapshot: { ...snapshot, words: [{ word: 24, current: null, shadow: null, locked: null }] } })
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
