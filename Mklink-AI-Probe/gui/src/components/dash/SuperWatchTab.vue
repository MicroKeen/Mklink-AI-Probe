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
        <button type="button" class="open-symbol" data-testid="superwatch-open-symbol" data-gui-file-picker
          :disabled="IS_REMOTE || loadingSymbols"
          :title="tr('加载程序符号，并恢复此 AXF/ELF 已保存的观测变量', 'Load program symbols and restore the watches saved for this AXF/ELF')"
          @click="loadSymbolFile"><FolderOpen :size="14" aria-hidden="true" />{{ tr('打开 AXF / ELF', 'Open AXF / ELF') }}</button>
      </div>
    <SymbolVariablePanel file-picker-in-toolbar ref="symbolPanel" v-show="!replayChannels && source === 'variables'"
      :panel-id="panelId" :view-paths="viewPaths"
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
      <PeripheralWatchPanel ref="peripheralPanel" v-show="!replayChannels && source === 'peripherals'" :device-connected="deviceConnected" :latest-values="latestValues" />
    </div>
    <div class="workspace-resizer" role="separator" tabindex="0" aria-orientation="vertical"
      :aria-valuenow="panelWidth" :aria-valuemin="280" :aria-valuemax="maxPanelWidth()"
      :aria-label="tr('调整变量目录宽度', 'Resize variable catalog')"
      :title="tr('拖动或使用方向键调整目录宽度', 'Drag or use arrow keys to resize catalog')"
      @mousedown.prevent="startResize" @keydown="resizeByKey"></div>
    <div class="waveform-pane">
      <div v-if="!panelId && watchProfile.profile.value?.path" class="profile-status" :title="watchProfile.profile.value.path">
        {{ watchProfile.saving.value ? tr('配置保存中', 'Saving settings') : tr('随 AXF/ELF 保存配置', 'Settings beside AXF/ELF') }}
        <span v-if="watchProfile.error.value" role="alert">{{ tr('配置未保存：', 'Settings not saved: ') }}{{ watchProfile.error.value }}</span>
        <span v-if="watchProfile.profile.value.missing.length">{{ tr('当前符号中未找到：', 'Unavailable symbols: ') }}{{ watchProfile.profile.value.missing.join(', ') }}</span>
        <button class="panel-btn" @click="watchProfile.load()">{{ tr('刷新配置', 'Reload settings') }}</button>
      </div>
      <div v-if="panelId" class="panel-profile-actions">
        <button class="panel-btn" @click="profileAction('load')">{{ tr('读取 AXF/ELF 配置', 'Load AXF/ELF settings') }}</button>
        <button class="panel-btn" :disabled="watchProfile.saving.value" @click="profileAction('save')">{{ tr('保存到 AXF/ELF 配置', 'Save AXF/ELF settings') }}</button>
        <span v-if="profileMessage" role="status">{{ profileMessage }}</span>
      </div>
      <WaveformViewer
        ref="waveformPanel" :panel-id="panelId" :signals="viewPaths"
        mode="SuperWatch"
        :device-connected="deviceConnected"
        :hidden-channels="replayChannels ? replayHidden : hiddenChannels"
        :array-snapshot-path="snapshotPath"
        @latest-values="latestValues = $event"
        @replay-channels="setReplayChannels"
        @visibility-change="(path, visible) => replayChannels ? setReplayVisibility(path, visible) : setChannelVisibility(path, visible)"
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
import { FolderOpen } from '@lucide/vue'
import { useDashboardSetup } from '../../composables/useDashboardSetup'
import { frontendFetch as fetch } from '../../lib/frontendControl'

import type { SemanticExecutionContext } from '../../lib/frontendControl'

import { onBeforeUnmount, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import SymbolVariablePanel from './SymbolVariablePanel.vue'
import PeripheralWatchPanel from './PeripheralWatchPanel.vue'
import WaveformViewer from './WaveformViewer.vue'
import { tr } from '../../composables/useLanguage'
import { API_BASE, IS_REMOTE } from '../../lib/runtimeEndpoint'
import { DESKTOP_SETTINGS_STORAGE_KEY } from '../../lib/desktopSettings'
import { domainAction, pathArg, boolArg, requireDomain, type DomainArgs } from '../../lib/domainActions'
import { flushWatchProfile, useWatchProfile } from '../../composables/useWatchProfile'

const props = withDefaults(defineProps<{
  deviceConnected: boolean
  symbolLoaded?: boolean
  symbolError?: string
  panelId?: string
  viewPaths?: string[]
}>(), {
  symbolLoaded: true,
  symbolError: '',
})

const { loadSymbolFile, loadingSymbols } = useDashboardSetup()
const focusMode = ref(false)
const symbolPanel = ref<InstanceType<typeof SymbolVariablePanel>>()
const peripheralPanel = ref<InstanceType<typeof PeripheralWatchPanel>>()
const waveformPanel = ref<InstanceType<typeof WaveformViewer>>()
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
const watchProfile = useWatchProfile()
const profileMessage = ref('')
async function sharedProfile(action: 'load' | 'save', context?: SemanticExecutionContext) {
  const viewer = action === 'save' ? waveformPanel.value?.exportProfile() : null
  await watchProfile.load()
  const profile = watchProfile.profile.value
  if (!profile?.path || profile.available === false || watchProfile.error.value) throw new Error(watchProfile.error.value || 'Load an AXF/ELF file before using shared settings')
  if (action === 'load') {
    restore(profile.layout.layout)
    waveformPanel.value?.loadProfile(profile.viewer.viewer, profile.path)
  } else {
    await watchProfile.save('viewer', viewer, context)
    if (watchProfile.error.value) throw new Error(watchProfile.error.value)
    await watchProfile.save('layout', { panelWidth: panelWidth.value, source: source.value, hidden: [...hiddenChannels.value] }, context)
    if (watchProfile.error.value) throw new Error(watchProfile.error.value)
  }
  profileMessage.value = action === 'load' ? tr('已读取共享配置', 'Shared settings loaded') : tr('共享配置已保存', 'Shared settings saved')
}
async function profileAction(action: 'load' | 'save') { try { await sharedProfile(action) } catch (error) { profileMessage.value = String(error) } }

let profileTimer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  if (props.panelId) return
  void watchProfile.load(); profileTimer = setInterval(() => void watchProfile.load(), 2000)
})
onBeforeUnmount(() => { clearInterval(profileTimer); if (!props.panelId) void flushWatchProfile() })
const layoutStorageKey = DESKTOP_SETTINGS_STORAGE_KEY + '.superwatch-layout' + (props.panelId ? '.' + props.panelId : '')
try {
  const saved = JSON.parse(localStorage.getItem(layoutStorageKey) || '{}')
  if (Number.isFinite(saved?.panelWidth)) panelWidth.value = Math.max(280, saved.panelWidth)
  if (saved?.source === 'variables' || saved?.source === 'peripherals') source.value = saved.source
  if (Array.isArray(saved?.hidden)) hiddenChannels.value = new Set(saved.hidden.filter((name: unknown) => typeof name === 'string').slice(0, 256))
} catch { /* Local preferences are optional. */ }
watch(() => watchProfile.profile.value?.layout.revision, () => {
  if (props.panelId) return
  const saved = watchProfile.profile.value?.layout.layout
  if (!saved || !watchProfile.profile.value?.path || watchProfile.profile.value.available === false) return
  panelWidth.value = clampPanelWidth(saved.panelWidth)
  source.value = saved.source
  hiddenChannels.value = new Set(saved.hidden)
}, { immediate: true })
watch([panelWidth, source, hiddenChannels], () => {
  if (!props.panelId) watchProfile.scheduleLayout({ panelWidth: panelWidth.value, source: source.value, hidden: [...hiddenChannels.value] })
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
  try {
    const response = await fetch(`${API_BASE}/api/dash/superwatch/array-snapshot`)
    if (!response.ok) return
    const payload = await response.json()
    snapshotPath.value = payload?.snapshot?.name ?? null
  } catch {
    // The dashboard can mount before the API is ready; retry on reconnect.
  }
}

onMounted(() => {
  void loadSnapshotSelection()
  window.addEventListener('mklink:watch-profile-loaded', loadSnapshotSelection)
})
onUnmounted(() => window.removeEventListener('mklink:watch-profile-loaded', loadSnapshotSelection))
watch(() => props.deviceConnected, loadSnapshotSelection)
function catalog() {
  return [
    ...(props.panelId ? [domainAction('superwatch.profile.load', 'Explicitly load shared AXF/ELF display settings into this panel'), domainAction('superwatch.profile.save', 'Explicitly save this panel display settings beside the AXF/ELF file', {}, [], 'file')] : []),
    domainAction('superwatch.catalog.set', 'Select the variables or peripheral catalog', { source: { type: 'string', enum: ['variables', 'peripherals'] } }, ['source']),
    domainAction('superwatch.focus', 'Focus or restore this workspace', { focused: boolArg }, ['focused']),
    domainAction('superwatch.width', 'Set the variable catalog width', { width: { type: 'number', minimum: 280, maximum: 10000 } }, ['width']),
    domainAction('superwatch.visibility', 'Show or hide a curve without changing acquisition', { path: pathArg, visible: boolArg }, ['path', 'visible']),
    ...(symbolPanel.value?.catalog?.() || []), ...(peripheralPanel.value?.catalog?.() || []), ...(waveformPanel.value?.catalog?.() || []),
  ]
}
function read() {
  const symbols = symbolPanel.value?.read?.(), peripherals = peripheralPanel.value?.read?.(), waveform = waveformPanel.value?.read?.()
  const view = { source: source.value, panelWidth: panelWidth.value, hidden: [...hiddenChannels.value], symbols: symbols?.view, peripherals: peripherals?.view, waveform: waveform?.view }
  return { view, source: source.value, focused: focusMode.value, panelWidth: panelWidth.value, hidden: [...hiddenChannels.value], snapshotPath: snapshotPath.value, symbols, peripherals, waveform }
}
async function execute(action: string, args: DomainArgs = {}, context?: SemanticExecutionContext) {
  if (action === 'superwatch.profile.load') await sharedProfile('load', context)
  else if (action === 'superwatch.profile.save') await sharedProfile('save', context)
  else if (action === 'superwatch.catalog.set') source.value = args.source
  else if (action === 'superwatch.focus') focusMode.value = args.focused
  else if (action === 'superwatch.width') panelWidth.value = clampPanelWidth(args.width)
  else if (action === 'superwatch.visibility') {
    if (replayChannels.value) { requireDomain(replayChannels.value.includes(args.path), 'Unknown replay channel'); setReplayVisibility(args.path, args.visible) }
    else { requireDomain(symbolPanel.value?.hasSignal?.(args.path) || peripheralPanel.value?.hasSignal?.(args.path), 'Signal is not selected'); setChannelVisibility(args.path, args.visible) }
  } else {
    const target = [symbolPanel.value, peripheralPanel.value, waveformPanel.value].find(panel => panel?.catalog?.().some(item => item.name === action))
    requireDomain(target, `Action is unavailable: ${action}`)
    return target.execute(action, args, context)
  }
  return read()
}
function restore(view: DomainArgs) {
  if (view.source === 'variables' || view.source === 'peripherals') source.value = view.source
  if (Number.isFinite(view.panelWidth)) panelWidth.value = clampPanelWidth(view.panelWidth)
  if (Array.isArray(view.hidden)) hiddenChannels.value = new Set(view.hidden.filter((path: unknown) => typeof path === 'string').slice(0, 500))
  if (view.symbols) symbolPanel.value?.restore(view.symbols)
  if (view.peripherals) peripheralPanel.value?.restore(view.peripherals)
  if (view.waveform) waveformPanel.value?.restore(view.waveform)
}
defineExpose({ catalog, read, execute, restore })
</script>

<style scoped>
.panel-profile-actions { display:flex; align-items:center; flex-wrap:wrap; gap:8px; padding:8px 0; font-size:12px; }
.focused { position:fixed; inset:0; z-index:900; background:var(--bg); height:100dvh !important; padding:8px; box-sizing:border-box; }
.workspace-actions { display:inline-flex; flex-shrink:0; }

.watch-catalog-pane { display: flex; flex-direction: column; min-width: 0; min-height: 0; overflow: hidden; }
.replay-catalog { padding: 12px; overflow: auto; }
.replay-catalog label { display: flex; align-items: center; gap: 8px; padding: 12px 0; border-bottom: 1px solid var(--border); overflow-wrap: anywhere; }
.replay-catalog small { display: block; color: var(--accent); margin-top: 4px; }
.watch-catalog-pane :deep(.symbol-panel) { flex: 1; min-height: 0; }
.watch-source-tabs { display: flex; border-bottom: 1px solid var(--border); flex: 0 0 auto; }
.watch-source-tabs button { flex: 1; padding: 10px; border: 0; background: var(--surface); color: var(--muted); cursor: pointer; }
.watch-source-tabs button.open-symbol { flex: 0 0 auto; display: inline-flex; align-items: center; gap: 4px; white-space: nowrap; color: var(--accent); }
.watch-source-tabs button.open-symbol:disabled { cursor: default; opacity: .55; }
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
.profile-status { display:flex; flex-wrap:wrap; align-items:center; gap:8px; padding:4px 8px; color:var(--muted); font-size:12px; }
.profile-status [role="alert"] { color:var(--danger, #f87e66); }

@media (max-width: 760px) {
  .superwatch-workspace {
    grid-template-columns: 1fr !important;
    grid-template-rows: minmax(220px, 38vh) minmax(360px, 1fr);
    overflow: auto;
  }
  .workspace-resizer { display: none; }
}
</style>
