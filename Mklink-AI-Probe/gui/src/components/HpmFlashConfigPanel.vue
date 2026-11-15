<script setup lang="ts">
import { computed, onBeforeUnmount, onDeactivated, ref, watch } from 'vue'
import { tr } from '../composables/useLanguage'
import { saveTextFile } from '../lib/downloadTextFile'
import { HPM_FLASH_FIELDS, hpmFlashFile, hpmFlashPreset, parseHpmFlashFile, parseHpmFlashWords, type HpmFlashWords } from '../lib/hpmFlashConfig'

const props = defineProps<{ targetPart: string; modelValue: HpmFlashWords; referenceBoard: string; storageError: string; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: HpmFlashWords] }>()
const fileInput = ref<HTMLInputElement | null>(null)
const fileError = ref('')
let revision = 0
onBeforeUnmount(() => { revision++ })
onDeactivated(() => { revision++ })
watch(() => [props.targetPart, props.modelValue, props.disabled], () => { revision++; fileError.value = '' }, { deep: true, flush: 'sync' })
const valid = computed(() => { try { parseHpmFlashWords(props.modelValue); return true } catch { return false } })
function edit(index: number, event: Event) {
  if (props.disabled) return
  const words: HpmFlashWords = [...props.modelValue]
  words[index] = (event.target as HTMLInputElement).value
  emit('update:modelValue', words)
}
function reset() {
  if (!props.disabled) emit('update:modelValue', hpmFlashPreset(props.targetPart).words)
}
async function importFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || props.disabled) return
  const current = ++revision
  const target = props.targetPart
  try {
    if (file.size > 64 * 1024) throw new Error('Too large')
    const words = parseHpmFlashFile(await file.text(), target)
    if (current !== revision || props.disabled || target !== props.targetPart) return
    emit('update:modelValue', words)
  } catch {
    if (current === revision) fileError.value = tr('导入失败：请选择同型号的有效 Flash 配置 JSON（最大 64 KiB）。', 'Import failed: use a valid Flash configuration JSON for this target (up to 64 KiB).')
  }
}
async function exportFile() {
  if (!valid.value) return
  try { await saveTextFile(`${props.targetPart}.flash.json`, hpmFlashFile(props.targetPart, props.modelValue)) }
  catch { fileError.value = tr('配置导出失败', 'Failed to export configuration') }
}
</script>

<template>
  <section class="hpm-flash-config" data-testid="hpm-flash-config">
    <h4>{{ tr('Flash 配置', 'Flash configuration') }}</h4>
    <p>{{ tr('按实际 NOR Flash 设置，烧录时应用。修改后按器件自动保存，在线与脱机共用。', 'Configure for the actual NOR Flash; applied when programming. Edits are saved per target and shared by online and offline programming.') }}</p>
    <p v-if="referenceBoard">{{ tr('参考默认值：', 'Reference preset: ') }}{{ referenceBoard }}</p>
    <p v-else>{{ tr('此器件无参考默认值，请填写或导入四个配置字。', 'No reference preset for this target. Enter or import all four configuration words.') }}</p>
    <label v-for="(field, index) in HPM_FLASH_FIELDS" :key="field">
      <span>{{ field === 'xpi_base_addr' ? tr('XPI 控制器基址', 'XPI controller base') : field }}</span>
      <input :data-testid="`hpm-flash-${field}`" :aria-label="field" :value="modelValue[index]" :disabled="disabled" spellcheck="false" placeholder="0x00000000" @input="edit(index, $event)" />
    </label>
    <p>{{ tr('每项为 32 位十六进制值。XPI 控制器基址不是 BIN 烧录地址；参考板参数不一定适合其他 NOR Flash。', 'Each value is 32-bit hexadecimal. The XPI controller base is not the BIN programming address. Reference board settings may not suit other NOR Flash devices.') }}</p>
    <div class="actions">
      <button class="btn" type="button" :disabled="disabled || !referenceBoard" @click="reset">{{ tr('恢复参考值', 'Restore preset') }}</button>
      <button class="btn" type="button" :disabled="disabled" @click="fileInput?.click()">{{ tr('导入配置', 'Import config') }}</button>
      <button class="btn" type="button" :disabled="!valid" @click="exportFile">{{ tr('导出配置', 'Export config') }}</button>
      <input ref="fileInput" type="file" accept=".json,application/json" hidden :disabled="disabled" data-testid="hpm-flash-import" @change="importFile" />
    </div>
    <p v-if="!valid" role="alert">{{ tr('请填写四个有效的 32 位十六进制配置字后再烧录。', 'Enter four valid 32-bit hexadecimal configuration words before programming.') }}</p>
    <p v-if="storageError || fileError" role="alert">{{ storageError || fileError }}</p>
  </section>
</template>

<style scoped>
.hpm-flash-config { padding: 14px 16px; border-top: 1px solid var(--border); color: var(--fg); }
h4 { margin: 0 0 10px; }
p { font-size: 12px; line-height: 1.6; color: var(--muted); margin: 8px 0; }
label { display: grid; grid-template-columns: minmax(70px, 1fr) minmax(120px, 1.4fr); align-items: center; gap: 8px; margin: 8px 0; font-size: 13px; }
input:not([hidden]) { width: 100%; min-width: 0; box-sizing: border-box; padding: 7px 8px; font-family: var(--font-mono); background: var(--bg); color: var(--fg); border: 1px solid var(--border); border-radius: 4px; }
.actions { display: flex; gap: 6px; flex-wrap: wrap; }
[role="alert"] { color: var(--danger); }
</style>
