<script setup lang="ts">
import { computed } from 'vue'
import { otpHex } from '../lib/otpConfiguration'
import { otpFieldValue, type OtpWord } from '../lib/hpmOtpProfiles'
import { tr } from '../composables/useLanguage'
const props = defineProps<{ entries: { word: number; value: number | null; locked?: boolean | null; shadow?: number | null }[]; columns: number; selected: number; disabled?: boolean; definitions?: OtpWord[] }>()
defineEmits<{ select: [word: number] }>()
const groups = computed(() => {
  const rows = new Map<number, typeof props.entries>()
  for (const entry of props.entries) {
    const start = Math.floor(entry.word / props.columns) * props.columns
    if (!rows.has(start)) rows.set(start, [])
    rows.get(start)!.push(entry)
  }
  return [...rows].sort(([a], [b]) => a - b).map(([start, entries]) => ({ start, cells: Array.from({ length: props.columns }, (_, i) => entries.find(entry => entry.word === start + i)) }))
})
function tooltip(item: typeof props.entries[number]) {
  const definition = props.definitions?.find(word => word.word === item.word)
  const fields = item.value === null ? '' : definition?.fields.map(field => `${field.name}: 0x${otpFieldValue(item.value!, field)}`).join('\n') || ''

  return `Word ${item.word}\nHex: ${item.value === null ? '—' : otpHex(item.value)}\nBinary: ${item.value === null ? '—' : item.value.toString(2).padStart(32, '0')}\n${tr('影子值', 'Shadow')}: ${item.shadow == null ? '—' : otpHex(item.shadow)}\n${tr('锁定', 'Locked')}: ${item.locked == null ? tr('未知', 'Unknown') : item.locked ? tr('是', 'Yes') : tr('否', 'No')}\n${definition?.name || ''}\n${fields}`
}
</script>
<template>
  <div class="grid-scroll"><table class="otp-grid">
    <thead><tr><th>Word</th><th v-for="n in columns" :key="n">{{ n - 1 }}</th></tr></thead>
    <tbody><tr v-for="group in groups" :key="group.start"><th>{{ group.start }}:{{ group.start + columns - 1 }}</th>
      <td v-for="(cell, i) in group.cells" :key="i"><button v-if="cell" type="button" :disabled="disabled" :class="[{ selected: selected === cell.word }, definitions?.find(word => word.word === cell.word)?.category]" :aria-label="`Word ${cell.word}`" :aria-pressed="selected === cell.word" :title="tooltip(cell)" @click="$emit('select', cell.word)">{{ cell.value === null ? '—' : otpHex(cell.value) }}</button><span v-else class="missing">—</span></td>
    </tr></tbody>
  </table></div>
</template>
<style scoped>
.grid-scroll{overflow:auto}.otp-grid{width:100%;border-collapse:collapse;font:12px var(--font-mono)}th,td{padding:8px;text-align:center;border-bottom:1px solid var(--border);white-space:nowrap}th{color:var(--muted);font-weight:400;background:var(--bg)}tbody tr:nth-child(even){background:color-mix(in srgb,var(--bg) 50%,var(--surface))}button{font:inherit;color:var(--success);background:transparent;border:1px solid transparent;border-radius:4px;padding:8px;cursor:pointer}button:hover,button.selected{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 9%,var(--surface))}button:focus-visible{outline:2px solid var(--accent)}.missing{color:var(--dim)}
.IDENTIFY{color:#68b8f5}.SECURE{color:#e0bf65}.SECRET{color:#f08080}
</style>
