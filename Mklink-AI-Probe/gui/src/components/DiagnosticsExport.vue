<template>
  <button v-if="!IS_REMOTE" class="btn btn-sm" data-testid="export-diagnostics"
    :disabled="saving" :title="tr('保存最近的连接错误及软件版本，不包含固件和采集原文', 'Save recent connection errors and software version, without firmware or captured output')"
    @click="exportDiagnostics">{{ saving ? tr('正在导出…', 'Exporting…') : tr('导出诊断包', 'Export diagnostics') }}</button>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { API_BASE, IS_REMOTE } from '../lib/runtimeEndpoint'
import { saveBlobFile } from '../lib/downloadTextFile'
import { tr } from '../composables/useLanguage'
import { useToast } from '../composables/useToast'
import { flushConnectionDiagnostics } from '../lib/connectionDiagnostics'

const saving = ref(false)
const toast = useToast()
async function exportDiagnostics() {
  if (saving.value) return
  saving.value = true
  try {
    await flushConnectionDiagnostics()
    const response = await fetch(`${API_BASE}/api/diagnostics/export`, { signal: AbortSignal.timeout(15000) })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    if (!response.headers.get('content-type')?.includes('application/zip')) throw new Error(tr('诊断包格式无效', 'Invalid diagnostic archive'))
    const filename = `mklink-diagnostics-${new Date().toISOString().replace(/[:.]/g, '-')}.zip`
    if (await saveBlobFile(filename, await response.blob())) toast.success(tr('诊断包已保存，可发送给技术支持', 'Diagnostic archive saved; send it to support'))
  } catch (error) {
    toast.error(`${tr('导出失败', 'Export failed')}: ${error instanceof Error ? error.message : String(error)}`)
  } finally {
    saving.value = false
  }
}
</script>
