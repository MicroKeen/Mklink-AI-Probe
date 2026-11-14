<template>
  <section class="serial-port-panel">
    <header>
      <strong>{{ port || tr('未选择串口', 'No port selected') }}</strong>
      <span>{{ status.ports?.[port] || tr('未打开', 'Closed') }}</span>
      <button :aria-pressed="mode === 'log'" @click="setMode('log')">{{ tr('收发', 'Traffic') }}</button>
      <button :aria-pressed="mode === 'terminal'" @click="setMode('terminal')">{{ tr('终端', 'Terminal') }}</button>
      <button :aria-pressed="paused" @click="setPaused(!paused)">{{ paused ? tr('继续显示', 'Resume display') : tr('暂停显示', 'Pause display') }}</button>
      <button @click="clear">{{ tr('清屏', 'Clear') }}</button>
    </header>
    <LogDisplayControls v-if="mode === 'log'" :id-prefix="instanceId" v-model:mode="format" v-model:show-timestamp="timestamps" />
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="!status.running" class="hint">{{ tr('此面板只查看已有串口会话；请在串口助手中打开端口。', 'This panel follows an existing session. Open the port in Serial Assistant.') }}</p>
    <VirtualLogPanel v-show="mode === 'log'" ref="log" :display-mode="format" :show-timestamp="timestamps" />
    <RttTerminalPanel v-show="mode === 'terminal'" ref="terminal" :input-enabled="writable" @input="terminalInput" />
    <RttTransmitBar :id-prefix="instanceId" :enabled="writable" :settings="settings" :send="send" @settings-change="saveSettings" />
    <small>{{ tr('显示缓冲', 'Display buffer') }} {{ streamTelemetry?.bufferedSamples || 0 }} · drops {{ streamTelemetry?.transportDroppedBatches || 0 }}/{{ streamTelemetry?.backendDroppedBatches || 0 }}</small>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useBinaryStream } from '../../composables/useBinaryStream'
import { tr } from '../../composables/useLanguage'
import { API_BASE } from '../../lib/runtimeEndpoint'
import { loadDesktopSettings, type DesktopSettings } from '../../lib/desktopSettings'
import { loadSerialAssistantSettings, saveSerialAssistantSettings } from '../../lib/serialAssistantSettings'
import { encodeRttTransmit, toHexPayload } from '../../lib/rttTransmit'
import { domainAction, boolArg, requireDomain, type DomainArgs } from '../../lib/domainActions'
import LogDisplayControls, { type LogDisplayMode } from './LogDisplayControls.vue'
import VirtualLogPanel, { type VirtualLogInput } from './VirtualLogPanel.vue'
import RttTerminalPanel from './RttTerminalPanel.vue'
import RttTransmitBar from './RttTransmitBar.vue'

const props = defineProps<{ port: string; panelId?: string }>()
const instanceId = computed(() => props.panelId || `serial-${props.port}`)
type Status = { running?: boolean; ports?: Record<string, string>; session?: string; ymodem?: { active?: boolean; port?: string } }
const status = ref<Status>({}), error = ref('')
const mode = ref<'log' | 'terminal'>('log'), format = ref<LogDisplayMode>('text'), timestamps = ref(true), paused = ref(false)
const log = ref<InstanceType<typeof VirtualLogPanel>>(), terminal = ref<InstanceType<typeof RttTerminalPanel>>()
const serialSettings = ref(loadSerialAssistantSettings(localStorage))
const settings = computed<DesktopSettings>(() => ({ ...loadDesktopSettings(localStorage), ...serialSettings.value }))
const writable = computed(() => Boolean(status.value.running && status.value.ports?.[props.port] === 'open' && !(status.value.ymodem?.active && status.value.ymodem.port === props.port)))
const logStream = useBinaryStream('serial', { capacity: 5000, channelCount: 1, decoderMode: 'serial-log' })
const terminalStream = useBinaryStream('serial', { capacity: 65536, channelCount: 1, decoderMode: 'serial-terminal' })
const streamTelemetry = computed(() => mode.value === 'log' ? logStream.telemetry.value : terminalStream.telemetry.value)
let disposed = false, timer: ReturnType<typeof setTimeout> | undefined, source = ''
let pausedLines: VirtualLogInput[] = [], pausedText = ''
async function request(path: string, body?: object) {
  const response = await fetch(`${API_BASE}/api/dash/serial/${path}`, body === undefined ? undefined : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  const data = await response.json()
  if (!response.ok || data.error) throw new Error(typeof data.detail === 'string' ? data.detail : data.detail?.message || data.error || `HTTP ${response.status}`)
  return data
}
async function refresh() {
  const next = await request('status')
  if (!disposed) { status.value = next; error.value = '' }
}
async function poll() {
  try { await refresh() } catch (caught) { if (!disposed) error.value = String(caught) }
  finally { if (!disposed) timer = setTimeout(poll, 1500) }
}
function attach() {
  // A subscription consumes retained backend history; it never opens the port.
  if (mode.value === 'log') { terminalStream.stop(); logStream.start() }
  else { logStream.stop(); terminalStream.start() }
}
function setMode(value: 'log' | 'terminal') {
  if (mode.value === value) return
  mode.value = value; attach()
  if (value === 'terminal') void nextTick(() => terminal.value?.activate())
}
function clear() { log.value?.clear(); terminal.value?.clear(); pausedLines = []; pausedText = '' }
function accept(port: string, session: string) {
  if (port !== props.port) return false
  const key = `${session}:${port}`
  if (source !== key) { source = key; clear() }
  return true
}
watch(() => props.port, port => {
  source = ''; clear(); logStream.selectSerialPort(port); terminalStream.selectSerialPort(port)
}, { immediate: true })
watch(logStream.serialLines, batch => {
  if (!batch || mode.value !== 'log' || !accept(batch.port, batch.session)) return
  const lines = batch.lines.map(line => ({ time: line.timestampNs, level: line.direction === 'RX' ? 'data' as const : 'warning' as const, label: line.direction, text: line.ascii.replace(/[\r\n]/g, ''), continuesPrevious: line.continuesPrevious, raw: encodeRttTransmit(line.rawHex, 'hex', '') }))
  if (paused.value) pausedLines = [...pausedLines, ...lines].slice(-5000)
  else log.value?.append(lines)
})
watch(terminalStream.serialTerminal, batch => {
  if (!batch || mode.value !== 'terminal' || !accept(batch.port, batch.session)) return
  if (paused.value) pausedText = (pausedText + batch.text).slice(-65536)
  else terminal.value?.write(batch.text)
})
watch([logStream.error, terminalStream.error], ([logError, terminalError]) => { const active = mode.value === 'log' ? logError : terminalError; if (active) error.value = active })
function setPaused(value: boolean) {
  paused.value = value
  if (!value) { log.value?.append(pausedLines); terminal.value?.write(pausedText); pausedLines = []; pausedText = '' }
}
async function send(payload: Uint8Array) {
  requireDomain(writable.value, 'Serial port is not writable')
  const result = await request('send', { port: props.port, data: toHexPayload(payload), hex: true })
  requireDomain(result.ok === true, 'Serial send acknowledgement is missing; do not retry automatically')
}
function terminalInput(data: string) { void send(new TextEncoder().encode(data)).catch(caught => { error.value = String(caught) }) }
function saveSettings(next: DesktopSettings) { serialSettings.value = saveSerialAssistantSettings(localStorage, { transmitMode: next.transmitMode, lineEnding: next.lineEnding, sendHistory: next.sendHistory }) }
function catalog() {
  return [
    domainAction('serial.refresh', 'Read the existing serial session status'),
    domainAction('serial.view.set', 'Set this port panel display preferences', { mode: { type: 'string', enum: ['log', 'terminal'] }, format: { type: 'string', enum: ['text', 'hex'] }, timestamps: boolArg }),
    domainAction('serial.pause', 'Pause or resume this display without closing the port', { paused: boolArg }, ['paused']),
    domainAction('serial.clear', 'Clear this panel display without clearing other panels'),
    domainAction('serial.send', 'Send once through the existing open port', { data: { type: 'string', maxLength: 65536 }, mode: { type: 'string', enum: ['text', 'hex'] }, lineEnding: { type: 'string', enum: ['', '\r', '\n', '\r\n'] } }, ['data'], 'device'),
  ]
}
function read() { return { view: { mode: mode.value, format: format.value, timestamps: timestamps.value, paused: paused.value }, port: props.port, running: Boolean(status.value.running), portStatus: status.value.ports?.[props.port] || 'closed', writable: writable.value, error: error.value } }
function restore(view: DomainArgs) {
  if (view.mode === 'log' || view.mode === 'terminal') setMode(view.mode)
  if (view.format === 'text' || view.format === 'hex') format.value = view.format
  if (typeof view.timestamps === 'boolean') timestamps.value = view.timestamps
  if (typeof view.paused === 'boolean') setPaused(view.paused)
}
async function execute(action: string, args: DomainArgs = {}) {
  requireDomain(!disposed, 'Serial panel is unavailable')
  if (action === 'serial.refresh') await refresh()
  else if (action === 'serial.view.set') restore(args)
  else if (action === 'serial.pause') setPaused(args.paused)
  else if (action === 'serial.clear') clear()
  else if (action === 'serial.send') await send(encodeRttTransmit(args.data, args.mode || 'text', args.lineEnding || ''))
  else throw new Error(`Unknown serial action: ${action}`)
  return read()
}
defineExpose({ catalog, read, execute, restore })
onMounted(() => { attach(); void poll() })
onUnmounted(() => { disposed = true; clearTimeout(timer); logStream.stop(); terminalStream.stop() })
</script>

<style scoped>
.serial-port-panel { display: flex; flex-direction: column; gap: 8px; height: 100%; min-height: 240px; min-width: 0; overflow: hidden; padding: 8px; box-sizing: border-box; }
header { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
header strong { margin-right: auto; }
button { background: var(--surface); color: var(--text); border: 1px solid var(--border); border-radius: 4px; padding: 4px 7px; cursor: pointer; }
button[aria-pressed=true] { color: var(--accent); }
.serial-port-panel :deep(.virtual-log), .serial-port-panel :deep(.rtt-terminal-panel) { flex: 1; min-height: 100px; }
.hint, small { color: var(--muted); font-size: 11px; }
[role=alert] { color: var(--error, #e86f6f); }
</style>
