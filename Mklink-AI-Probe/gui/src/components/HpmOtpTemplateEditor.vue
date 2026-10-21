<script setup lang="ts">
import { computed, ref } from 'vue'
import { applyOtpFields, type OtpWord } from '../lib/hpmOtpProfiles'
import { customOtpEntries, type OtpEntry } from '../lib/otpConfiguration'
import { tr } from '../composables/useLanguage'
const props = defineProps<{ words: OtpWord[]; entries: OtpEntry[]; disabled: boolean }>()
const emit = defineEmits<{ add: [entries: OtpEntry[]] }>()
const selected = ref<string[]>([]), values = ref<Record<string, string>>({}), error = ref('')
const fields = computed(() => props.words.flatMap(word => word.fields.filter(field => field.kind !== 'none').map(field => ({ word: word.word, field, id: `${word.word}:${field.name}` }))))
const keyGroups = computed(() => {
  const groups = new Map<string, number[]>()
  for (const word of props.words) for (const field of word.fields) {
    if (!/^(SRK_HASH|EXIP\d_KEK|OTP_KEK\d|DEBUG_KEY|MASTER_KEY)\[/.test(field.name)) continue
    const name = field.name.split('[')[0]!
    if (!groups.has(name)) groups.set(name, [])
    groups.get(name)!.push(word.word)
  }
  return [...groups].map(([name, words]) => ({ name, start: words[0]!, count: words.length }))
})
const key = ref(''), keyValues = ref('')
function addFields() {
  try {
    const edits = fields.value.filter(item => selected.value.includes(item.id)).map(item => ({ ...item, value: values.value[item.id] ?? '0' }))
    emit('add', applyOtpFields(props.entries, edits)); error.value = ''
  } catch (e) { error.value = String(e) }
}
function addKey() {
  try {
    const group = keyGroups.value.find(item => item.name === key.value)
    if (!group) return
    emit('add', customOtpEntries(group.start, group.count, keyValues.value, { first: 0, last: 127 })); error.value = ''; keyValues.value = ''
  } catch (e) { error.value = String(e) }
}
</script>
<template>
  <section class="templates" data-testid="otp-templates">
    <p>{{ tr('勾选需要配置的字段。未勾选字段保留当前值。', 'Select fields to configure. Unselected fields retain their current values.') }}</p>
    <fieldset :disabled="disabled">
      <div class="fields">
        <div v-for="item in fields" :key="item.id" class="field">
          <label><input v-model="selected" type="checkbox" :value="item.id">{{ item.field.name }} <small>Word {{ item.word }}</small></label>
          <select v-if="item.field.options.length" v-model="values[item.id]" :aria-label="item.id" :disabled="!selected.includes(item.id)">
            <option value="" disabled>{{ tr('选择值', 'Select value') }}</option><option v-for="choice in item.field.options" :key="choice.value" :value="String(choice.value)">{{ choice.label }} ({{ choice.value }})</option>
          </select>
          <select v-else-if="item.field.kind === 'check' && item.field.width === 1" v-model="values[item.id]" :aria-label="item.id" :disabled="!selected.includes(item.id)"><option value="0">0</option><option :value="String(2 ** item.field.width - 1)">{{ 2 ** item.field.width - 1 }}</option></select>
          <input v-else v-model="values[item.id]" :aria-label="item.id" :disabled="!selected.includes(item.id)" placeholder="0x…">
        </div>
      </div>
      <button class="btn" type="button" :disabled="!selected.length || selected.some(id => !values[id])" data-testid="otp-template-add" @click="addFields">{{ tr('添加所选字段', 'Add selected fields') }}</button>
      <details><summary>{{ tr('密钥与公钥摘要', 'Keys and public-key hashes') }}</summary>
        <select v-model="key" aria-label="OTP key template"><option value="" disabled>{{ tr('选择模板', 'Select template') }}</option><option v-for="group in keyGroups" :key="group.name" :value="group.name">{{ group.name }} · Word {{ group.start }}–{{ group.start + group.count - 1 }}</option></select>
        <p>{{ tr('按 Word 索引递增输入完整的 8 位十六进制值。', 'Enter full 8-digit hexadecimal words in increasing word-index order.') }}</p>
        <textarea v-model="keyValues" rows="3" aria-label="OTP key words" autocomplete="off" spellcheck="false" />
        <button class="btn" type="button" :disabled="!key || !keyValues" @click="addKey">{{ tr('添加 Words', 'Add Words') }}</button>
      </details>
    </fieldset>
    <p v-if="error" role="alert">{{ error }}</p>
  </section>
</template>
<style scoped>
.templates{padding:14px;border:1px solid var(--border);border-radius:5px;margin-bottom:14px}p,small{color:var(--muted);font-size:12px;line-height:1.6}fieldset{border:0;margin:0;padding:0;min-width:0}.fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:10px 24px;margin:12px 0}.field{display:grid;gap:5px}.field label{display:flex;gap:6px;align-items:center;font:12px var(--font-mono)}small{margin-left:auto}select,input:not([type=checkbox]),textarea{min-width:0;width:100%;box-sizing:border-box;padding:7px;background:var(--bg);color:var(--fg);border:1px solid var(--border);border-radius:4px}details{margin-top:18px}summary{cursor:pointer;margin-bottom:12px}textarea{margin-bottom:8px;font-family:var(--font-mono)}[role=alert]{color:var(--danger)}
</style>
