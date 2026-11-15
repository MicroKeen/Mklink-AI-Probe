import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import FirmwareCompatibilityBanner from './FirmwareCompatibilityBanner.vue'
import { setLanguage } from '../composables/useLanguage'

const compatibility = { checked: true, version: 'V4.7.3', warnings: [{
  code: 'firmware_upgrade_required', feature: 'Live writes', feature_zh: '采集中写入',
  required: 'MUX_TARGET=1', message: 'upgrade', action: 'upgrade_probe_firmware',
}] }

describe('firmware capability guidance', () => {
  it('is absent when capabilities are supported or unknown', () => {
    for (const value of [undefined, { ...compatibility, warnings: [] }]) {
      const wrapper = mount(FirmwareCompatibilityBanner, { props: { compatibility: value } })
      expect(wrapper.find('aside').exists()).toBe(false)
      wrapper.unmount()
    }
  })
  it('shows affected features and opens the firmware page only on request', async () => {
    setLanguage('zh')
    const wrapper = mount(FirmwareCompatibilityBanner, { props: { compatibility } })
    expect(wrapper.text()).toContain('采集中写入')
    expect(wrapper.emitted()).toEqual({})
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('openFirmware')).toHaveLength(1)
    setLanguage('en')
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Live writes')
    wrapper.unmount()
    setLanguage('zh')
  })
  it('directs remote clients to the site operator', () => {
    const wrapper = mount(FirmwareCompatibilityBanner, { props: { compatibility, remote: true } })
    expect(wrapper.find('button').exists()).toBe(false)
    expect(wrapper.text()).toContain('现场用户')
  })
})
