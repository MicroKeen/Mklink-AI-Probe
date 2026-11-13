import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import FirmwareUpdatePrompt from './FirmwareUpdatePrompt.vue'
import { setLanguage } from '../composables/useLanguage'
import type { FirmwareUpdateNotice } from '../types/mklink'

const notice: FirmwareUpdateNotice = { status: 'available', family: 'microlink', model: 'V4',
  current_version: 'V4.7.3', latest_version: 'V4.7.4', probe_id: 'fixture', device_generation: 1 }

describe('deferred firmware prompt', () => {
  beforeEach(() => { sessionStorage.clear(); setLanguage('zh') })

  it.each(['unknown', 'checking', 'current', 'unavailable', 'no_firmware'] as const)('keeps %s quiet', status => {
    const wrapper = mount(FirmwareUpdatePrompt, { props: { notice: { ...notice, status } } })
    expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
    expect(wrapper.emitted()).toEqual({})
    wrapper.unmount()
  })

  it('shows versions in both languages and only requests navigation on accept', async () => {
    const wrapper = mount(FirmwareUpdatePrompt, { props: { notice } })
    expect(wrapper.text()).toContain('发现新固件')
    expect(wrapper.text()).toContain('MicroLink V4')
    expect(wrapper.text()).toContain('V4.7.3')
    expect(wrapper.text()).toContain('V4.7.4')
    expect(wrapper.emitted('openFirmware')).toBeUndefined()
    setLanguage('en')
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('New Probe Firmware')
    expect(wrapper.get('[data-testid="confirmation-cancel"]').text()).toBe('Later')
    expect(wrapper.get('[data-testid="confirmation-accept"]').text()).toBe('Open Firmware Update')
    await wrapper.get('[data-testid="confirmation-accept"]').trigger('click')
    expect(wrapper.emitted('openFirmware')).toHaveLength(1)
    expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('recommends upgrade for unrecognized legacy replies without inventing a cloud version', async () => {
    const wrapper = mount(FirmwareUpdatePrompt, { props: { notice: { status: 'unrecognized', probe_id: 'legacy' } } })
    expect(wrapper.text()).toContain('建议升级固件')
    expect(wrapper.text()).toContain('按下载器型号')
    expect(wrapper.text()).not.toContain('云端版本')
    expect(wrapper.text()).not.toContain('undefined')
    await wrapper.get('[data-testid="confirmation-accept"]').trigger('click')
    expect(wrapper.emitted('openFirmware')).toHaveLength(1)
    wrapper.unmount()
  })

  it('deduplicates polling, reconnect and page reload but permits a new version or probe', async () => {
    let wrapper = mount(FirmwareUpdatePrompt, { props: { notice } })
    await wrapper.get('[data-testid="confirmation-cancel"]').trigger('click')
    expect(wrapper.emitted('openFirmware')).toBeUndefined()
    await wrapper.setProps({ notice: null })
    await wrapper.setProps({ notice: { ...notice, device_generation: 2 } })
    expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
    wrapper.unmount()
    wrapper = mount(FirmwareUpdatePrompt, { props: { notice: { ...notice } } })
    expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
    await wrapper.setProps({ notice: { ...notice, latest_version: 'V4.7.5' } })
    expect(wrapper.find('[role="alertdialog"]').exists()).toBe(true)
    await wrapper.get('[data-testid="confirmation-cancel"]').trigger('click')
    await wrapper.setProps({ notice: { ...notice, probe_id: 'another' } })
    expect(wrapper.find('[role="alertdialog"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('clears stale results on disconnect or replacement and does not prompt on the firmware page', async () => {
    const wrapper = mount(FirmwareUpdatePrompt, { props: { notice } })
    await wrapper.setProps({ notice: null })
    expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
    await wrapper.setProps({ notice: { ...notice, status: 'checking' } })
    expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
    await wrapper.setProps({ notice: { ...notice, family: 'hpmlink', probe_id: 'hpm' } })
    expect(wrapper.text()).toContain('HPMLink V4')
    await wrapper.setProps({ onFirmwarePage: true })
    expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
    await wrapper.setProps({ onFirmwarePage: false })
    expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('supports Escape and remembers Later even when storage is unavailable', async () => {
    const get = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw Error('disabled') })
    const set = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw Error('disabled') })
    const wrapper = mount(FirmwareUpdatePrompt, { props: { notice } })
    try {
      await wrapper.get('[role="alertdialog"]').trigger('keydown', { key: 'Escape' })
      await wrapper.setProps({ notice: null })
      await wrapper.setProps({ notice: { ...notice } })
      expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
      expect(wrapper.emitted('openFirmware')).toBeUndefined()
    } finally { wrapper.unmount(); get.mockRestore(); set.mockRestore() }
  })
})
