import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import SuperWatchTab from './SuperWatchTab.vue'
import SymbolVariablePanel from './SymbolVariablePanel.vue'
import WaveformViewer from './WaveformViewer.vue'
import { DESKTOP_SETTINGS_STORAGE_KEY } from '../../lib/desktopSettings'

describe('SuperWatchTab', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ profile: 'medium' }) })))
  })
  afterEach(() => vi.unstubAllGlobals())
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
            emits: ['latest-values'],
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
