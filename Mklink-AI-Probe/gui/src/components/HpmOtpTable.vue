<script setup lang="ts">
import { tr } from '../composables/useLanguage'
defineProps<{ rows: { word: number; current: number | null; shadow: number | null; locked: boolean | null }[]; romRead?: boolean }>()
const hex = (value: number | null) => value === null ? '—' : `0x${value.toString(16).toUpperCase().padStart(8, '0')}`
</script>

<template>
  <div v-if="rows.length" class="table-wrap"><table>
    <thead><tr><th>Word</th><th>{{ romRead ? tr('ROM 读取值', 'ROM value') : tr('熔丝值', 'Fuse') }}</th><th>{{ tr('影子值', 'Shadow') }}</th><th>{{ tr('锁定', 'Locked') }}</th></tr></thead>
    <tbody><tr v-for="item in rows" :key="item.word"><td>{{ item.word }}</td><td>{{ hex(item.current) }}</td><td>{{ hex(item.shadow) }}</td><td>{{ item.locked === null ? tr('未知', 'Unknown') : item.locked ? tr('是', 'Yes') : tr('否', 'No') }}</td></tr></tbody>
  </table></div>
</template>

<style scoped>
.table-wrap{overflow:auto;max-height:300px;margin:10px 0}table{width:100%;border-collapse:collapse;font-family:var(--font-mono);font-size:11px}th,td{text-align:left;padding:5px;white-space:nowrap;border-bottom:1px solid var(--border)}
</style>
