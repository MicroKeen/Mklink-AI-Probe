<script setup lang="ts">
import { FolderOpen } from '@lucide/vue'
import { useDashboardSetup } from '../../composables/useDashboardSetup'
import { tr } from '../../composables/useLanguage'
import { IS_REMOTE } from '../../lib/runtimeEndpoint'

defineProps<{ busy?: boolean }>()
const { loadedSymbolName, loadingSymbols, loadSymbolFile } = useDashboardSetup()
</script>

<template>
  <button type="button" data-gui-file-picker :disabled="IS_REMOTE || loadingSymbols || busy"
    :title="loadedSymbolName ? tr('重新选择 AXF / ELF', 'Open another AXF / ELF') + ' · ' + loadedSymbolName : tr('选择板上程序对应的 AXF / ELF', 'Open the AXF / ELF for the running firmware')"
    @click="loadSymbolFile">
    <FolderOpen :size="14" aria-hidden="true" />
    <span>{{ loadedSymbolName || tr('打开 AXF / ELF', 'Open AXF / ELF') }}</span>
  </button>
</template>

<style scoped>
button { max-width: 20ch; min-width: 0; }
svg { flex: none; }
span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
