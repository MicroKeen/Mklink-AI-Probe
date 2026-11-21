import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick, defineComponent } from 'vue'
import SuperWatchTab from './SuperWatchTab.vue'
import SymbolVariablePanel from './SymbolVariablePanel.vue'
import WaveformViewer from './WaveformViewer.vue'
import { DESKTOP_SETTINGS_STORAGE_KEY } from '../../lib/desktopSettings'
import { useWatchProfile } from '../../composables/useWatchProfile'

describe('SuperWatchTab', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ profile: 'medium' }) })))
  })
  afterEach(() => vi.unstubAllGlobals())
  it('loads and saves shared AXF display settings only on an explicit panel operation', async () => {
    const profile = useWatchProfile(), previous = profile.profile.value
    const saved = { path: 'target.axf.superwatch.json', available: true, error: '', missing: [],
      viewer: { revision: 'viewer-1', viewer: {} }, layout: { revision: 'layout-1', layout: { source: 'peripherals', panelWidth: 480, hidden: ['gain'] } } }
    const loadProfile = vi.fn()
    const Wave = defineComponent({ setup(_, { expose }) { expose({ loadProfile, exportProfile: () => ({ interval: .02 }) }); return () => null } })
    vi.mocked(fetch).mockImplementation(async (_url, options) => {
      const body = options?.body ? JSON.parse(String(options.body)) : null
      return { ok: true, json: async () => body ? { revision: 'saved-2', [body.section]: body.value } : saved } as Response
    })
    const wrapper = mount(SuperWatchTab, { props: { deviceConnected: false, panelId: 'profile_test' }, global: { stubs: { SymbolVariablePanel: true, PeripheralWatchPanel: true, WaveformViewer: Wave } } })
    try {
      await flushPromises()
      expect(vi.mocked(fetch).mock.calls.some(([, options]) => options?.method === 'PUT')).toBe(false)
      await wrapper.vm.execute('superwatch.profile.load', {})
      expect(wrapper.vm.read().panelWidth).toBe(480)
      expect(loadProfile).toHaveBeenCalledWith({}, saved.path)
      await wrapper.vm.execute('superwatch.width', { width: 400 })
      await wrapper.vm.execute('superwatch.profile.save', {})
      expect(vi.mocked(fetch).mock.calls.filter(([, options]) => options?.method === 'PUT').map(([, options]) => JSON.parse(String(options?.body)).section)).toEqual(['viewer', 'layout'])
      expect(profile.profile.value?.layout.layout.panelWidth).toBe(400)
    } finally { wrapper.unmount(); profile.profile.value = previous }
  })

  it('keeps workbench layout independent of the shared AXF profile', async () => {
    const profile = useWatchProfile()
    const previous = profile.profile.value
    profile.profile.value = { path: 'target.axf.superwatch.json', error: '', missing: [],
      viewer: { revision: 'viewer-1', viewer: {} },
      layout: { revision: 'layout-1', layout: { source: 'peripherals', panelWidth: 480, hidden: ['gain'] } } }
    const wrappers = ['left', 'right'].map(panelId => mount(SuperWatchTab, {
      props: { deviceConnected: false, panelId },
      global: { stubs: { SymbolVariablePanel: true, PeripheralWatchPanel: true, WaveformViewer: true } },
    }))
    try {
      await flushPromises()
      expect(wrappers[0]!.vm.read()).toMatchObject({ source: 'variables', hidden: [] })
      expect(wrappers.every(wrapper => !wrapper.find('.profile-status').exists())).toBe(true)
      await wrappers[0]!.vm.execute('superwatch.catalog.set', { source: 'peripherals' })
      expect(wrappers[1]!.vm.read().source).toBe('variables')
      await new Promise(resolve => setTimeout(resolve, 300))
      expect(vi.mocked(fetch).mock.calls.some(([, options]) => options?.method === 'PUT')).toBe(false)
    } finally {
      wrappers.forEach(wrapper => wrapper.unmount())
      profile.profile.value = previous
    }
  })
  it('ignores obsolete hidden-pane preferences while retaining the useful layout settings', async () => {
    vi.stubGlobal('localStorage', { getItem: (key: string) => key === DESKTOP_SETTINGS_STORAGE_KEY + '.superwatch-layout'
      ? JSON.stringify({ panelWidth: 420, hideSettings: true, hideCatalog: true }) : null, setItem: vi.fn() })
    const wrapper = mount(SuperWatchTab, {
      props: { deviceConnected: false },
      global: { stubs: { SymbolVariablePanel: true, PeripheralWatchPanel: true, WaveformViewer: { template: '<div><slot name="actions" /></div>' } } },
    })
    expect(wrapper.get('.superwatch-workspace').classes()).not.toContain('compact')
    expect(wrapper.get('.superwatch-workspace').classes()).not.toContain('catalog-hidden')
    expect(wrapper.get('.superwatch-workspace').attributes('style')).toContain('420px')
    expect(wrapper.get('.workspace-actions').findAll('button')).toHaveLength(1)
    expect(wrapper.find('#superwatch-speed').exists()).toBe(false)
    wrapper.unmount()
  })
  it('uses the Dashboard clock without its own polling or setter', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.fn(async (_url: unknown) => ({ ok: true, json: async () => ({}) }))
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mount(SuperWatchTab, {
      props: { deviceConnected: true },
      global: { stubs: { SymbolVariablePanel: true, PeripheralWatchPanel: true, WaveformViewer: true } },
    })
    await flushPromises()
    await vi.advanceTimersByTimeAsync(3000)
    expect(wrapper.find('[data-testid="superwatch-speed"]').exists()).toBe(false)
    expect(fetchMock.mock.calls.some(call => String(call[0]).includes('debug-speed'))).toBe(false)
    wrapper.unmount()
    vi.useRealTimers()
  })
  it('shares waveform values and channel visibility between both workspace panes', async () => {
    const wrapper = mount(SuperWatchTab, {
      props: { deviceConnected: true },
      global: {
        stubs: {
          PeripheralWatchPanel: true,
          SymbolVariablePanel: {
            name: 'SymbolVariablePanel',
            emits: ['visibility-change', 'selection-removed', 'snapshot-change'],
            props: ['deviceConnected', 'latestValues', 'hiddenChannels'],
            template: '<aside class="variable-panel-stub" />',
          },
          WaveformViewer: {
            name: 'WaveformViewer',
            emits: ['latest-values', 'visibility-change'],
            props: ['mode', 'deviceConnected', 'hiddenChannels', 'arraySnapshotPath'],
            template: '<main class="waveform-stub" />',
          },
        },
      },
    })

    expect(wrapper.get('.superwatch-workspace').exists()).toBe(true)
    wrapper.findComponent(WaveformViewer).vm.$emit('latest-values', { gain: 1.25 })
    await nextTick()

    expect(wrapper.findComponent(SymbolVariablePanel).props('latestValues')).toEqual({ gain: 1.25 })

    wrapper.findComponent(SymbolVariablePanel).vm.$emit('visibility-change', 'gain', false)
    await nextTick()
    expect(wrapper.findComponent(SymbolVariablePanel).props('hiddenChannels')).toEqual(new Set(['gain']))
    expect(wrapper.findComponent(WaveformViewer).props('hiddenChannels')).toEqual(new Set(['gain']))
    wrapper.findComponent(WaveformViewer).vm.$emit('visibility-change', 'gain', true)
    await nextTick()
    expect(wrapper.findComponent(SymbolVariablePanel).props('hiddenChannels')).toEqual(new Set())
    wrapper.findComponent(WaveformViewer).vm.$emit('visibility-change', 'gain', false)
    await nextTick()
    expect(wrapper.findComponent(SymbolVariablePanel).props('hiddenChannels')).toEqual(new Set(['gain']))
    expect(wrapper.findComponent(WaveformViewer).props('arraySnapshotPath')).toBe(null)
    wrapper.findComponent(SymbolVariablePanel).vm.$emit('snapshot-change', 'samples')
    await nextTick()
    expect(wrapper.findComponent(WaveformViewer).props('arraySnapshotPath')).toBe('samples')

    wrapper.findComponent(SymbolVariablePanel).vm.$emit('selection-removed', 'gain')
    await nextTick()
    expect(wrapper.findComponent(SymbolVariablePanel).props('hiddenChannels')).toEqual(new Set())
    expect(wrapper.findComponent(WaveformViewer).props('hiddenChannels')).toEqual(new Set())
  })
})
