<template>
  <div class="workbench-tool" :data-tool="tool">
    <p v-if="IS_REMOTE && !remoteTools.includes(tool)" role="alert">{{ tr('远程模式不开放此宿主功能。', 'This host function is unavailable in remote mode.') }}</p>
    <component v-else :is="toolComponents[tool]" ref="surface" v-bind="componentProps" />
  </div>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { IS_REMOTE } from '../../lib/runtimeEndpoint'
import { toolComponents, remoteTools, type WorkbenchTool } from '../../lib/workbenchTools'
import { tr } from '../../composables/useLanguage'
import type { SemanticSurface, SemanticExecutionContext, JsonObject } from '../../lib/frontendControl'
const props = defineProps<{ tool: WorkbenchTool; active?: boolean; panelId: string; deviceConnected: boolean; symbolLoaded: boolean; symbolError?: string; latestValues: Record<string, number> }>()
const surface = ref<SemanticSurface | null>(null)
const componentProps = computed(() => {
  if (['connection', 'files', 'firmware', 'runtime'].includes(props.tool)) return { embedded: true, section: props.tool === 'connection' ? 'local' : props.tool }
  if (props.tool === 'superwatch') return { panelId: props.panelId, deviceConnected: props.deviceConnected, symbolLoaded: props.symbolLoaded, symbolError: props.symbolError }
  if (props.tool === 'peripherals') return { deviceConnected: props.deviceConnected, latestValues: props.latestValues }
  if (['symbols', 'hardfault'].includes(props.tool)) return { deviceConnected: props.deviceConnected, symbolLoaded: props.symbolLoaded, symbolError: props.symbolError }
  if (props.tool === 'rtt') return { deviceConnected: props.deviceConnected, panelId: props.panelId, active: props.active }
  if (props.tool === 'trace') return { deviceConnected: props.deviceConnected, active: props.active ?? true }
  if (props.tool === 'memory') return { deviceConnected: props.deviceConnected }
  return {}
})
defineExpose({
  catalog: () => surface.value?.catalog?.() || [],
  read: () => ({ tool: props.tool, mounted: !!surface.value, ...(surface.value?.read?.() || {}) }),
  execute: (action: string, args: JsonObject, context?: SemanticExecutionContext) => {
    if (!surface.value?.execute) throw new Error('Use this panel’s rendered GUI controls')
    return surface.value.execute(action, args, context)
  },
  restore: (view: JsonObject) => surface.value?.restore?.(view),
})
</script>
<style scoped>
.workbench-tool { padding:12px; min-width:0; min-height:100%; box-sizing:border-box; display:flex; flex-direction:column; container-type:inline-size; }
.workbench-tool :deep(.config-workspace) { min-height:0; }
.workbench-tool :deep(.superwatch-workspace), .workbench-tool :deep(.rtt-view-tab), .workbench-tool :deep(.systemview-tab) { flex:1; min-height:480px; }
.workbench-tool :deep(.superwatch-workspace.focused) { position:relative; inset:auto; }
@container (max-width:700px) { .workbench-tool :deep(.config-workspace) { display:flex; flex-direction:column; } .workbench-tool :deep(.superwatch-workspace) { display:flex; flex-direction:column; } }
</style>
