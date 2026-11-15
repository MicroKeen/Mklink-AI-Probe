<template>
  <section class="capability-panel">
    <details :open="!current" class="operation-picker"><summary>{{ current ? '更换操作' : '选择操作' }}</summary>
      <label>查找操作<input v-model="query" type="search" placeholder="查找设备、变量、记录…" /></label>
      <label>操作<select :value="selected" :disabled="busy" @change="userExecute('capability.select', { name: ($event.target as HTMLSelectElement).value })">
        <option value="">选择操作</option>
        <option v-for="item in filtered" :key="item.name" :value="item.name" :disabled="!item.available">{{ operationLabel(item) }}</option>
      </select></label>
    </details>
    <template v-if="current">
      <h3>{{ operationLabel(current) }}</h3>
      <form @submit.prevent="submitForm">
        <template v-for="field in form.fields" :key="field.key">
          <label v-if="field.kind !== 'guided'">{{ label(field.key) }}{{ field.required ? ' *' : '' }}
            <select v-if="field.kind === 'boolean' || field.kind === 'enum'" v-model="values[field.key]" :disabled="busy" :required="field.required">
              <option value="">{{ field.required ? '请选择' : '使用默认设置' }}</option>
              <template v-if="field.kind === 'boolean'"><option value="true">是</option><option value="false">否</option></template>
              <option v-else v-for="(choice, index) in field.schema.enum" :key="index" :value="String(index)">{{ display(choice) }}</option>
            </select>
            <textarea v-else-if="field.kind === 'lines'" v-model="values[field.key]" :disabled="busy" :required="field.required" placeholder="每行填写一项" />
            <input v-else v-model="values[field.key]" :type="field.kind === 'number' || field.kind === 'integer' ? 'number' : 'text'" :step="field.kind === 'integer' ? '1' : 'any'" :min="field.schema.minimum" :max="field.schema.maximum" :minlength="field.schema.minLength" :maxlength="field.schema.maxLength || 32768" :required="field.required" :disabled="busy" :placeholder="field.schema.default === undefined ? '' : `默认：${display(field.schema.default)}`" />
          </label>
          <p v-else>{{ label(field.key) }}：可在对话中描述需要的设置。</p>
        </template>
        <p v-if="form.guided" class="operation-help">请在对话中描述要执行的操作，Agent 会配置参数；结果和过程显示在这里。</p>
        <button v-else type="submit" data-testid="operation-run" :disabled="busy || !current.available || status === 'unknown'">{{ busy ? '执行中…' : operationLabel(current) }}</button>
      </form>
    </template>
    <p v-if="error" role="alert">{{ error }}</p>
    <p role="status" class="operation-status" :data-state="status">{{ display(status) }}</p>
    <p v-if="status === 'unknown'">结果未确认；先查询原任务或状态，不自动重放。</p>
    <section v-if="result !== undefined" aria-label="操作结果" class="operation-result"><h4>结果信息</h4><CapabilityInformation :value="result?.rows || result" /></section>
    <section v-if="history.length" aria-label="操作记录" class="operation-history"><h4>操作记录</h4><ol><li v-for="item in history" :key="item.id"><time>{{ item.time }}</time><span>{{ item.name }}</span><strong>{{ display(item.status) }}</strong><p v-if="item.error">{{ item.error }}</p></li></ol></section>
  </section>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, ref } from 'vue'
import { API_BASE } from '../../lib/runtimeEndpoint'
import { objectSchema, type JsonObject } from '../../lib/frontendControl'
import { bindingHostKey } from '../../lib/workbenchBindings'
import { saveTextFile } from '../../lib/downloadTextFile'
import { display, label, errorText, operationFields, formArguments } from '../../lib/capabilityPresentation'
import CapabilityInformation from './CapabilityInformation.vue'

const props = defineProps<{ panelId: string }>()
const host = inject(bindingHostKey, null)
const capabilities = ref<JsonObject[]>([]), selected = ref(''), query = ref(''), values = ref<JsonObject>({})
const busy = ref(false), error = ref(''), status = ref('idle'), operationId = ref('')
const result = ref<any>(undefined)
const current = computed(() => capabilities.value.find(item => item.name === selected.value))
const operationLabel = (item: JsonObject) => label(item.name) !== item.name.replace(/_/g, ' ') ? label(item.name) : item.description || label(item.name)
const filtered = computed(() => capabilities.value.filter(item => item.name === selected.value || (item.name + ' ' + operationLabel(item)).toLowerCase().includes(query.value.toLowerCase())))
const form = computed(() => operationFields(current.value))
const history = ref<{ id: string; time: string; name: string; status: string; error: string }[]>([])
function summary(value: any) {
  const text = JSON.stringify(value)
  return text === undefined || text.length <= 8192 ? value : { truncated: true, characters: text.length, preview: text.slice(0, 8192) }
}
async function request(path: string, body?: JsonObject) {
  const response = await fetch(`${API_BASE}/api/runtime/capabilities${path}`, { method: body ? 'POST' : 'GET', signal: AbortSignal.timeout(body ? 120000 : 5000),
    ...(body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}) })
  const payload = await response.json()
  if (!response.ok) throw Object.assign(new Error(errorText(payload)), { status: response.status })
  return payload
}
onMounted(async () => {
  try { capabilities.value = (await request('')).capabilities }
  catch (cause) { error.value = errorText(cause) }
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
    selected.value = args.name; values.value = {}; error.value = ''; status.value = 'idle'; result.value = undefined; operationId.value = ''
    return read()
  }
  if (action === 'capability.export') {
    if (result.value === undefined) throw new Error('There is no operation result to save')
    return { saved: await saveTextFile(`mklink-${selected.value}-${operationId.value}.json`, JSON.stringify(result.value, null, 2)) }
  }
  if (!current.value?.available || action !== 'mklink.' + selected.value) throw new Error('Capability changed; read the current selection')
  if (status.value === 'unknown') throw new Error('Query the original operation before explicitly selecting a capability again')
  let argumentsValue: JsonObject
  try { argumentsValue = JSON.parse(args.arguments_json ?? '{}') }
  catch { throw new Error('操作参数无法解析，请重新配置本次操作。') }
  if (!argumentsValue || typeof argumentsValue !== 'object' || Array.isArray(argumentsValue)) throw new Error('Arguments must be a JSON object')
  busy.value = true; error.value = ''; status.value = 'running'; operationId.value = crypto.randomUUID(); result.value = undefined
  try {
    result.value = await request('/call', { capability: selected.value, arguments: argumentsValue })
    status.value = result.value?.job_id || result.value?.runtime_job_id
      ? result.value.state || result.value.status || 'submitted' : 'completed'
    return { operation_id: operationId.value, status: status.value, result: summary(result.value) }
  } catch (cause) {
    const httpStatus = (cause as { status?: number }).status
    status.value = !httpStatus || httpStatus >= 500 ? 'unknown' : 'failed'; error.value = errorText(cause)
    throw Object.assign(cause as Error, { unknown: status.value === 'unknown' })
  } finally {
    history.value.unshift({ id: operationId.value, time: new Date().toLocaleTimeString(), name: operationLabel(current.value!), status: status.value, error: error.value })
    history.value = history.value.slice(0, 50)
    busy.value = false
  }
}
async function submitForm() {
  try { await userExecute('mklink.' + selected.value, { arguments_json: JSON.stringify(formArguments(form.value.fields, values.value)) }) }
  catch (cause) { error.value = errorText(cause) }
}
async function userExecute(action: string, args: JsonObject) {
  try {
    if (!host) throw new Error('Workbench control is not connected')
    await host.invoke(props.panelId, action, args)
  } catch (cause) { error.value = errorText(cause) }
}
function restore(view: JsonObject) { if (typeof view.capability === 'string') selected.value = view.capability }
defineExpose({ catalog, read, execute, restore })
</script>

<style scoped>
.capability-panel { display:flex; flex-direction:column; gap:12px; padding:12px; min-width:0; overflow:auto; }
label { display:flex; flex-direction:column; gap:4px; font-size:14px; } input,select,textarea { min-width:0; width:100%; box-sizing:border-box; color:var(--fg); background:var(--input-bg); border:1px solid var(--border); border-radius:4px; padding:6px; }
textarea { min-height:70px; resize:vertical; } p { margin:0; font-size:14px; overflow-wrap:anywhere; }
form { display:flex; flex-direction:column; gap:10px; } h3,h4 { margin:4px 0; } h3 { font-size:15px; } h4 { font-size:14px; color:var(--muted); }
.operation-result,.operation-history { border-top:1px solid var(--border); padding-top:12px; }
.operation-status { padding:6px 8px; border-radius:5px; background:var(--input-bg); }
.operation-status[data-state="failed"], [role="alert"] { color:var(--danger-color, #dc4555); }
ol { list-style:none; margin:0; padding:0; max-height:180px; overflow:auto; } li { display:flex; flex-wrap:wrap; gap:8px; padding:5px 0; font-size:12px; } li p { flex-basis:100%; } time { color:var(--muted); } summary { cursor:pointer; }
button { color:var(--fg); background:var(--input-bg); border:1px solid var(--border); border-radius:4px; padding:7px 10px; cursor:pointer; } button:disabled { opacity:.5; cursor:default; }
</style>
