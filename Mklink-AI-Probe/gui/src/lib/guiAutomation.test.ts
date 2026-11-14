import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { mount } from '@vue/test-utils'
import { createGuiAutomation, useGuiPanel } from './guiAutomation'

describe('semantic GUI control', () => {
  it('navigates all local pages and reads actual state without starting hardware', async () => {
    const router = createRouter({ history: createMemoryHistory(), routes: ['config', 'dashboard', 'online-flash', 'offline-flash', 'remote-service'].map(name => ({ name, path: '/' + name, component: { template: '<div/>' } })) })
    const gui = createGuiAutomation(router, () => ({ backend: 'alive' }))
    for (const page of ['config', 'dashboard', 'online-flash', 'offline-flash', 'remote-service']) {
      const state = await gui.execute({ action: 'navigate', page })
      expect(state.page).toBe(page)
      expect(state.backend).toBe('alive')
    }
    expect((await gui.execute({ action: 'navigate', page: 'dashboard', tab: 'modbus' })).tab).toBe('modbus')
    expect((await gui.execute({ action: 'navigate', page: 'config', section: 'files' })).section).toBe('files')
    await expect(gui.execute({ action: 'navigate', page: 'https://bad' })).rejects.toThrow()
    await expect(gui.execute({ action: 'eval' })).rejects.toThrow()
  })
  it('uses component controls and removes stale handlers when a panel unmounts', async () => {
    const router = createRouter({ history: createMemoryHistory(), routes: [] })
    let paused = false
    const action = vi.fn(() => { paused = true })
    const panel = mount({ setup() { useGuiPanel('systemview', { snapshot: () => ({ paused }), actions: { 'systemview.pause': action } }) }, template: '<div/>' })
    const gui = createGuiAutomation(router, () => ({}))
    expect((await gui.execute({ action: 'systemview.pause' })).panels.systemview).toEqual({ paused: true })
    expect(action).toHaveBeenCalledOnce()
    panel.unmount()
    await expect(gui.execute({ action: 'systemview.pause' })).rejects.toThrow('not mounted')
  })
})
