import { computed, onActivated, onBeforeUnmount, onMounted, ref, watch, type Ref } from 'vue'
import { hpmFlashPreset, parseHpmFlashWords, type HpmFlashWords } from '../lib/hpmFlashConfig'
import { tr } from './useLanguage'

const EVENT = 'mklink-hpm-flash-config-changed'
export function useHpmFlashConfig(target: Ref<string>) {
  const words = ref<HpmFlashWords>(['', '', '', ''])
  const storageError = ref('')
  const referenceBoard = computed(() => hpmFlashPreset(target.value).board)
  const key = () => `mklink.hpmFlash.${target.value.trim().toLowerCase()}`
  const flashCfg = computed(() => {
    try { return parseHpmFlashWords(words.value) } catch { return null }
  })
  function load() {
    storageError.value = ''
    try {
      const saved = localStorage.getItem(key())
      if (saved === null) { words.value = hpmFlashPreset(target.value).words; return }
      const data: unknown = JSON.parse(saved)
      // Incomplete drafts are intentionally restored instead of falling back to a preset.
      if (!Array.isArray(data) || data.length !== 4 || !data.every(word => typeof word === 'string')) throw new Error('Invalid draft')
      words.value = [...data] as HpmFlashWords
    } catch {
      words.value = ['', '', '', '']
      storageError.value = tr('无法读取已保存的配置，请重新输入或导入。', 'Cannot read saved configuration. Enter or import it again.')
    }
  }
  function setWords(value: HpmFlashWords) {
    words.value = [...value]
    storageError.value = ''
    try {
      localStorage.setItem(key(), JSON.stringify(value))
      window.dispatchEvent(new CustomEvent(EVENT, { detail: key() }))
    } catch {
      storageError.value = tr('配置未能保存；关闭页面后将丢失，请导出备份。', 'Configuration could not be saved. Export a backup before closing.')
    }
  }
  function changed(event: Event) {
    if ((event as CustomEvent).detail === key()) load()
  }
  watch(target, load, { immediate: true, flush: 'sync' })
  onActivated(load)
  onMounted(() => window.addEventListener(EVENT, changed))
  onBeforeUnmount(() => window.removeEventListener(EVENT, changed))
  return { words, flashCfg, referenceBoard, storageError, setWords }
}
