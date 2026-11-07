<template>
  <div class="row-actions">
    <button type="button" :data-testid="selectedList ? `selected-write-${path}` : `edit-${path}`"
      :disabled="writeDisabled" :title="writeTitle" @click="$emit('write')">{{ tr('写入', 'Write') }}</button>
    <button v-if="removable" type="button" :data-testid="selectedList ? `selected-remove-${path}` : `remove-${path}`"
      :disabled="removeDisabled" :aria-label="tr(`移除 ${path}`, `Remove ${path}`)" @click="$emit('remove')">{{ tr('移除', 'Remove') }}</button>
  </div>
</template>

<script setup lang="ts">
import { tr } from '../../composables/useLanguage'
defineProps<{ path: string; writeDisabled: boolean; writeTitle: string; removable: boolean; removeDisabled: boolean; selectedList?: boolean }>()
defineEmits<{ write: []; remove: [] }>()
</script>

<style scoped>
.row-actions { display:flex; gap:12px; padding:0 8px 3px 28px; }
button { border:0; background:transparent; color:var(--accent); font-size:11px; cursor:pointer; }
button:disabled { color:var(--muted); cursor:default; }
</style>
