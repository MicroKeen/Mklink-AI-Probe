<template>
  <div class="operation-information">
    <template v-if="Array.isArray(value)">
      <table v-if="columns.length"><thead><tr><th v-for="key in columns" :key="key">{{ label(key) }}</th></tr></thead>
        <tbody><tr v-for="(row, index) in value.slice(0, 40)" :key="index"><td v-for="key in columns" :key="key">{{ display(row[key], key) }}</td></tr></tbody></table>
      <ul v-else><li v-for="(item, index) in value.slice(0, 40)" :key="index"><CapabilityInformation v-if="depth < 3" :value="item" :depth="depth + 1" /><span v-else>更多信息已保留，可在对话中查询</span></li></ul>
      <p v-if="value.length > 40">显示前 40 项，共 {{ value.length }} 项；可在对话中查询其余内容。</p>
    </template>
    <dl v-else-if="value && typeof value === 'object'">
      <template v-for="(item, key) in value" :key="key"><dt>{{ label(String(key)) }}</dt><dd>
        <details v-if="item && typeof item === 'object'"><summary>{{ Array.isArray(item) ? `${item.length} 项` : '查看详情' }}</summary><CapabilityInformation v-if="depth < 3" :value="item" :depth="depth + 1" /><p v-else>更多信息已保留，可在对话中查询</p></details>
        <span v-else>{{ display(item, String(key)) }}</span>
      </dd></template>
    </dl>
    <p v-else>{{ display(value) }}</p>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { display, label } from '../../lib/capabilityPresentation'
const props = withDefaults(defineProps<{ value: any; depth?: number }>(), { depth: 0 })
const columns = computed(() => Array.isArray(props.value) && props.value.length && props.value.slice(0, 40).every(row => row && typeof row === 'object' && !Array.isArray(row) && Object.values(row).every(value => value === null || typeof value !== 'object'))
  ? [...new Set(props.value.slice(0, 40).flatMap(row => Object.keys(row)))].slice(0, 12) : [])
</script>
<style scoped>
.operation-information { overflow:auto; min-width:0; font-size:12px; } dl { display:grid; grid-template-columns:minmax(80px, 1fr) minmax(0, 3fr); gap:8px 12px; margin:0; }
dt { color:var(--muted); } dd { margin:0; overflow-wrap:anywhere; } table { border-collapse:collapse; width:100%; } th,td { padding:7px; border-bottom:1px solid var(--border); text-align:left; overflow-wrap:anywhere; } p { margin:4px 0; } ul { padding-left:20px; } summary { cursor:pointer; }
</style>
