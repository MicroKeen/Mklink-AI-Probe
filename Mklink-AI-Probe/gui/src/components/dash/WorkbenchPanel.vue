<template>
  <div ref="root" class="workbench-panel-body" :data-gui-panel-id="panel.id" @pointerdown.capture="emit('viewInteraction')" @keydown.capture="emit('viewInteraction')" @wheel.capture.passive="emit('viewInteraction')" @focusin.capture="emit('viewInteraction')" @click.capture="recordNative" @input.capture="emit('viewInteraction')" @change.capture="emit('viewInteraction')" @pointerup.capture="emit('viewInteraction')">
  <p v-if="restoreError" role="alert">{{ restoreError }}</p>
  <template v-if="panel.type === 'watch'">
  <WaveformViewer ref="surface" :panel-id="panel.id" :signals="panel.source.signals?.length ? panel.source.signals : undefined" :view-state="panel.view"
    mode="SuperWatch" :active="active" :device-connected="deviceConnected" :array-snapshot-path="snapshotForPanel" @latest-values="values => emit('values', values)" />
  </template>
  <SymbolVariablePanel v-else-if="panel.type === 'variables'" ref="surface" :panel-id="panel.id" :view-paths="panel.source.signals"
    :device-connected="deviceConnected" :symbol-loaded="symbolLoaded" :symbol-error="symbolError" :latest-values="latestValues" :subscribe-values="true" :active="active" :snapshot-path="snapshotPath" @snapshot-change="path => emit('snapshot', path)" />
  <RttChannelPanel v-else-if="panel.type === 'rtt'" ref="surface" :panel-id="panel.id" :channel="panel.source.channel || 0"
    :running="active && rtt.running === true" :send-enabled="rtt.running === true && !rtt.runtime_error && rtt.down_buffers?.some((item: any) => item.channel === (panel.source.channel || 0) && item.active) === true" :session="rtt.session" :channel-status="rtt.channel_status?.[String(panel.source.channel || 0)]" />
  <ControlPanel v-else-if="panel.type === 'controls'" ref="surface" :panel-id="panel.id" :widgets="panel.widgets || []" :active="active" :commit-widgets="commitWidgets" @transfer="event => emit('transfer', event)" />
  <CapabilityPanel v-else-if="panel.type === 'capability'" ref="surface" :panel-id="panel.id" />
  <WorkbenchToolPanel v-else-if="panel.type === 'tool'" ref="surface" :tool="panel.source.tool!" :active="active" :panel-id="panel.id" :device-connected="deviceConnected" :symbol-loaded="symbolLoaded" :symbol-error="symbolError" :latest-values="latestValues" />
  <WorkbenchLogPanel v-else-if="panel.type === 'log'" ref="surface" />
  <WorkbenchInformationPanel v-else-if="panel.type === 'information' || panel.type === 'chart'" ref="surface" :panel-id="panel.id" :chart="panel.type === 'chart'" />
  <SerialPortPanel v-else ref="surface" :panel-id="panel.id" :port="panel.source.port || ''" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick, markRaw, provide, inject, defineAsyncComponent } from 'vue'
import type { WorkbenchPanel } from '../../lib/workbenchLayout'
import type { SemanticSurface, SemanticExecutionContext, JsonObject } from '../../lib/frontendControl'
import WaveformViewer from './WaveformViewer.vue'
import SymbolVariablePanel from './SymbolVariablePanel.vue'
import RttChannelPanel from './RttChannelPanel.vue'
import SerialPortPanel from './SerialPortPanel.vue'
import ControlPanel from './ControlPanel.vue'
import CapabilityPanel from './CapabilityPanel.vue'
import WorkbenchToolPanel from './WorkbenchToolPanel.vue'
import WorkbenchLogPanel from './WorkbenchLogPanel.vue'
import WorkbenchInformationPanel from './WorkbenchInformationPanel.vue'
import { guiPanelScopeKey } from '../../lib/guiAutomation'
import { panelSurface } from '../../lib/panelSurface'
import { workbenchActivityKey, activitySourceKey } from '../../lib/workbenchActivity'
import { registerControlRenderer, type ControlWidget } from '../../lib/workbenchControls'
import WorkbenchIndicator from './WorkbenchIndicator.vue'
import WorkbenchNumeric from './WorkbenchNumeric.vue'
registerControlRenderer('indicator', markRaw(WorkbenchIndicator))
registerControlRenderer('numeric', markRaw(WorkbenchNumeric))
const meter = defineAsyncComponent(() => import('./WorkbenchMeter.vue'))
registerControlRenderer('gauge', meter)
registerControlRenderer('bar-meter', meter)
const props = withDefaults(defineProps<{ panel: WorkbenchPanel; deviceConnected: boolean; symbolLoaded: boolean; symbolError?: string; latestValues: Record<string, number>; rtt: JsonObject; snapshotPath?: string | null; active?: boolean; commitWidgets?: (widgets: ControlWidget[]) => void }>(), { active: true })
const emit = defineEmits<{ viewInteraction: []; values: [values: Record<string, number>]; snapshot: [path: string | null]; transfer: [event: { widgetId: string; targetPanelId: string }] }>()
const snapshotForPanel = computed(() => props.snapshotPath && (!props.panel.source.signals?.length || props.panel.source.signals.includes(props.snapshotPath)) ? props.snapshotPath : null)
const surface = ref<SemanticSurface | null>(null)
const root = ref<HTMLElement | null>(null)
const scope = { id: props.panel.id, ownerDocument: () => root.value?.ownerDocument || document, panels: new Map() }
provide(guiPanelScopeKey, scope)
provide(activitySourceKey, props.panel.title)
const activity = inject(workbenchActivityKey, null)
const scopedSurface = panelSurface(root, scope, surface)
function recordNative(event: MouseEvent) {
  const control = event.target instanceof Element ? event.target.closest('button,summary') : null
  if (!event.isTrusted || !control || !root.value?.contains(control) || props.panel.type === 'log') return
  const title = (control.getAttribute('aria-label') || control.getAttribute('title') || control.textContent || '').trim().slice(0, 180)
  if (title) activity?.append({ kind: 'operation', source: props.panel.title, title: (event.isTrusted ? '用户 · ' : 'Agent · ') + title, text: '', status: 'dispatched' })
}
const restoreError = ref('')
watch(surface, async value => {
  if (value && props.panel.view && props.panel.type !== 'watch') {
    await nextTick()
    try { await value.restore?.(props.panel.view); restoreError.value = '' }
    catch (error) { restoreError.value = String(error) }
  }
})
defineExpose({
  catalog: scopedSurface.catalog,
  readValues: scopedSurface.readValues,
  read: () => ({ ...scopedSurface.read(), ...(restoreError.value ? { restore_error: restoreError.value } : {}) }),
  execute: async (action: string, args: JsonObject, context?: SemanticExecutionContext) => {
    emit('viewInteraction')
    try { return await scopedSurface.execute(action, args, context) }
    finally { await nextTick(); emit('viewInteraction') }
  },
})
</script>
<style scoped>
.workbench-panel-body { display:flex; flex-direction:column; flex:1; min-width:0; min-height:0; }
</style>
