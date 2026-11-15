import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, ref } from 'vue'
import HpmFlashConfigPanel from './HpmFlashConfigPanel.vue'
import { useHpmFlashConfig } from '../composables/useHpmFlashConfig'
import { hpmFlashFile, hpmFlashPreset, parseHpmFlashFile, parseHpmFlashWords } from '../lib/hpmFlashConfig'

const Host = defineComponent({
  components: { HpmFlashConfigPanel },
  setup() { const target = ref('HPM5301'); return { target, ...useHpmFlashConfig(target) } },
  template: `<HpmFlashConfigPanel :target-part="target" :model-value="words" :reference-board="referenceBoard" :storage-error="storageError" @update:model-value="setWords" />`,
})

beforeEach(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => data.set(key, value),
  })
})
describe('HPM Flash configuration', () => {
  it('shares edits, restores them after remount and isolates different targets', async () => {
    const first = mount(Host), second = mount(Host)
    await first.get('[aria-label="opt0"]').setValue('0x00000007')
    expect(second.get<HTMLInputElement>('[aria-label="opt0"]').element.value).toBe('0x00000007')
    await first.get('[aria-label="header"]').setValue('')
    first.unmount(); second.unmount()
    const restored = mount(Host)
    expect(restored.get<HTMLInputElement>('[aria-label="opt0"]').element.value).toBe('0x00000007')
    expect(restored.get('[role="alert"]').text()).toContain('32')
    restored.vm.target = 'HPM6400'; await flushPromises()
    expect(restored.get<HTMLInputElement>('[aria-label="opt0"]').element.value).toBe('')
    await restored.get('[aria-label="opt0"]').setValue('0x8')
    restored.vm.target = 'HPM5301'; await flushPromises()
    expect(restored.get<HTMLInputElement>('[aria-label="opt0"]').element.value).toBe('0x00000007')
    restored.unmount()
  })

  it('does not substitute defaults for corrupt saved data', () => {
    localStorage.setItem('mklink.hpmFlash.hpm5301', '{bad')
    const host = mount(Host)
    expect(host.text()).toContain('无法读取已保存的配置')
    expect(host.get<HTMLInputElement>('[aria-label="header"]').element.value).toBe('')
    host.unmount()
  })

  it('imports four words for the same target and rejects mismatches and bad words', () => {
    const words = hpmFlashPreset('HPM5301').words
    expect(parseHpmFlashFile(hpmFlashFile('HPM5301', words), 'hpm5301')).toEqual(words)
    expect(() => parseHpmFlashFile(hpmFlashFile('HPM5301', words), 'HPM6400')).toThrow()
    for (const bad of ['0x100000000', '-1', '0x1);evil()', 1, true, '']) {
      expect(() => parseHpmFlashWords([bad, ...words.slice(1)])).toThrow()
    }
  })

  it.each(['lock', 'edit', 'target', 'unmount'])('discards an import completed after %s', async (change) => {
    const words = hpmFlashPreset('HPM5301').words
    const wrapper = mount(HpmFlashConfigPanel, { props: { targetPart: 'HPM5301', modelValue: words, referenceBoard: 'hpm5301evklite', storageError: '' } })
    let finish!: (text: string) => void
    const file = new File(['{}'], 'config.json')
    vi.spyOn(file, 'text').mockImplementation(() => new Promise(resolve => { finish = resolve }))
    const input = wrapper.get('[data-testid="hpm-flash-import"]')
    Object.defineProperty(input.element, 'files', { configurable: true, value: [file] })
    await input.trigger('change')
    if (change === 'lock') await wrapper.setProps({ disabled: true })
    if (change === 'edit') await wrapper.setProps({ modelValue: ['0x1', ...words.slice(1)] as typeof words })
    if (change === 'target') await wrapper.setProps({ targetPart: 'HPM6400' })
    if (change === 'unmount') wrapper.unmount()
    finish(hpmFlashFile('HPM5301', words)); await flushPromises()
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    if (change === 'lock') expect(wrapper.get('[aria-label="header"]').attributes('disabled')).toBeDefined()
    if (change !== 'unmount') wrapper.unmount()
  })
})
