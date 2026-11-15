import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, nextTick, ref } from 'vue'
import { expect, it, vi } from 'vitest'
import WorkbenchPanel from './WorkbenchPanel.vue'

vi.mock('./WaveformViewer.vue', () => ({ default: { name: 'WaveformViewer', props: ['arraySnapshotPath', 'signals'], template: '<div class="waveform-fixture" />' } }))
vi.mock('./SymbolVariablePanel.vue', () => ({ default: {
  name: 'SymbolVariablePanel', props: ['snapshotPath'], emits: ['snapshot-change'], template: '<div class="variables-fixture" />',
  setup: (props: any, { emit, expose }: any) => {
    const read = () => ({ snapshotPath: props.snapshotPath })
    expose({ catalog: () => [], read, execute: async (_action: string, args: any) => { emit('snapshot-change', args.path); await nextTick(); return read() } })
  },
} }))
vi.mock('./RttChannelPanel.vue', () => ({ default: { template: '<div/>' } }))
vi.mock('./SerialPortPanel.vue', () => ({ default: { template: '<div/>' } }))

it('propagates an array selection and only displays it in matching wave sources', async () => {
  const panels = ['variables', 'watch', 'watch', 'watch'].map((type, index) => ({ id: `p${index}`, type, title: type, source: { signals: index === 2 ? ['other'] : index === 3 ? ['samples'] : [] }, x: 0, y: index * 4, w: 6, h: 4 }))
  const cards: any[] = []
  const Harness = defineComponent({ components: { WorkbenchPanel }, setup: () => ({ panels, snapshot: ref<string | null>(null), register: (index: number, card: unknown) => { cards[index] = card } }), template: '<WorkbenchPanel v-for="(panel, index) in panels" :key="panel.id" :ref="card => register(index, card)" :panel="panel" :snapshot-path="snapshot" :device-connected="true" :symbol-loaded="true" :latest-values="{}" :rtt="{}" @snapshot="snapshot = $event" />' })
  const wrapper = mount(Harness)
  await flushPromises()
  expect(await cards[0].execute('symbols.array.set', { path: 'samples' })).toEqual({ snapshotPath: 'samples' })
  const waves = wrapper.findAllComponents({ name: 'WaveformViewer' })
  expect(waves.map(wave => wave.props('arraySnapshotPath'))).toEqual(['samples', null, 'samples'])
  expect(cards[0].read()).toEqual({ snapshotPath: 'samples' })
  await cards[0].execute('symbols.array.clear', { path: null })
  expect(waves.map(wave => wave.props('arraySnapshotPath'))).toEqual([null, null, null])
  wrapper.unmount()
})
