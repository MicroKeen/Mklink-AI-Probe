<template>
  <div ref="workspace" class="superwatch-workspace" :class="{ focused: focusMode }" :style="{ gridTemplateColumns: `${panelWidth}px 5px minmax(0, 1fr)` }">
    <div class="watch-catalog-pane">
      <div v-if="replayChannels" class="replay-catalog">
        <strong>{{ tr('日志通道', 'Log channels') }}</strong>
        <label v-for="name in replayChannels" :key="name">
          <input type="checkbox" :checked="!replayHidden.has(name)" @change="setReplayVisibility(name, ($event.target as HTMLInputElement).checked)">
          <span>{{ name }}<small>{{ latestValues[name] ?? '—' }}</small></span>
        </label>
      </div>
      <div v-show="!replayChannels" class="watch-source-tabs">
        <button :class="{ active: source === 'variables' }" @click="source = 'variables'">{{ tr('程序变量', 'Variables') }}</button>
        <button :class="{ active: source === 'peripherals' }" @click="source = 'peripherals'">{{ tr('芯片外设', 'Peripherals') }}</button>
      </div>
    <SymbolVariablePanel v-show="!replayChannels && source === 'variables'"
      :device-connected="deviceConnected"
      :symbol-loaded="symbolLoaded"
      :symbol-error="symbolError"
      :latest-values="latestValues"
      :hidden-channels="hiddenChannels"
      :snapshot-path="snapshotPath"
      @visibility-change="setChannelVisibility"
      @selection-removed="clearChannelVisibility"
      @snapshot-change="snapshotPath = $event"
    />
      <PeripheralWatchPanel v-show="!replayChannels && source === 'peripherals'" :device-connected="deviceConnected" :latest-values="latestValues" />
    </div>
    <div class="workspace-resizer" role="separator" tabindex="0" aria-orientation="vertical"
      :aria-valuenow="panelWidth" :aria-valuemin="280" :aria-valuemax="maxPanelWidth()"
      :aria-label="tr('调整变量目录宽度', 'Resize variable catalog')"
      :title="tr('拖动或使用方向键调整目录宽度', 'Drag or use arrow keys to resize catalog')"
      @mousedown.prevent="startResize" @keydown="resizeByKey"></div>
    <div class="waveform-pane">
      <WaveformViewer
        mode="SuperWatch"
        :device-connected="deviceConnected"
        :hidden-channels="replayChannels ? replayHidden : hiddenChannels"
        :array-snapshot-path="snapshotPath"
        @latest-values="latestValues = $event"
        @replay-channels="setReplayChannels"
      >
        <template #actions>
          <span class="workspace-actions">
            <button type="button" class="panel-btn" @click="focusMode = !focusMode">{{ focusMode ? tr('退出专注', 'Exit focus') : tr('展开工作区', 'Focus workspace') }}</button>
          </span>
        </template>
      </WaveformViewer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import SymbolVariablePanel from './SymbolVariablePanel.vue'
import PeripheralWatchPanel from './PeripheralWatchPanel.vue'
import WaveformViewer from './WaveformViewer.vue'
import { tr } from '../../composables/useLanguage'
import { API_BASE } from '../../lib/runtimeEndpoint'
import { DESKTOP_SETTINGS_STORAGE_KEY } from '../../lib/desktopSettings'

const props = withDefaults(defineProps<{
  deviceConnected: boolean
  symbolLoaded?: boolean
  symbolError?: string
}>(), {
  symbolLoaded: true,
  symbolError: '',
})

const focusMode = ref(false)
function exitFocus(event: KeyboardEvent) { if (event.key === 'Escape') focusMode.value = false }
onMounted(() => window.addEventListener('keydown', exitFocus))
onUnmounted(() => window.removeEventListener('keydown', exitFocus))
const panelWidth = ref(340)
const workspace = ref<HTMLElement | null>(null)
let workspaceObserver: ResizeObserver | undefined
const source = ref('variables')
const latestValues = shallowRef<Record<string, number | boolean>>({})
const replayChannels = shallowRef<string[] | null>(null)
const replayHidden = shallowRef(new Set<string>())
function setReplayChannels(channels: string[] | null) {
  if (!replayChannels.value || !channels) replayHidden.value = new Set()
  replayChannels.value = channels
}
function setReplayVisibility(name: string, visible: boolean) {
  const hidden = new Set(replayHidden.value)
  if (visible) hidden.delete(name); else hidden.add(name)
  replayHidden.value = hidden
}
const hiddenChannels = shallowRef(new Set<string>())
const layoutStorageKey = DESKTOP_SETTINGS_STORAGE_KEY + '.superwatch-layout'
try {
  const saved = JSON.parse(localStorage.getItem(layoutStorageKey) || '{}')
  if (Number.isFinite(saved?.panelWidth)) panelWidth.value = Math.max(280, saved.panelWidth)
  if (saved?.source === 'variables' || saved?.source === 'peripherals') source.value = saved.source
  if (Array.isArray(saved?.hidden)) hiddenChannels.value = new Set(saved.hidden.filter((name: unknown) => typeof name === 'string').slice(0, 256))
} catch { /* Local preferences are optional. */ }
watch([panelWidth, source, hiddenChannels], () => {
  try {
    localStorage.setItem(layoutStorageKey, JSON.stringify({ panelWidth: panelWidth.value, source: source.value,
      hidden: [...hiddenChannels.value] }))
  } catch { /* Do not block the shared viewer when storage is unavailable. */ }
})
const snapshotPath = ref<string | null>(null)
let resizeStartX = 0
let resizeStartWidth = 0

function setChannelVisibility(path: string, visible: boolean): void {
  const next = new Set(hiddenChannels.value)
  if (visible) next.delete(path)
  else next.add(path)
  hiddenChannels.value = next
}

function clearChannelVisibility(path: string): void {
  if (!hiddenChannels.value.has(path)) return
  const next = new Set(hiddenChannels.value)
  next.delete(path)
  hiddenChannels.value = next
}

function startResize(event: MouseEvent): void {
  resizeStartX = event.clientX
  resizeStartWidth = panelWidth.value
  document.addEventListener('mousemove', resizePanel)
  document.addEventListener('mouseup', stopResize, { once: true })
}

function resizePanel(event: MouseEvent): void {
  panelWidth.value = clampPanelWidth(resizeStartWidth + event.clientX - resizeStartX)
}

function maxPanelWidth(): number {
  // Leave a small usable waveform pane; large screens can use their full width.
  return Math.max(280, (workspace.value?.clientWidth || window.innerWidth) - 165)
}

function clampPanelWidth(width: number): number {
  return Math.min(maxPanelWidth(), Math.max(280, width))
}

function resizeByKey(event: KeyboardEvent): void {
  if (event.key === 'ArrowLeft') panelWidth.value = clampPanelWidth(panelWidth.value - 40)
  else if (event.key === 'ArrowRight') panelWidth.value = clampPanelWidth(panelWidth.value + 40)
  else if (event.key === 'Home') panelWidth.value = 280
  else if (event.key === 'End') panelWidth.value = maxPanelWidth()
  else return
  event.preventDefault()
}

onMounted(() => {
  workspaceObserver = new ResizeObserver(() => { panelWidth.value = clampPanelWidth(panelWidth.value) })
  if (workspace.value) workspaceObserver.observe(workspace.value)
})

function stopResize(): void {
  document.removeEventListener('mousemove', resizePanel)
}

onUnmounted(() => {
  workspaceObserver?.disconnect()
  document.removeEventListener('mousemove', resizePanel)
  document.removeEventListener('mouseup', stopResize)
})

async function loadSnapshotSelection(): Promise<void> {
  if (!props.deviceConnected) {
    snapshotPath.value = null
    return
  }
  try {
    const response = await fetch(`${API_BASE}/api/dash/superwatch/array-snapshot`)
    if (!response.ok) return
    const payload = await response.json()
    snapshotPath.value = payload?.snapshot?.name ?? null
  } catch {
    // The dashboard can mount before the API is ready; retry on reconnect.
  }
}

onMounted(loadSnapshotSelection)
watch(() => props.deviceConnected, loadSnapshotSelection)
</script>

<style scoped>
.focused { position:fixed; inset:0; z-index:900; background:var(--bg); height:100dvh !important; padding:8px; box-sizing:border-box; }
.workspace-actions { display:inline-flex; flex-shrink:0; }

.watch-catalog-pane { display: flex; flex-direction: column; min-width: 0; min-height: 0; overflow: hidden; }
.replay-catalog { padding: 12px; overflow: auto; }
.replay-catalog label { display: flex; align-items: center; gap: 8px; padding: 12px 0; border-bottom: 1px solid var(--border); overflow-wrap: anywhere; }
.replay-catalog small { display: block; color: var(--accent); margin-top: 4px; }
.watch-catalog-pane :deep(.symbol-panel) { flex: 1; min-height: 0; }
.watch-source-tabs { display: flex; border-bottom: 1px solid var(--border); flex: 0 0 auto; }
.watch-source-tabs button { flex: 1; padding: 10px; border: 0; background: var(--surface); color: var(--muted); cursor: pointer; }
.watch-source-tabs button.active { color: var(--accent); box-shadow: inset 0 -2px var(--accent); }
.superwatch-workspace {
  display: grid;
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}
.workspace-resizer {
  width: 5px;
  background: var(--border);
  cursor: col-resize;
}
.workspace-resizer:hover { background: var(--accent); }
.waveform-pane {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}
.waveform-pane > :last-child { flex: 1; min-height: 0; }

@media (max-width: 760px) {
  .superwatch-workspace {
    grid-template-columns: 1fr !important;
    grid-template-rows: minmax(220px, 38vh) minmax(360px, 1fr);
    overflow: auto;
  }
  .workspace-resizer { display: none; }
}
</style>
