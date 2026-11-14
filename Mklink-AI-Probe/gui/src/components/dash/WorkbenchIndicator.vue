<template>
  <div class="workbench-indicator">
    <output :aria-label="widget.title"><span class="indicator-light" :class="{ active: value === true || typeof value === 'number' && value > 0 }" aria-hidden="true"></span>{{ value === undefined ? '—' : typeof value === 'object' ? JSON.stringify(value) : String(value) }}</output>
    <button type="button" :disabled="busy" @click="emit('read')">{{ tr('刷新状态', 'Refresh status') }}</button>
  </div>
</template>
<script setup lang="ts">
import { tr } from '../../composables/useLanguage'
import type { ControlWidget } from '../../lib/workbenchControls'
defineProps<{ widget: ControlWidget; value?: unknown; busy?: boolean }>()
const emit = defineEmits<{ read: [] }>()
</script>
<style scoped>
.workbench-indicator { display:flex; align-items:center; flex-wrap:wrap; gap:8px; min-width:0; }.workbench-indicator output { display:flex; align-items:center; gap:8px; overflow-wrap:anywhere; }.indicator-light { flex:none; width:12px; height:12px; border-radius:50%; background:var(--muted); }.indicator-light.active { background:var(--success); box-shadow:0 0 5px var(--success); }.workbench-indicator button { color:var(--fg); background:var(--input-bg); border:1px solid var(--border); border-radius:4px; padding:4px 6px; cursor:pointer; }
</style>
