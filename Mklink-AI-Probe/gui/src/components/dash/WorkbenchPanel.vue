<template>
  <p v-if="restoreError" role="alert">{{ restoreError }}</p>
  <WaveformViewer v-if="panel.type === 'watch'" ref="surface" :panel-id="panel.id" :signals="panel.source.signals?.length ? panel.source.signals : undefined" :view-state="panel.view"
    mode="SuperWatch" :device-connected="deviceConnected" :array-snapshot-path="snapshotForPanel" @latest-values="values => emit('values', values)" />
  <SymbolVariablePanel v-else-if="panel.type === 'variables'" ref="surface" :panel-id="panel.id" :view-paths="panel.source.signals"
    :device-connected="deviceConnected" :symbol-loaded="symbolLoaded" :symbol-error="symbolError" :latest-values="latestValues" :subscribe-values="true" :snapshot-path="snapshotPath" @snapshot-change="path => emit('snapshot', path)" />
  <RttChannelPanel v-else-if="panel.type === 'rtt'" ref="surface" :panel-id="panel.id" :channel="panel.source.channel || 0"
    :running="rtt.running === true" :send-enabled="rtt.running === true && !rtt.runtime_error && rtt.down_buffers?.some((item: any) => item.channel === (panel.source.channel || 0) && item.active) === true" :session="rtt.session" :channel-status="rtt.channel_status?.[String(panel.source.channel || 0)]" />
  <SerialPortPanel v-else ref="surface" :panel-id="panel.id" :port="panel.source.port || ''" />
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import type { WorkbenchPanel } from '../../lib/workbenchLayout'
import type { SemanticSurface, JsonObject } from '../../lib/frontendControl'
import WaveformViewer from './WaveformViewer.vue'
import SymbolVariablePanel from './SymbolVariablePanel.vue'
import RttChannelPanel from './RttChannelPanel.vue'
import SerialPortPanel from './SerialPortPanel.vue'
const props = defineProps<{ panel: WorkbenchPanel; deviceConnected: boolean; symbolLoaded: boolean; symbolError?: string; latestValues: Record<string, number>; rtt: JsonObject; snapshotPath?: string | null }>()
const emit = defineEmits<{ values: [values: Record<string, number>]; snapshot: [path: string | null] }>()
const snapshotForPanel = computed(() => props.snapshotPath && (!props.panel.source.signals?.length || props.panel.source.signals.includes(props.snapshotPath)) ? props.snapshotPath : null)
const surface = ref<SemanticSurface | null>(null)
const restoreError = ref('')
watch(surface, async value => {
  if (value && props.panel.view && props.panel.type !== 'watch') {
    await nextTick()
    try { await value.restore?.(props.panel.view); restoreError.value = '' }
    catch (error) { restoreError.value = String(error) }
  }
})
defineExpose({
  catalog: () => surface.value?.catalog?.() || [],
  read: () => ({ ...(surface.value?.read?.() || { ready: false }), ...(restoreError.value ? { restore_error: restoreError.value } : {}) }),
  execute: async (action: string, args: JsonObject) => {
    if (!surface.value) throw new Error('Panel is still loading')
    const result = await surface.value.execute(action, args)
    await nextTick()
    return result
  },
})
</script>
