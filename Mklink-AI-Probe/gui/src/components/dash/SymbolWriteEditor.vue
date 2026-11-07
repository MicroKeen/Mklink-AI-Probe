<template>
  <div class="write-editor">
    <select v-if="symbol.scalar_kind === 'bool' || symbol.scalar_kind === 'enum'" v-model="value"
      :aria-label="tr('新值', 'New value')" :data-testid="`write-input-${symbol.path}`" :disabled="busy">
      <option v-for="label in options" :key="label" :value="label">{{ label }}</option>
    </select>
    <input v-else v-model="value" class="form-input" inputmode="decimal"
      :aria-label="tr('新值', 'New value')" :data-testid="`write-input-${symbol.path}`" :disabled="busy" />
    <button type="button" class="btn btn-primary" :data-testid="`write-${symbol.path}`" :disabled="disabled || busy || !value.trim()" @click="$emit('write')">
      {{ busy ? tr('写入中', 'Writing') : tr('确认写入', 'Confirm write') }}
    </button>
    <button type="button" class="btn btn-secondary" :disabled="busy" @click="$emit('cancel')">{{ tr('取消', 'Cancel') }}</button>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { tr } from '../../composables/useLanguage'
import type { SymbolDescriptor } from '../../types/mklink'
const props = defineProps<{ symbol: SymbolDescriptor; busy: boolean; disabled: boolean }>()
defineEmits<{ write: []; cancel: [] }>()
const value = defineModel<string>({ required: true })
const options = computed(() => props.symbol.scalar_kind === 'bool' ? ['true', 'false'] : Object.keys(props.symbol.enum_values))
</script>
<style scoped>
.write-editor { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 6px; padding: 4px 8px; }
.write-editor input, .write-editor select { min-width: 0; height: 28px; }
.write-editor .btn { min-height: 28px; padding: 3px 8px; }
</style>
