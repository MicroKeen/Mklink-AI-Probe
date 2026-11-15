<template>
  <section class="capability-panel">
    <label>查找能力<input v-model="query" type="search" placeholder="memory / fault / recording…" /></label>
    <label>MKLink 能力<select :value="selected" :disabled="busy" @change="userExecute('capability.select', { name: ($event.target as HTMLSelectElement).value })">
      <option value="">选择运行时公布的能力</option>
      <option v-for="item in filtered" :key="item.name" :value="item.name" :disabled="!item.available">{{ item.name }}</option>
    </select></label>
    <template v-if="current">
      <p>{{ current.description }}</p>
      <details><summary>参数与前置条件</summary><p>沿用原业务检查；设备写入、供电和任务操作需要本次授权。返回任务 ID 表示已提交，需查询原任务终态。</p><pre>{{ JSON.stringify({ parameters: current.parameters, requestBody: current.requestBody }, null, 2) }}</pre></details>
      <label>参数 JSON<textarea v-model="draft" :disabled="busy" maxlength="32768" spellcheck="false" /></label>
      <div class="capability-actions"><button type="button" :disabled="busy || !current.available || status === 'unknown'" @click="userExecute('mklink.' + selected, { arguments_json: draft })">{{ busy ? '执行中…' : '执行能力' }}</button>
        <button type="button" :disabled="result === undefined || busy" @click="userExecute('capability.export', {})">保存结果 JSON</button></div>
    </template>
    <p v-if="error" role="alert">{{ error }}</p>
    <p role="status">{{ status }}<span v-if="operationId"> · {{ operationId }}</span></p>
    <p v-if="status === 'unknown'">结果未确认；先查询原任务或状态，不自动重放。</p>
    <pre v-if="result !== undefined" class="capability-result">{{ resultText }}</pre>
  </section>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, ref } from 'vue'
import { API_BASE } from '../../lib/runtimeEndpoint'
import { objectSchema, type JsonObject } from '../../lib/frontendControl'
import { bindingHostKey } from '../../lib/workbenchBindings'
import { saveTextFile } from '../../lib/downloadTextFile'

const props = defineProps<{ panelId: string }>()
const host = inject(bindingHostKey, null)
const capabilities = ref<JsonObject[]>([]), selected = ref(''), query = ref(''), draft = ref('{}')
const busy = ref(false), error = ref(''), status = ref('idle'), operationId = ref('')
const result = ref<any>(undefined)
const current = computed(() => capabilities.value.find(item => item.name === selected.value))
const filtered = computed(() => capabilities.value.filter(item => item.name === selected.value || (item.name + ' ' + item.description).toLowerCase().includes(query.value.toLowerCase())))
const resultText = computed(() => JSON.stringify(result.value, null, 2)?.slice(0, 16384) || '')
function summary(value: any) {
  const text = JSON.stringify(value)
  return text === undefined || text.length <= 8192 ? value : { truncated: true, characters: text.length, preview: text.slice(0, 8192) }
}
async function request(path: string, body?: JsonObject) {
  const response = await fetch(`${API_BASE}/api/runtime/capabilities${path}`, { method: body ? 'POST' : 'GET', signal: AbortSignal.timeout(body ? 120000 : 5000),
    ...(body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}) })
  const payload = await response.json()
  if (!response.ok) throw Object.assign(new Error(typeof payload.detail === 'string' ? payload.detail : JSON.stringify(payload.detail || payload)), { status: response.status })
  return payload
}
onMounted(async () => {
  try { capabilities.value = (await request('')).capabilities }
  catch (cause) { error.value = String(cause) }
})
function catalog() {
  const items = capabilities.value
  return [
    ...(items.length ? [{ name: 'capability.select', description: 'Choose an advertised MKLink capability without executing it', args: objectSchema({ name: { type: 'string', enum: items.map(item => item.name) } }), effect: 'view' }] : []),
    ...(current.value?.available ? [{ name: 'mklink.' + selected.value, description: current.value.description,
      args: objectSchema({ arguments_json: { type: 'string', maxLength: 32768, description: 'JSON arguments; contract ' + current.value.revision } }, []), effect: current.value.effect }] : []),
    { name: 'capability.export', description: 'Save the actual result as JSON; does not rerun the operation', args: objectSchema(), effect: 'file' },
  ]
}
function read() { return { ready: capabilities.value.length > 0, count: capabilities.value.length, view: { capability: selected.value },
  selected: current.value, status: status.value, operation_id: operationId.value || null, result: summary(result.value) } }
async function execute(action: string, args: JsonObject) {
  if (busy.value) throw new Error('An operation is still running')
  if (action === 'capability.select') {
    if (!capabilities.value.some(item => item.name === args.name)) throw new Error('Capability is unavailable')
    selected.value = args.name; draft.value = '{}'; error.value = ''; status.value = 'idle'; result.value = undefined; operationId.value = ''
    return read()
  }
  if (action === 'capability.export') {
    if (result.value === undefined) throw new Error('There is no operation result to save')
    return { saved: await saveTextFile(`mklink-${selected.value}-${operationId.value}.json`, JSON.stringify(result.value, null, 2)) }
  }
  if (!current.value?.available || action !== 'mklink.' + selected.value) throw new Error('Capability changed; read the current selection')
  if (status.value === 'unknown') throw new Error('Query the original operation before explicitly selecting a capability again')
  const argumentsValue = JSON.parse(args.arguments_json ?? '{}')
  if (!argumentsValue || typeof argumentsValue !== 'object' || Array.isArray(argumentsValue)) throw new Error('Arguments must be a JSON object')
  busy.value = true; error.value = ''; status.value = 'running'; operationId.value = crypto.randomUUID(); result.value = undefined
  try {
    result.value = await request('/call', { capability: selected.value, arguments: argumentsValue })
    status.value = result.value?.job_id || result.value?.runtime_job_id
      ? result.value.state || result.value.status || 'submitted' : 'completed'
    return { operation_id: operationId.value, status: status.value, result: summary(result.value) }
  } catch (cause) {
    const httpStatus = (cause as { status?: number }).status
    status.value = !httpStatus || httpStatus >= 500 ? 'unknown' : 'failed'; error.value = String(cause)
    throw Object.assign(cause as Error, { unknown: status.value === 'unknown' })
  } finally { busy.value = false }
}
async function userExecute(action: string, args: JsonObject) {
  try {
    if (!host) throw new Error('Workbench control is not connected')
    await host.invoke(props.panelId, action, args)
  } catch (cause) { error.value = String(cause) }
}
function restore(view: JsonObject) { if (typeof view.capability === 'string') selected.value = view.capability }
defineExpose({ catalog, read, execute, restore })
</script>

<style scoped>
.capability-panel { display:flex; flex-direction:column; gap:8px; padding:10px; min-width:0; overflow:auto; }
label { display:flex; flex-direction:column; gap:4px; font-size:12px; } input,select,textarea { min-width:0; width:100%; box-sizing:border-box; }
textarea { min-height:100px; font-family:monospace; resize:vertical; } p { margin:0; font-size:12px; overflow-wrap:anywhere; }
pre { white-space:pre-wrap; overflow-wrap:anywhere; font-size:11px; max-height:300px; overflow:auto; } .capability-actions { display:flex; gap:8px; flex-wrap:wrap; }
</style>
