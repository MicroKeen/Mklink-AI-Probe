import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AppUpdateBanner from './AppUpdateBanner.vue'

describe('AppUpdateBanner', () => {
  it('offers only restart after an installed update could not relaunch', async () => {
    const wrapper = mount(AppUpdateBanner, { props: {
      state: 'restart-required', version: '0.5.0', progress: 1, error: '请重启',
    } })
    expect(wrapper.get('[data-testid="install-update"]').text()).toContain('重新启动')
    expect(wrapper.find('[data-testid="later-update"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="retry-update"]').exists()).toBe(false)
    await wrapper.get('[data-testid="install-update"]').trigger('click')
    expect(wrapper.emitted('install')).toHaveLength(1)
    wrapper.unmount()
  })
  it('prioritizes the client update and disables installation while firmware is being written', async () => {
    const wrapper = mount(AppUpdateBanner, {
      props: { state: 'ready', version: '0.5.0', progress: 1, error: '', firmwarePending: true },
    })
    expect(wrapper.text()).toContain('先更新上位机')
    await wrapper.setProps({ firmwareBusy: true })
    expect(wrapper.get('[data-testid="install-update"]').attributes('disabled')).toBeDefined()
    await wrapper.get('[data-testid="install-update"]').trigger('click')
    expect(wrapper.emitted('install')).toBeUndefined()
    expect(wrapper.text()).toContain('固件升级处理中')
    wrapper.unmount()
  })
  it('presents an unavailable platform as information with no install action', async () => {
    const wrapper = mount(AppUpdateBanner, {
      props: { state: 'unavailable', version: '', progress: null, error: '' },
    })
    expect(wrapper.text()).toContain('当前平台暂无可用更新')
    expect(wrapper.get('[data-testid="update-banner"]').attributes('role')).toBe('status')
    expect(wrapper.find('[data-testid="install-update"]').exists()).toBe(false)
    await wrapper.get('[data-testid="retry-update"]').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })
  it('shows background download progress without blocking the application', () => {
    const wrapper = mount(AppUpdateBanner, {
      props: { state: 'downloading', version: '0.2.0', progress: 0.42, error: '' },
    })

    expect(wrapper.get('[data-testid="update-banner"]').text()).toContain('正在下载 v0.2.0')
    expect(wrapper.get('progress').attributes('value')).toBe('0.42')
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it('offers installation only after the update is ready', async () => {
    const wrapper = mount(AppUpdateBanner, {
      props: { state: 'ready', version: '0.2.0', progress: 1, error: '' },
    })

    await wrapper.get('[data-testid="install-update"]').trigger('click')
    expect(wrapper.emitted('install')).toHaveLength(1)
    await wrapper.get('[data-testid="later-update"]').trigger('click')
    expect(wrapper.emitted('dismiss')).toHaveLength(1)
  })

  it('offers retry after an update error', async () => {
    const wrapper = mount(AppUpdateBanner, {
      props: { state: 'error', version: '', progress: null, error: 'network unavailable' },
    })

    expect(wrapper.text()).toContain('network unavailable')
    await wrapper.get('[data-testid="retry-update"]').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })
})
