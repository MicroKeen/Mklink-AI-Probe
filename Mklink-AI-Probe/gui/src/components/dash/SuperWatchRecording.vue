<template>
  <button class="panel-btn" data-testid="sw-record-toggle" :data-gui-directory-picker="!status.active && isTauri() ? '' : undefined" :class="{ active: status.active }" :disabled="busy || (disabled && !status.active)" @click="status.active ? stop() : showPicker()">{{ status.active ? tr('停止记录', 'Stop recording') : tr('开始记录', 'Start recording') }}</button>
  <span v-if="status.path" class="record-result" :title="status.path">{{ status.active ? (status.samples ? tr('记录中', 'Recording') : tr('等待数据', 'Waiting for data')) : tr('已保存', 'Saved') }} · {{ status.samples || 0 }} {{ tr('条', 'samples') }}</span>
  <button v-if="name !== 'Serial' && status.path" class="panel-btn" data-testid="record-convert" :disabled="busy || status.active || status.export_state === 'generating' || status.export_state === 'completed'" @click="convert">{{ status.export_state === 'failed' ? tr('重新转换', 'Retry export') : name === 'SuperWatch' ? tr('转换为 Excel', 'Convert to Excel') : tr('转换为 TXT', 'Convert to TXT') }}</button>
  <span v-if="status.export_state && status.export_state !== 'pending'" class="record-result" data-testid="record-export-status" :title="status.export_path">{{ status.export_state === 'completed' ? tr('转换完成', 'Export ready') : status.export_state === 'failed' ? tr('转换失败', 'Export failed') : tr('转换中', 'Converting') }}{{ status.export_parts ? ` · ${status.export_parts} ${tr('段', 'parts')}` : '' }}</span>
  <span v-if="status.export_error" role="alert" class="record-error">{{ status.export_error }}</span>
  <span v-if="error || status.error" role="alert" class="record-error">{{ error || status.error }}</span>
  <Teleport :to="guiScope?.ownerDocument?.().body || 'body'">
    <dialog ref="dialog" class="record-dialog" :data-gui-panel-owner="guiScope?.id" @keydown.stop>
      <form @submit.prevent="start">
        <h3>{{ tr('保存 ', 'Save ') + name + tr(' 日志', ' log') }}</h3>
        <p>{{ tr('可先开启记录，再开始采集。日志写入后台电脑的所选目录，停止采集也会完成保存。', 'You can enable recording before acquisition. Logs are saved on the backend computer; stopping acquisition also completes recording.') }}</p>
        <div class="record-path"><input v-model="directory" data-testid="sw-record-directory" :aria-label="tr('保存目录', 'Save directory')"><button type="button" @click="browse(directory)">{{ tr('浏览', 'Browse') }}</button></div>
        <div class="record-drives"><button v-for="drive in drives" :key="drive" type="button" @click="browse(drive)">{{ drive }}</button><button type="button" @click="browse(parent)">↑ {{ tr('上一级', 'Parent') }}</button></div>
        <div class="record-folders"><button v-for="dir in dirs" :key="dir.path" type="button" @click="browse(dir.path)">▸ {{ dir.name }}</button></div>
        <p>{{ tr('每次记录保存为一个 .mklog 文件，回放时可直接跳到需要的时间段。', 'Each recording creates one .mklog file. Seek directly to the interval you need.') }}</p>
        <p v-if="name !== 'Serial'">{{ name === 'SuperWatch' ? tr('停止后可手动转换为 Excel，时间和变量分列显示；原始记录保留。', 'After stopping, manually convert to Excel with time and variable columns. The original recording is retained.') : tr('停止后可手动转换为带时间戳的 TXT；原始记录保留。', 'After stopping, manually convert to timestamped TXT. The original recording is retained.') }}</p>
        <p v-if="error" role="alert" class="record-error">{{ error }}</p>
        <footer><button type="button" @click="dialog?.close()">{{ tr('取消', 'Cancel') }}</button><button data-testid="sw-record-confirm" :disabled="busy || !directory.trim()">{{ tr('开始记录', 'Start recording') }}</button></footer>
      </form>
    </dialog>
  </Teleport>
</template>

<script setup lang="ts">
import { requestError } from '../../lib/requestError'
import { frontendFetch as fetch } from '../../lib/frontendControl'

import type { SemanticExecutionContext } from '../../lib/frontendControl'

import { inject } from 'vue'
import { guiPanelScopeKey } from '../../lib/guiAutomation'
const guiScope = inject(guiPanelScopeKey, null)
import { ref, onMounted, onUnmounted } from 'vue'
import { isTauri } from '@tauri-apps/api/core'
import { API_BASE, IS_REMOTE } from '../../lib/runtimeEndpoint'
import { pickDirectory } from '../../lib/filePicker'
import { language } from '../../composables/useLanguage'
import { domainAction, requireDomain, type DomainArgs } from '../../lib/domainActions'
const props = withDefaults(defineProps<{ endpoint?: string; name?: string; channel?: number; disabled?: boolean }>(), {
  endpoint: '/api/dash/superwatch/recording', name: 'SuperWatch', channel: 0, disabled: false,
})
const storageKey = `mklink.${props.name.toLowerCase()}.recordDirectory`
const route = (action: string) => `${props.endpoint}/${action}${props.name === 'SuperWatch' ? '' : '?channel=' + props.channel}`
const emit = defineEmits<{ state: [state: string] }>()
const tr = (zh: string, en: string) => language.value === 'en' ? en : zh
type Recording = { active: boolean; state: string; samples?: number; path?: string; error?: string; export_state?: string; export_path?: string; export_error?: string; export_parts?: number }
const status = ref<Recording>({ active: false, state: 'idle' })
const directory = ref(localStorage.getItem(storageKey) || '')
const dialog = ref<HTMLDialogElement>()
const dirs = ref<Array<{ name: string; path: string }>>([]), drives = ref<string[]>([]), parent = ref('')
const busy = ref(false), error = ref('')
let timer: ReturnType<typeof setTimeout> | undefined, disposed = false, browseGeneration = 0, statusGeneration = 0
async function request(path: string, body?: unknown, context?: SemanticExecutionContext) {
  const response = await (context?.fetch || fetch)(`${API_BASE}${path}`, body === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  const data = await response.json()
  if (!response.ok) {
    const detail = data.detail
    const message = typeof detail === 'string' ? detail : detail?.message
    throw new Error(requestError(detail ?? message, response.status, props.name))
  }
  return data
}
function update(data: Recording) { if (!disposed) { status.value = data; emit('state', data.state) } }
async function poll() {
  const generation = statusGeneration
  try {
    if (!busy.value) {
      const data = await request(route('status'))
      if (generation === statusGeneration) update(data)
    }
  }
  catch (caught) { if (!disposed && generation === statusGeneration) error.value = String(caught) }
  finally { if (!disposed) timer = setTimeout(poll, 1000) }
}
async function browse(path: string) {
  const generation = ++browseGeneration
  try {
    const data = await request(`/api/project-root/browse?path=${encodeURIComponent(path)}`)
    if (generation !== browseGeneration || disposed) return
    directory.value = data.current; parent.value = data.parent; dirs.value = data.dirs; drives.value = data.drives
    error.value = ''
  } catch (caught) { error.value = String(caught) }
}
async function showPicker() {
  if (busy.value) return
  error.value = ''
  if (!isTauri() || IS_REMOTE) {
    // A browser/remote window cannot give the backend a local OS path.
    dialog.value?.showModal()
    void browse(directory.value)
    return
  }
  busy.value = true
  try {
    const selected = await pickDirectory(tr('选择日志保存文件夹', 'Choose a log folder'), directory.value)
    if (!selected || disposed) return
    directory.value = selected
    await start()
  } catch (caught) { error.value = String(caught) }
  finally { busy.value = false }
}
async function start(strict: unknown = false, context?: SemanticExecutionContext) {
  statusGeneration++
  busy.value = true; error.value = ''
  try {
    update(await request(route('start'), { directory: directory.value, ...(props.name === 'SuperWatch' ? {} : { channel: props.channel }) }, context))
    localStorage.setItem(storageKey, directory.value)
    dialog.value?.close()
  } catch (caught) { error.value = String(caught); if (strict === true) throw caught }
  finally { busy.value = false }
}
async function stop(strict: unknown = false, context?: SemanticExecutionContext) {
  statusGeneration++
  busy.value = true; error.value = ''
  try { update(await request(route('stop'), {}, context)) }
  catch (caught) { error.value = String(caught); if (strict === true) throw caught }
  finally { busy.value = false }
}
async function convert() {
  statusGeneration++
  busy.value = true; error.value = ''
  try { update(await request(route('export'), { path: status.value.path, ...(props.name === 'SuperWatch' ? {} : { channel: props.channel }) })) }
  catch (caught) { error.value = String(caught) }
  finally { busy.value = false }
}
onMounted(poll)
onUnmounted(() => { disposed = true; clearTimeout(timer) })
function catalog() {
  return [
    domainAction('recording.refresh', 'Read backend recording progress'),
    domainAction('recording.start', 'Start recording into a backend-accessible directory', { directory: { type: 'string', maxLength: 4096 } }, ['directory'], 'file'),
    domainAction('recording.stop', 'Stop and finalize the current recording', {}, [], 'file'),
  ]
}
function read() { return { active: status.value.active, state: status.value.state, path: status.value.path, busy: busy.value, error: error.value || status.value.error, directory: directory.value } }
async function execute(action: string, args: DomainArgs = {}, context?: SemanticExecutionContext) {
  requireDomain(!disposed && !busy.value, 'Recording controls are unavailable or busy')
  if (action === 'recording.refresh') { update(await request(route('status'))); return { ...read(), progress: { ...status.value } } }
  else if (action === 'recording.start') {
    requireDomain(typeof args.directory === 'string' && args.directory.trim(), 'Recording directory cannot be empty')
    requireDomain(!props.disabled, 'Recording is unavailable while replaying')
    requireDomain(!status.value.active, 'Recording is already active')
    directory.value = args.directory; await start(true, context)
  } else if (action === 'recording.stop') await stop(true, context)
  else throw new Error(`Unknown recording action: ${action}`)
  return read()
}
defineExpose({ catalog, read, execute })
</script>

<style scoped>
.record-dialog { color: var(--text-primary, #ddd); background: var(--bg-secondary, #1b222c); border: 1px solid var(--border, #465366); border-radius: 8px; width: min(620px, 90vw); padding: 20px; }
.record-dialog::backdrop { background: #0008; }
.record-dialog p { font-size: 12px; opacity: .8; }
.record-dialog button, .record-dialog input { color: inherit; background: transparent; border: 1px solid #465366; border-radius: 4px; padding: 6px 10px; }
.record-path, .record-drives, footer { display: flex; gap: 8px; margin: 10px 0; }
.record-path input { flex: 1; min-width: 0; }
.record-folders { height: 220px; overflow: auto; display: flex; flex-direction: column; gap: 4px; }
.record-folders button { text-align: left; }
footer { justify-content: flex-end; }
.record-error { color: #ff8585; max-width: 320px; font-size: 12px; }
.record-result { font-size: 12px; white-space: nowrap; }
</style>
