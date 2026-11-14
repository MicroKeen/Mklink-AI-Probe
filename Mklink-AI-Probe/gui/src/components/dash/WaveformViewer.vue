<template>
  <div
    ref="container"
    class="waveform-viewer"
    :class="{ 'superwatch-desktop': props.mode === 'SuperWatch' }"
  ></div>
  <Teleport v-if="recordHost" :to="recordHost"><SuperWatchRecording ref="recordingControl" @state="updateRecordingLabel" /></Teleport>
  <Teleport v-if="actionsHost" :to="actionsHost"><slot name="actions" /></Teleport>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useBinaryStream } from '../../composables/useBinaryStream'
import { RenderScheduler } from '../../lib/stream/renderScheduler'
import type { WorkerOutput } from '../../workers/streamDecoder.worker'
import '../../assets/rtt_viewer.css'
import i18nUrl from '../../assets/rtt_i18n.js?url'
import viewerUrl from '../../assets/rtt_viewer.js?url'
import { DESKTOP_SETTINGS_STORAGE_KEY } from '../../lib/desktopSettings'
import { signalFormula, compileSignalFormula } from '../../lib/signalFormula'
import { language } from '../../composables/useLanguage'
import { API_BASE } from '../../lib/runtimeEndpoint'
import { saveTextFile, saveImageFile } from '../../lib/downloadTextFile'
import { mountReplayButton, type ReplayControl } from '../../../../mklink/static/superwatch_replay.js'
import '../../../../mklink/static/superwatch_replay.css'
import SuperWatchRecording from './SuperWatchRecording.vue'

const props = defineProps<{
  mode: 'SuperWatch' | 'VOFA'
  deviceConnected: boolean
  panelId?: string
  signals?: string[]
  viewState?: Record<string, unknown>
  hiddenChannels?: ReadonlySet<string>
  arraySnapshotPath?: string | null
}>()

const emit = defineEmits<{
  'latest-values': [values: Record<string, number>]
  'replay-channels': [channels: string[] | null]
  'visibility-change': [path: string, visible: boolean]
}>()

const viewerKey = props.panelId || props.mode
const getViewer = () => (window as any).__waveformViewers?.[viewerKey]
const recordingControl = ref<any>()
const viewError = ref('')
const container = ref<HTMLDivElement>()
let mountedContainer: HTMLDivElement | undefined
const recordHost = ref<HTMLElement>()
const actionsHost = ref<HTMLElement>()
function updateRecordingLabel(state: string) {
  const summary = container.value?.querySelector('.watch-log-controls summary')
  if (!summary) return
  summary.removeAttribute('data-i18n')
  const en = language.value === 'en'
  summary.textContent = (en ? 'Logs' : '日志') + (state === 'recording' ? (en ? ' · Recording' : ' · 记录中') : state === 'failed' ? (en ? ' · Error' : ' · 记录失败') : '')
}
const binary = useBinaryStream(
  props.mode === 'VOFA' ? 'vofa' : 'superwatch',
  { capacity: props.mode === 'VOFA' ? 10000 : 50000, channelCount: 1 },
)
let vofaChannels: Array<Record<string, unknown>> = []
let vofaChannelSignature: string | null = null
let pendingBatch: Extract<WorkerOutput, { type: 'waveform-batch' }> | null = null
let visibleRequestId = 0
let historyRequestId = 0
let visibleRequestInFlight: number | null = null
let visibleRangePending = false
let visibleRangePendingInteractive = false
const interactiveVisibleRequests = new Set<number>()
let previousTransportPhase = 'stopped'
let statusPollTimer: ReturnType<typeof setTimeout> | null = null
let statusPollGeneration = 0
let latestVofaStatus: Record<string, unknown> | null = null
let arraySnapshotTimer: ReturnType<typeof setTimeout> | null = null
let arraySnapshotGeneration = 0
let disposed = false
let disposeReplay: ReplayControl | null = null
let pendingView = props.viewState
const replayFileRequests = new Set<AbortController>()
async function loadReplayFile(path: string): Promise<File> {
  const controller = new AbortController()
  replayFileRequests.add(controller)
  try {
    const response = await fetch(`${API_BASE}/api/runtime/frontend/replay-file`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path }), signal: controller.signal,
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail?.message || error.detail || response.statusText)
    }
    const blob = await response.blob()
    if (disposed) throw new Error('Waveform panel is closed')
    return new File([blob], path.split(/[\\/]/).pop() || 'capture.csv', { type: blob.type })
  } finally { replayFileRequests.delete(controller) }
}
function requestLatestVisibleRange(interactive = false): void {
  if (visibleRequestInFlight !== null) {
    visibleRangePending = true
    visibleRangePendingInteractive ||= interactive
    return
  }
  const viewer = getViewer()
  if (viewer?.isReplaying?.()) return
  const range = viewer?.getBinaryVisibleRange?.()
  if (!range) return
  const { start, end, pixelWidth } = range
  if (![start, end, pixelWidth].every(Number.isFinite) || pixelWidth < 1) return
  visibleRangePending = false
  visibleRangePendingInteractive = false
  visibleRequestInFlight = ++visibleRequestId
  if (interactive) interactiveVisibleRequests.add(visibleRequestInFlight)
  const formulas = viewer.getFormulas?.()
  if (props.mode === 'SuperWatch' && Number.isFinite(range.gapThresholdMs)) binary.requestVisibleRange(visibleRequestInFlight, start, end, pixelWidth, formulas?.some(Boolean) ? formulas : undefined, range.gapThresholdMs)
  else if (formulas?.some(Boolean)) binary.requestVisibleRange(visibleRequestInFlight, start, end, pixelWidth, formulas)
  else binary.requestVisibleRange(visibleRequestInFlight, start, end, pixelWidth)
}

function resetVisibleRangeRequests(): void {
  visibleRequestId++
  visibleRequestInFlight = null
  visibleRangePending = false
  visibleRangePendingInteractive = false
  interactiveVisibleRequests.clear()
}

const vofaScheduler = new RenderScheduler(() => requestLatestVisibleRange(false))

function attachSuperwatchRequesters(viewer: any): void {
  viewer?.setBinaryCapacityRequester?.((capacity: number) => binary.resizeWaveform(capacity))
  if (props.mode !== 'SuperWatch' || !viewer) return
  viewer.setBinaryHistoryRequester?.(() => {
    binary.requestHistorySnapshot?.(++historyRequestId)
  })
  viewer.setBinaryDetailRequester?.((enabled: boolean) => {
    binary.setWaveformDetail?.(enabled)
  })
  viewer.setBinaryVisibleRangeRequester?.(() => requestLatestVisibleRange(true))
  viewer.setBinaryFreezeRequester?.((frozen: boolean) => {
    resetVisibleRangeRequests()
    binary.setWaveformFrozen?.(frozen)
  })
}

function channelSignature(channels: readonly Record<string, unknown>[]): string {
  return JSON.stringify(channels.map((channel, index) => [
    channel.name ?? channel.addr ?? channel.address ?? index,
    channel.type ?? 'float', channel.size ?? 4,
    channel.addr ?? channel.address ?? null, channel.unit ?? '',
  ]))
}

function applyVofaChannels(channels: readonly Record<string, unknown>[]): void {
  if (disposed) return
  const signature = channelSignature(channels)
  if (signature === vofaChannelSignature) return
  vofaChannelSignature = signature
  vofaChannels = channels.map(channel => ({ ...channel }))
  resetVisibleRangeRequests()
  pendingBatch = null
  if (props.mode === 'VOFA') binary.configure(Math.max(1, channels.length))
  const viewer = getViewer()
  viewer?.configureBinaryChannels?.(vofaChannels)
  applyHiddenChannels()
}

function applyHiddenChannels(): void {
  const names = [...(props.hiddenChannels ?? [])].sort()
  const viewer = getViewer()
  if (viewer?.isReplaying?.()) viewer.setReplayHiddenChannels?.(names)
  else viewer?.setHiddenChannels?.(names)
}

function onVisibility(event: Event) {
  const {path, visible} = (event as CustomEvent).detail
  emit('visibility-change', path, visible)
}
function onReplay(event: Event) {
  const detail = (event as CustomEvent).detail
  emit('replay-channels', detail.channels)
  emit('latest-values', detail.values)
}

function stopArraySnapshotPolling(): void {
  arraySnapshotGeneration += 1
  if (arraySnapshotTimer !== null) {
    clearTimeout(arraySnapshotTimer)
    arraySnapshotTimer = null
  }
}

async function pollArraySnapshot(generation: number): Promise<void> {
  if (disposed || props.mode !== 'SuperWatch' || !props.arraySnapshotPath || !props.deviceConnected) return
  try {
    const response = await fetch(`${API_BASE}/api/dash/superwatch/array-snapshot`)
    const payload = await response.json().catch(() => ({}))
    if (response.ok && payload?.snapshot?.name === props.arraySnapshotPath) {
      ;getViewer()?.setArraySnapshot?.(payload.snapshot)
    } else {
      ;getViewer()?.setArraySnapshot?.(null)
    }
  } catch {
    // The binary stream remains independent when the optional snapshot poll fails.
  }
  if (!disposed && generation === arraySnapshotGeneration && props.arraySnapshotPath) {
    arraySnapshotTimer = setTimeout(() => {
      arraySnapshotTimer = null
      void pollArraySnapshot(generation)
    }, 50)
  }
}

function startArraySnapshotPolling(): void {
  stopArraySnapshotPolling()
  if (props.mode !== 'SuperWatch' || !props.arraySnapshotPath || !props.deviceConnected) {
    ;getViewer()?.setArraySnapshot?.(null)
    return
  }
  const generation = arraySnapshotGeneration
  void pollArraySnapshot(generation)
}

function onVofaChannels(event: Event): void {
  const channels = (event as CustomEvent<unknown>).detail
  if (!Array.isArray(channels)) return
  applyVofaChannels(channels as Array<Record<string, unknown>>)
}

function resetVofaSession(): void {
  if (disposed) return
  resetVisibleRangeRequests()
  pendingBatch = null
  binary.reset()
  ;getViewer()?.resetBinaryStream?.()
}

function stopVofaStatusPolling(): void {
  statusPollGeneration++
  if (statusPollTimer !== null) {
    clearTimeout(statusPollTimer)
    statusPollTimer = null
  }
}

async function pollVofaStatus(generation: number, startTransport: boolean): Promise<void> {
  let status: Record<string, unknown> | null = null
  try {
    const response = await fetch(`${API_BASE}/api/dash/${props.mode === 'VOFA' ? 'vofa' : 'superwatch'}/status`)
    status = response.ok ? await response.json() : null
  } catch { /* retry on the bounded cadence below */ }
  if (disposed || generation !== statusPollGeneration) return
  if (status) {
    latestVofaStatus = status
    if (startTransport) {
      const channels = props.mode === 'VOFA' ? status.channels : status.items
      applyVofaChannels(Array.isArray(channels) ? channels : [])
    }
    ;getViewer()?.updateAcquisitionStatus?.(status)
  }
  if (startTransport) binary.start()
  statusPollTimer = setTimeout(() => {
    statusPollTimer = null
    void pollVofaStatus(generation, false)
  }, 1_000)
}

function startVofaStatusPolling(startTransport: boolean): void {
  if (disposed) return
  stopVofaStatusPolling()
  const generation = statusPollGeneration
  void pollVofaStatus(generation, startTransport)
}

function onVofaStreamState(event: Event): void {
  const state = (event as CustomEvent<unknown>).detail
  if (state === 'running') {
    binary.stop()
    resetVofaSession()
    binary.start()
    startVofaStatusPolling(false)
  } else if (state === 'stopped') {
    pendingBatch = null
    // Stop the shared producer, not this window's subscription. Another GUI
    // can start it again; retain history while still receiving status/metadata.
    if (props.mode === 'SuperWatch') {
      startVofaStatusPolling(false)
      return
    }
    binary.stop()
    stopVofaStatusPolling()
  }
}

watch(() => binary.waveformBatch.value, batch => {
  if (!batch) return
  if (getViewer()?.isReplaying?.()) return
  pendingBatch = batch
  if (
    props.mode === 'SuperWatch'
    && !binary.waveformSummary
    && batch.itemCount > 0
    && batch.channelCount === vofaChannels.length
  ) {
    const values = new Float32Array(batch.values)
    const offset = (batch.itemCount - 1) * batch.channelCount
    const latest: Record<string, number> = {}
    for (let channel = 0; channel < batch.channelCount; channel += 1) {
      const name = String(vofaChannels[channel]?.name ?? '')
      const value = values[offset + channel]
      if (name && Number.isFinite(value)) latest[name] = value
    }
    emit('latest-values', latest)
  }
  const viewer = getViewer()
  if (viewer?.acceptBinaryBatch) {
    viewer.acceptBinaryBatch(batch, vofaChannels)
    pendingBatch = null
  }
  if (props.mode !== 'SuperWatch') {
    vofaScheduler?.recordCollection(batch.itemCount)
    vofaScheduler?.invalidate('data')
  }
})

watch(() => binary.waveformSummary?.value, summary => {
  if (!summary || props.mode !== 'SuperWatch') return
  if (getViewer()?.isReplaying?.()) return
  const values = new Float32Array(summary.latestValues)
  if (summary.channelCount === vofaChannels.length && values.length === summary.channelCount) {
    const latest: Record<string, number> = {}
    for (let channel = 0; channel < summary.channelCount; channel += 1) {
      const name = String(vofaChannels[channel]?.name ?? '')
      if (name && Number.isFinite(values[channel])) latest[name] = values[channel]
    }
    emit('latest-values', latest)
  }
  ;getViewer()?.acceptBinarySummary?.(summary, vofaChannels)
  vofaScheduler?.recordCollection(summary.collectedItemCount)
  vofaScheduler?.invalidate('data')
})

watch(() => binary.historySnapshot?.value, snapshot => {
  if (!snapshot || props.mode !== 'SuperWatch') return
  ;getViewer()?.exportBinaryHistorySnapshot?.(snapshot)
})

watch(() => binary.envelope.value, envelope => {
  if (!envelope || envelope.requestId !== visibleRequestInFlight) return
  visibleRequestInFlight = null
  const renderWhilePaused = interactiveVisibleRequests.delete(envelope.requestId)
  ;getViewer()?.renderBinaryEnvelope?.(
    envelope, renderWhilePaused,
  )
  if (visibleRangePending) {
    const interactive = visibleRangePendingInteractive
    requestLatestVisibleRange(interactive)
  }
})

watch(() => binary.superwatchMetadata.value, metadata => {
  if (!metadata || props.mode !== 'SuperWatch') return
  applyVofaChannels(metadata.channels)
})

watch([
  () => binary.state.value,
  () => binary.telemetry.value,
  () => binary.error.value,
], ([state, telemetry, error]) => {
  if (!state) return
  if (state.phase === 'reconnecting' && previousTransportPhase !== 'reconnecting') {
    resetVofaSession()
  }
  previousTransportPhase = state.phase
  ;getViewer()?.updateBinaryHealth?.({
    phase: state.phase,
    reconnectDelayMs: state.reconnectDelayMs,
    bufferedSamples: telemetry?.bufferedSamples ?? 0,
    transportDroppedBatches: telemetry?.transportDroppedBatches ?? 0,
    backendDroppedBatches: telemetry?.backendDroppedBatches ?? 0,
    backendDroppedItems: telemetry?.backendDroppedItems ?? 0,
    error: state.phase === 'connected' || state.phase === 'stopped' ? null : error,
  })
})

onMounted(() => {
  if (!container.value) return
  const el = container.value
  mountedContainer = el
  el.addEventListener('mklink:replay', onReplay)
  el.addEventListener('mklink:visibility', onVisibility)

  const saveViewerFile = (filename: string, text: string) => saveTextFile(filename, text)
  ;(window as any).__MKLINK_SAVE_FILE__ = saveViewerFile
  ;(window as any).__MKLINK_SAVE_BLOB__ = saveImageFile

  // 1. Inject HTML template
  el.innerHTML = buildTemplate(props.mode)
  if (props.mode === 'SuperWatch') {
    compactSuperwatchControls(el)
    recordHost.value = el.querySelector('.watch-log-menu') as HTMLElement
    disposeReplay = mountReplayButton(el.querySelector('.watch-log-menu') as HTMLElement, { language: language.value, viewer: getViewer, loadFile: loadReplayFile })
  }

  // 2. Inject CONFIG + load scripts
  injectScripts(el, props.mode)
  {
    if (props.mode === 'VOFA') {
      window.addEventListener('mklink:vofa-channels', onVofaChannels)
    }
    window.addEventListener('mklink:vofa-stream-state', onVofaStreamState)
    vofaScheduler?.start()
    startVofaStatusPolling(true)
    startArraySnapshotPolling()
    const viewer = getViewer()
    attachSuperwatchRequesters(viewer)
  }
})

watch(() => props.deviceConnected, (val) => {
  const viewers = (window as any).__waveformViewers
  if (viewers?.[viewerKey]?.setDeviceConnected) viewers[viewerKey].setDeviceConnected(val)
})

watch(() => props.hiddenChannels, applyHiddenChannels)
watch(() => props.signals, names => getViewer()?.setSignals?.(names), { deep: true })
watch([() => props.arraySnapshotPath, () => props.deviceConnected], startArraySnapshotPolling)

watch(language, value => {
  getViewer()?.setLanguage?.(value)
})

onUnmounted(() => {
  const el = mountedContainer
  el?.querySelectorAll('script').forEach(script => {
    if ((script as any).__mklinkContext) (script as any).__mklinkContext.cancelled = true
  })
  el?.removeEventListener('mklink:replay', onReplay)
  el?.removeEventListener('mklink:visibility', onVisibility)
  disposeReplay?.()
  disposed = true
  replayFileRequests.forEach(controller => controller.abort())
  replayFileRequests.clear()
  stopVofaStatusPolling()
  stopArraySnapshotPolling()
  binary.stop()
  vofaScheduler?.dispose()
  window.removeEventListener('mklink:vofa-channels', onVofaChannels)
  window.removeEventListener('mklink:vofa-stream-state', onVofaStreamState)
  // Close EventSource if running
  try {
    const viewers = (window as any).__waveformViewers
    viewers?.[viewerKey]?.dispose?.()
    if (viewers) delete viewers[viewerKey]
  } catch { /* ignore */ }
  // Clear DOM
  if (el) el.innerHTML = ''
  mountedContainer = undefined
})

function compactSuperwatchControls(el: HTMLElement): void {
  // Remove UI before the viewer binds handlers; VOFA retains its raw terminal.
  for (const id of ['raw-log-panel', 'btn-save-project', 'btn-load-project', 'project-load-input']) el.querySelector('#' + id)?.remove()
  el.querySelector('[data-i18n="help_rawlog"]')?.parentElement?.remove()
  const actions = el.querySelector('.header-actions')!
  const row = document.createElement('div')
  row.className = 'watch-toolbar-row'
  const control = el.querySelector('#control-toolbar')!
  control.before(row)
  row.append(control, actions)
  for (const id of ['conn-status', 'transport-state-badge', 'transport-health-badge', 'sample-rate-badge']) {
    control.append(el.querySelector('#' + id)!)
  }
  const logs = document.createElement('details')
  logs.className = 'watch-log-controls'
  logs.innerHTML = '<summary data-i18n="logs">日志</summary><div class="watch-log-menu"></div>'
  el.querySelector('#btn-export-csv')?.remove()
  actions.append(logs)
  const trigger = el.querySelector('#trigger-toolbar')!
  const dialog = document.createElement('dialog')
  dialog.className = 'watch-trigger-dialog'
  dialog.setAttribute('aria-label', '触发设置 / Trigger settings')
  dialog.innerHTML = '<header><strong data-i18n="trigger_settings">触发设置</strong><button type="button" class="panel-btn" data-i18n="close">关闭</button></header>'
  dialog.append(trigger)
  el.append(dialog)
  const open = document.createElement('button')
  open.type = 'button'; open.className = 'panel-btn'; open.dataset.testid = 'open-trigger-settings'
  open.dataset.i18n = 'trigger_settings'; open.textContent = '触发设置'
  open.onclick = () => dialog.showModal()
  dialog.querySelector('button')!.onclick = () => dialog.close()
  dialog.addEventListener('keydown', event => event.stopPropagation())
  actions.prepend(open)
  const extra = document.createElement('span')
  extra.className = 'watch-extra-actions'
  actions.prepend(extra)
  actionsHost.value = extra
}

function buildTemplate(mode: string): string {
  const minPoints = mode === 'SuperWatch' ? 50000 : 2
  const maxPoints = mode === 'SuperWatch' ? 50000 : 10000
  const intervalValue = mode === 'SuperWatch' ? '0.001' : '0'
  const intervalMinimum = mode === 'SuperWatch' ? '0.000001' : '0'
  const intervalStep = mode === 'SuperWatch' ? '0.000001' : '0.001'
  return `
<header>
  <div class="header-status">
    <h1>MKLink ${mode}</h1>
    <span id="mode-badge" class="badge badge-mode">${mode}</span>
    <span id="conn-status" class="badge badge-ok" data-i18n="live">live</span>
    <span id="pts-count" class="badge badge-info">0 pts</span>
    <span id="sample-rate-badge" class="badge badge-info">-- Hz</span>
    <span id="transport-state-badge" class="badge badge-info">transport stopped</span>
    <span id="transport-health-badge" class="badge badge-info">transport 0 / backend 0/0 / buffer 0</span>
  </div>
  <div class="header-actions">
    <button id="btn-cursor-toggle" class="panel-btn" data-i18n-title="cursors_tip" data-i18n="cursors">Cursors</button>
    <button id="btn-cursor-mode" class="panel-btn" style="display:none;" data-i18n-title="cursor_mode_tip">Time</button>
    <button id="btn-save-project" class="panel-btn" data-i18n-title="save_project_tip" data-i18n="save">Save</button>
    <button id="btn-load-project" class="panel-btn" data-i18n-title="load_project_tip" data-i18n="load">Load</button>
    <button id="btn-thresholds" class="panel-btn" data-i18n-title="thresholds_tip" data-i18n="thresholds">Thresholds</button>
    <button id="btn-export-csv" class="panel-btn" data-i18n-title="export_csv_tip">CSV</button>
    <button id="btn-export-png" class="panel-btn" data-i18n-title="export_png_tip">PNG</button>
    <button id="btn-help" class="panel-btn" data-i18n-title="help_tip">?</button>
    <input id="project-load-input" class="hidden-file-input" type="file" accept="application/json,.json">
  </div>
</header>

<div id="control-toolbar">
  <button id="btn-start" class="ctrl-btn active" data-i18n="start">Start</button>
  <button id="btn-pause" class="ctrl-btn" data-i18n="pause">Pause</button>
  <button id="btn-stop" class="ctrl-btn danger" data-i18n="stop">Stop</button>
  <span id="collection-status-badge" class="status-running" data-i18n="running">Running</span>
  <div class="ctrl-sep"></div>
  <label data-i18n="buffer">Buffer</label>
  <input type="number" id="buffer-input" value="${maxPoints}" min="${minPoints}" max="1000000" step="1">
  <span class="buffer-unit">pts/ch</span>
  <span id="buffer-memory-estimate" class="buffer-memory-estimate" data-i18n-title="buffer_memory_tip">~0 MB</span>
  <button id="btn-apply-buffer" class="ctrl-btn" data-i18n="apply">Apply</button>
  <div class="ctrl-sep"></div>
  <div id="interval-group">
    <label data-i18n="interval">Interval</label>
    <input type="number" id="interval-input" value="${intervalValue}" step="${intervalStep}" min="${intervalMinimum}" max="60" aria-describedby="interval-error">
    <span class="interval-unit">s</span>
    <button id="btn-apply-interval" class="ctrl-btn" data-i18n="apply">Apply</button>
  </div>
</div>
<div id="interval-error" role="alert" hidden></div>
<div id="trigger-toolbar">
  <button id="trigger-enable-btn" data-i18n="trigger">Trigger</button>
  <span id="trigger-state-badge" class="trigger-state-idle" data-i18n="idle">Idle</span>
  <div class="trigger-sep"></div>
  <label data-i18n="source">Source</label>
  <select id="trigger-source"><option value="">--</option></select>
  <div class="trigger-sep"></div>
  <label data-i18n="edge">Edge</label>
  <select id="trigger-edge">
    <option value="rising" data-i18n="rising">Rising</option>
    <option value="falling" data-i18n="falling">Falling</option>
    <option value="both" data-i18n="both">Both</option>
  </select>
  <div class="trigger-sep"></div>
  <label data-i18n="level">Level</label>
  <input type="number" id="trigger-level" value="0" step="0.1">
  <div class="trigger-sep"></div>
  <label data-i18n="mode">Mode</label>
  <select id="trigger-mode">
    <option value="auto" data-i18n="auto">Auto</option>
    <option value="normal" data-i18n="normal">Normal</option>
    <option value="single" data-i18n="single">Single</option>
  </select>
  <div class="trigger-sep"></div>
  <label data-i18n="pretrig">Pre-trig</label>
  <input type="number" id="trigger-pretrig" value="1000" min="10" max="50000" step="1">
  <div class="trigger-sep"></div>
  <button id="trigger-force-btn" data-i18n="force_trigger">Force Trigger</button>
</div>

<div id="var-selector"></div>

<main id="debug-main">
  <section id="chart-watch-wrap">
    <div id="enum-tooltip"></div>
    <div id="chart-wrap">
      <canvas id="chart"></canvas>
      <button
        id="chart-legend-toggle"
        type="button"
        aria-expanded="false"
        aria-controls="chart-legend"
        data-i18n-title="show_channel_legend_tip"
        title="显示通道列表"
      ><span aria-hidden="true">&#9776;</span></button>
      <div id="chart-legend" aria-label="Channel layout" aria-hidden="true"></div>
      <div id="split-panel-control" class="split-panel-control" hidden>
        <span class="split-panel-label" data-i18n="split_panel">独立通道</span>
        <span id="split-panel-name" class="split-panel-name"></span>
        <button
          id="split-panel-merge"
          type="button"
          data-i18n="merge_channel"
          data-i18n-title="merge_channel_tip"
          title="将此通道合并回主面板"
        >合并</button>
      </div>
      <div id="y-axis-hit" class="axis-hit-region axis-hit-y" data-i18n-title="y_axis_tip" title="纵轴：滚轮缩放；按住鼠标左键拖动；双击恢复自动范围"></div>
      <div id="x-axis-hit" class="axis-hit-region axis-hit-x" data-i18n-title="x_axis_tip" title="横轴：滚轮缩放；按住鼠标左键拖动；双击恢复默认视图"></div>
      <div id="tooltip"></div>
      <div id="cursor-a" class="cursor-line" style="display:none;"></div>
      <div id="cursor-b" class="cursor-line" style="display:none;"></div>
      <div id="cursor-measure-panel" style="display:none;"></div>
    </div>
    <div id="watch-resizer"></div>
    <div id="watch-panel">
      <div class="panel-header">
        <div class="panel-title">
          <span class="panel-dot"></span>
          <span data-i18n="watch">监视</span>
        </div>
        <div class="panel-actions">
          <span id="watch-count" class="panel-count">0 ch</span>
          <button id="watch-columns-btn" class="panel-btn" data-i18n-title="columns_tip" data-i18n="columns">列</button>
          <button id="watch-collapse" class="panel-btn panel-btn-close" data-i18n-title="collapse_watch" title="折叠监视面板">&#x2715;</button>
        </div>
      </div>
      <div id="watch-columns-menu" class="columns-menu" aria-hidden="true"></div>
      <div id="watch-table-wrap">
        <table id="watch-table">
          <thead>
            <tr id="watch-table-head-row"></tr>
          </thead>
          <tbody id="watch-tbody"></tbody>
        </table>
      </div>
    </div>
  </section>

  <div id="minimap-wrap">
    <canvas id="minimap-canvas"></canvas>
    <div id="minimap-viewport"></div>
    <div id="cursor-readout"></div>
  </div>

  <section id="raw-log-panel" data-open="false">
    <div class="panel-resizer" title="Drag to resize"></div>
    <div class="panel-header">
      <div class="panel-title">
        <span class="panel-dot"></span>
        <span data-i18n="raw_log">原始日志</span>
      </div>
      <div class="panel-actions">
        <span id="raw-log-count" class="panel-count">0 lines</span>
        <button id="raw-log-save" class="panel-btn" data-i18n-title="save_raw_log_tip" data-i18n="save">保存</button>
        <button id="raw-log-clear" class="panel-btn" data-i18n-title="clear_log" data-i18n="clear">清除</button>
        <button id="raw-log-close" class="panel-btn panel-btn-close" data-i18n-title="close_panel" title="关闭面板">&#x2715;</button>
      </div>
    </div>
    <pre id="raw-log"></pre>
  </section>
  <section id="inspector-panel" aria-hidden="true"></section>
</main>

<div id="threshold-overlay" class="config-overlay" aria-hidden="true">
  <div class="config-dialog" role="dialog" aria-modal="true" aria-labelledby="threshold-title">
    <h2 id="threshold-title" data-i18n="thresholds">阈值</h2>
    <div class="config-grid">
      <div class="config-field full">
        <label for="threshold-channel" data-i18n="channel">通道</label>
        <select id="threshold-channel"></select>
      </div>
      <div class="config-field">
        <label for="threshold-warn-low" data-i18n="warn_low">警告下限</label>
        <input id="threshold-warn-low" type="number" step="0.1">
      </div>
      <div class="config-field">
        <label for="threshold-warn-high" data-i18n="warn_high">警告上限</label>
        <input id="threshold-warn-high" type="number" step="0.1">
      </div>
      <div class="config-field">
        <label for="threshold-alarm-low" data-i18n="alarm_low">报警下限</label>
        <input id="threshold-alarm-low" type="number" step="0.1">
      </div>
      <div class="config-field">
        <label for="threshold-alarm-high" data-i18n="alarm_high">报警上限</label>
        <input id="threshold-alarm-high" type="number" step="0.1">
      </div>
    </div>
    <div class="config-actions">
      <button id="threshold-clear" class="panel-btn" data-i18n="clear">清除</button>
      <button id="threshold-cancel" class="panel-btn" data-i18n="cancel">取消</button>
      <button id="threshold-apply" class="panel-btn" data-i18n="apply">应用</button>
    </div>
  </div>
</div>
<div id="shutdown-overlay">
  <h2 data-i18n="server_shutdown">服务器已关闭</h2>
  <p data-i18n="server_stopped_msg">可视化服务器已停止。</p>
  <p data-i18n="close_tab_msg">可以关闭此标签页。</p>
</div>

<div id="help-overlay" aria-hidden="true">
  <div id="help-modal" role="dialog" aria-modal="true" aria-labelledby="help-modal-title">
    <div id="help-modal-header">
      <h2 id="help-modal-title" data-i18n="help_title">使用说明</h2>
      <button id="help-close-btn" data-i18n-title="close_esc" title="关闭 (Esc)">&times;</button>
    </div>
    <div id="help-modal-body">
      <div class="help-section"><h3 data-i18n="help_chart">图表交互</h3><ul id="help-chart-list"></ul></div>
      <div class="help-section"><h3 data-i18n="${mode === 'SuperWatch' ? 'help_sw_variables' : 'help_var_selector'}">变量选择器</h3><ul id="help-var-list"></ul></div>
      <div class="help-section"><h3 data-i18n="help_trigger_sys">触发系统</h3><ul id="help-trigger-list"></ul></div>
      <div class="help-section"><h3 data-i18n="${mode === 'SuperWatch' ? 'help_sw_sampling' : 'help_watch_panel'}">Watch 面板</h3><ul id="help-watch-list"></ul></div>
      <div class="help-section"><h3 data-i18n="help_minimap">缩略图</h3><ul id="help-minimap-list"></ul></div>
      <div class="help-section"><h3 data-i18n="help_cursors">测量光标</h3><ul id="help-cursors-list"></ul></div>
      <div class="help-section"><h3 data-i18n="help_export">数据导出</h3><ul id="help-export-list"></ul></div>
      <div class="help-section"><h3 data-i18n="help_shortcuts">键盘快捷键</h3><table class="help-kbd-table" id="help-kbd-table"></table></div>
      <div class="help-section"><h3 data-i18n="help_rawlog">Raw Log 面板</h3><ul id="help-rawlog-list"></ul></div>
      <div class="help-section"><h3 data-i18n="help_pause_resume">暂停/恢复</h3><ul id="help-pause-list"></ul></div>
    </div>
  </div>
</div>`
}

function injectScripts(el: HTMLDivElement, mode: string) {
  ;(window as any).__mklinkSignalFormula = signalFormula
  ;(window as any).__mklinkCompileSignalFormula = compileSignalFormula
  const config = {
    minPoints: mode === 'SuperWatch' ? 50000 : 2,
    maxPoints: mode === 'SuperWatch' ? 50000 : 10000,
    title: `MKLink ${mode}`, mode, panelId: viewerKey,
    lang: language.value, apiBase: API_BASE,
    viewerSettingsKey: DESKTOP_SETTINGS_STORAGE_KEY + '.waveform.' + viewerKey,
    deviceConnected: props.deviceConnected,
  }
  const i18nScript = document.createElement('script')
  i18nScript.src = i18nUrl
  i18nScript.onload = () => {
    if (disposed) return
    loadViewerScript(el, config)
  }
  el.appendChild(i18nScript)
}

function loadViewerScript(el: HTMLDivElement, config: Record<string, unknown>) {
  const viewerScript = document.createElement('script')
  ;(viewerScript as any).__mklinkContext = { root: el, config }
  viewerScript.src = viewerUrl
  viewerScript.onload = async () => {
    if (disposed) return
    const viewer = getViewer()
    if (viewer) {
      viewer.setDeviceConnected?.(props.deviceConnected)
      attachSuperwatchRequesters(viewer)
      viewer.configureBinaryChannels?.(vofaChannels)
      viewer.setSignals?.(props.signals)
      applyHiddenChannels()
      if (latestVofaStatus) viewer.updateAcquisitionStatus?.(latestVofaStatus)
      if (pendingBatch) { viewer.acceptBinaryBatch?.(pendingBatch, vofaChannels); pendingBatch = null }
      if (pendingView) {
        try { await viewer.restore?.(pendingView) } catch (error) { viewError.value = String(error) }
        pendingView = undefined
      }
    }
  }
  el.appendChild(viewerScript)
}

function catalog() {
  return [...(getViewer()?.catalog?.() || []), ...(disposeReplay?.catalog() || []), ...(recordingControl.value?.catalog?.() || [])]
}
function read() {
  const replay = disposeReplay?.read()
  // Playback position is available in the action result; omit its live clock from
  // the normal configuration snapshot used for optimistic action revisions.
  return { ...(getViewer()?.read?.() || { panelId: viewerKey, ready: false }),
    error: viewError.value || undefined,
    replay: replay && { loaded: replay.loaded, playing: replay.playing, speed: replay.speed, filename: replay.filename, duration: replay.duration },
    recording: recordingControl.value?.read?.() }
}
function validate(action: string, args: Record<string, unknown> = {}) {
  if (action.startsWith('recording.')) return recordingControl.value?.validate?.(action, args) || { valid: true }
  if (action.startsWith('waveform.replay.')) {
    if (!disposeReplay) throw new Error('Replay controls are not ready')
    return disposeReplay.validate(action, args)
  }
  if (!getViewer()?.validate) throw new Error('Waveform panel is not ready')
  return getViewer().validate(action, args)
}
async function execute(action: string, args: Record<string, unknown> = {}) {
  validate(action, args)
  if (action.startsWith('recording.')) {
    if (!recordingControl.value?.execute) throw new Error('Recording controls are not ready')
    return await recordingControl.value.execute(action, args)
  }
  if (action.startsWith('waveform.replay.')) return await disposeReplay!.execute(action, args)
  return await getViewer().execute(action, args)
}
async function restore(view: Record<string, unknown>) {
  if (getViewer()?.restore) {
    try { const result = await getViewer().restore(view); viewError.value = ''; return result }
    catch (error) { viewError.value = String(error); throw error }
  }
  pendingView = view
  return { pending: true }
}
defineExpose({ catalog, read, validate, execute, restore })

</script>

<style scoped>
.waveform-viewer {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
</style>
