<template>
  <section class="control-panel" :data-control-panel="panelId">
    <header class="component-toolbar">
      <select v-model="newType" aria-label="组件类型"><option v-for="(definition, type) in controlTypes" :key="type" :value="type">{{ definition.title }}</option></select>
      <button type="button" @click="userAdd">＋ 添加组件</button>
      <small>拖动组件排列；固定参数随布局保存，表单输入仅用于本次执行。</small>
    </header>
    <p v-if="error" role="alert">{{ error }}</p>
    <div ref="grid" class="component-grid" @dragover.prevent @drop.prevent="drop">
      <article v-for="widget in localWidgets" :key="widget.id" class="control-widget" :data-component-id="widget.id" :style="{ gridColumn: `${widget.x + 1} / span ${widget.w}`, gridRow: `${widget.y + 1} / span ${widget.h}` }">
        <header draggable="true" @dragstart.stop="drag($event, widget.id)">
          <strong>{{ widget.title }}</strong>
          <button type="button" aria-label="配置组件" :aria-expanded="editing === widget.id" @click="userExecute('component.editor', { component_id: widget.id, open: editing !== widget.id })">⚙</button>
          <button type="button" aria-label="删除组件" @click="userExecute('component.remove', { component_id: widget.id })">×</button>
        </header>
        <div class="control-body">
          <small v-if="bindingError(widget)" class="binding-error">{{ bindingError(widget) }}</small>
          <component v-if="controlTypes[widget.type]?.renderer" :is="controlTypes[widget.type]!.renderer" :widget="widget" :schema="actionFor(widget)?.args" :busy="statuses[widget.id]?.status === 'running'" :value="values[widget.id]" @read="userExecute('component.read', { component_id: widget.id })" @invoke="(args: JsonObject) => userExecute('component.invoke', { component_id: widget.id, args_json: JSON.stringify(args || {}) })" />
          <template v-else-if="controlTypes[widget.type]?.presentation === 'value'">
            <output>{{ formatValue(values[widget.id]) }}</output>
            <button type="button" :disabled="Boolean(bindingError(widget))" @click="userExecute('component.read', { component_id: widget.id })">刷新数值</button>
          </template>
          <form v-else-if="controlTypes[widget.type]?.presentation === 'form'" @submit.prevent="submitForm(widget)">
            <label v-for="(field, name) in actionFor(widget)?.args.properties || {}" :key="name" class="argument-field">
              <span>{{ name }}{{ actionFor(widget)?.args.required?.includes(name) ? ' *' : '' }}</span>
              <select v-if="field.enum || field.type === 'boolean'" :value="fieldText(widget, String(name))" :aria-label="String(name)" @change="setField(widget, String(name), $event)">
                <option value="">使用固定参数 / 未设置</option>
                <option v-for="value in field.enum || [true, false]" :key="String(value)" :value="String(value)">{{ value }}</option>
              </select>
              <textarea v-else-if="field.type === 'object' || field.type === 'array'" :value="fieldText(widget, String(name))" :aria-label="String(name)" placeholder="JSON" @input="setField(widget, String(name), $event)" />
              <input v-else :type="field.type === 'string' ? 'text' : 'number'" :min="field.minimum" :max="field.maximum" :step="field.type === 'integer' ? 1 : 'any'" :maxlength="field.maxLength" :value="fieldText(widget, String(name))" :aria-label="String(name)" @input="setField(widget, String(name), $event)" />
            </label>
            <button type="submit" :disabled="Boolean(bindingError(widget)) || statuses[widget.id]?.status === 'running'">执行 {{ widget.title }}</button>
          </form>
          <button v-else type="button" :disabled="Boolean(bindingError(widget)) || statuses[widget.id]?.status === 'running'" @click="userExecute('component.invoke', { component_id: widget.id })">{{ statuses[widget.id]?.status === 'running' ? '执行中…' : widget.title }}</button>
          <p v-if="statuses[widget.id]" :role="statuses[widget.id]?.status === 'failed' || statuses[widget.id]?.status === 'unknown' ? 'alert' : 'status'">{{ statuses[widget.id]?.status }} {{ statuses[widget.id]?.message }}</p>
          <pre v-if="results[widget.id] !== undefined" class="control-result">{{ formatValue(results[widget.id]) }}</pre>
        </div>
      </article>
      <p v-if="!localWidgets.length" class="empty-controls">添加动作按钮、参数表单或状态数值，然后绑定现有面板的能力。</p>
    </div>
    <form v-if="editing" class="component-editor" @submit.prevent="applyEdit">
      <header><strong>配置组件</strong><button type="button" aria-label="关闭组件配置" @click="userExecute('component.editor', { component_id: editing, open: false })">×</button></header>
      <label>标题<input v-model="draft.title" maxlength="200" /></label>
      <div class="component-geometry"><label v-for="key in geometryKeys" :key="key">{{ key }}<input v-model.number="draft[key]" type="number" :min="key === 'x' || key === 'y' ? 0 : 1" :max="key === 'y' ? 200 : 12" /></label></div>
      <label>目标面板<select v-model="draft.panel_id" @change="draft.action = ''; draft.state_path = ''"><option value="">未绑定</option><option v-for="target in targets()" :key="target.id" :value="target.id">{{ target.title }} · {{ target.id }}</option></select></label>
      <label v-if="editingWidget && controlTypes[editingWidget.type]?.presentation === 'value'">公开状态字段<input v-model="draft.state_path" :list="panelId + '-state-fields'" placeholder="view.paused" maxlength="512" /><datalist :id="panelId + '-state-fields'"><option v-for="path in statePaths()" :key="path" :value="path" /></datalist></label>
      <template v-else>
        <label>业务动作<select v-model="draft.action"><option value="">选择已公布的动作</option><option v-for="action in draftActions()" :key="action.name" :value="action.name">{{ action.name }} · {{ action.description }}</option></select></label>
        <label>固定参数 JSON（随布局保存）<textarea v-model="draft.args_json" maxlength="8192" /></label>
      </template>
      <button type="submit">应用配置</button>
      <button type="button" @click="userExecute('component.unbind', { component_id: editing })">清除绑定</button>
      <button type="button" @click="userExecute('component.editor', { component_id: editing, open: false })">取消</button>
    </form>
  </section>
</template>

<script setup lang="ts">
import { computed, inject, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { interaction, objectSchema, type JsonObject, type SemanticAction, type SemanticExecutionContext } from '../../lib/frontendControl'
import { bindingHostKey, bindingAction, makeBinding, invokeBinding, parseArguments, readBoundValue, sameBinding, type ControlBinding } from '../../lib/workbenchBindings'
import { controlTypes, controlGeometrySchema, controlIdSchema, controlStateKey, createControlState, createControl, placeControl, validateControls, type ControlWidget } from '../../lib/workbenchControls'

const props = withDefaults(defineProps<{ panelId: string; widgets: ControlWidget[]; active?: boolean; commitWidgets?: (widgets: ControlWidget[]) => void }>(), { active: true })
const emit = defineEmits<{ change: [widgets: ControlWidget[]]; transfer: [request: { sourcePanelId: string; widgetId: string; targetPanelId: string; x: number; y: number }] }>()
const host = inject(bindingHostKey, null)
const localWidgets = ref<ControlWidget[]>([]), newType = ref('button'), editing = ref(''), error = ref('')
const grid = ref<HTMLElement | null>(null)
const providedState = inject(controlStateKey, null)
const transient = providedState || createControlState()
const { statuses, results, values, drafts, operations } = transient
const draft = reactive({ title: '', panel_id: '', action: '', state_path: '', args_json: '{}', x: 0, y: 0, w: 4, h: 1 })
const geometryKeys = ['x', 'y', 'w', 'h'] as const
let valueTimer: ReturnType<typeof setTimeout> | undefined, disposed = false
watch(() => props.widgets, widgets => { localWidgets.value = validateControls(widgets) }, { immediate: true, deep: true })
const editingWidget = computed(() => localWidgets.value.find(widget => widget.id === editing.value))
const targets = () => host?.targets().filter(target => target.type !== 'controls') || []
function requiredHost() { if (!host) throw new Error('Workbench bindings are unavailable'); return host }
function find(id: string) { const widget = localWidgets.value.find(item => item.id === id); if (!widget) throw new Error('Component no longer exists'); return widget }
function publish(widgets: ControlWidget[]) { const next = validateControls(widgets); if (props.commitWidgets) props.commitWidgets(next); else emit('change', next); localWidgets.value = next; error.value = '' }
function actionFor(widget: ControlWidget) { try { return bindingAction(requiredHost(), widget.binding) } catch { return undefined } }
function bindingError(widget: ControlWidget) {
  if (!widget.binding.panel_id) return '尚未绑定业务接口'
  try {
    if (controlTypes[widget.type]?.presentation === 'value') readBoundValue(requiredHost(), widget.binding)
    else bindingAction(requiredHost(), widget.binding)
    return ''
  } catch (cause) { return String(cause) }
}
function formatValue(value: unknown) { if (value === undefined) return '—'; const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2); return text.length > 8192 ? text.slice(0, 8192) + '…' : text }
function refreshValues(schedule = true) {
  for (const widget of props.active === false ? [] : localWidgets.value) if (controlTypes[widget.type]?.presentation === 'value' && widget.binding.panel_id) {
    try { const value = readBoundValue(requiredHost(), widget.binding); if (JSON.stringify(value) !== JSON.stringify(values[widget.id])) values[widget.id] = value }
    catch { delete values[widget.id] }
  }
  if (schedule && !disposed) valueTimer = setTimeout(refreshValues, 1000)
}
watch(() => props.active, active => { if (active !== false) refreshValues(false) })
function draftActions() { return targets().find(target => target.id === draft.panel_id)?.surface.catalog().filter(action => !action.name.startsWith('component.')) || [] }
function statePaths() {
  const target = targets().find(item => item.id === draft.panel_id), paths: string[] = []
  function visit(value: unknown, prefix = '', depth = 0) {
    if (depth > 5 || paths.length >= 100 || !value || typeof value !== 'object') return
    for (const key of Object.keys(value)) {
      if (['__proto__', 'prototype', 'constructor'].includes(key)) continue
      const path = prefix ? prefix + '.' + key : key
      if (paths.length >= 100) break
      paths.push(path); visit((value as JsonObject)[key], path, depth + 1)
    }
  }
  if (target) visit(target.surface.read())
  return paths
}
function edit(widget: ControlWidget) {
  editing.value = widget.id
  Object.assign(draft, { title: widget.title, panel_id: widget.binding.panel_id || '', action: widget.binding.action || '', state_path: widget.binding.state_path || '', args_json: JSON.stringify(widget.binding.args || {}, null, 2), x: widget.x, y: widget.y, w: widget.w, h: widget.h })
}
function applyEdit() { void userExecute('component.configure', { component_id: editing.value, ...draft }).then(ok => { if (ok) editing.value = '' }) }
function fieldText(widget: ControlWidget, name: string) {
  if (Object.hasOwn(drafts[widget.id] || {}, name)) return drafts[widget.id]![name]
  const value = widget.binding.args?.[name]
  return value === undefined ? '' : typeof value === 'object' ? JSON.stringify(value) : String(value)
}
function setField(widget: ControlWidget, name: string, event: Event) { (drafts[widget.id] ||= {})[name] = (event.target as HTMLInputElement).value }
function formArguments(widget: ControlWidget) {
    const action = bindingAction(requiredHost(), widget.binding), args: JsonObject = {}
    for (const [name, field] of Object.entries(action.args.properties) as [string, JsonObject][]) {
      const value = fieldText(widget, name)
      const provided = Object.hasOwn(drafts[widget.id] || {}, name) || Object.hasOwn(widget.binding.args || {}, name)
      if (value === '' && (field.type !== 'string' || !provided && !action.args.required.includes(name))) continue
      args[name] = field.type === 'string' ? value : field.type === 'boolean' ? value === 'true' : field.type === 'integer' || field.type === 'number' ? Number(value) : JSON.parse(value)
    }
    return args
}
function submitForm(widget: ControlWidget) { void userExecute('component.invoke', { component_id: widget.id }) }
function drag(event: DragEvent, id: string) { event.dataTransfer?.setData('application/x-mklink-control', JSON.stringify({ panel_id: props.panelId, widget_id: id })) }
function drop(event: DragEvent) {
  const text = event.dataTransfer?.getData('application/x-mklink-control')
  if (!text || !grid.value) return
  try {
    const data = JSON.parse(text), bounds = grid.value.getBoundingClientRect()
    if (data.panel_id !== props.panelId) return
    event.stopPropagation()
    const x = Math.max(0, Math.min(11, Math.floor((event.clientX - bounds.left) / (bounds.width / 12))))
    const y = Math.max(0, Math.min(200, Math.floor((event.clientY - bounds.top) / 88)))
    const widget = find(data.widget_id)
    void userExecute('component.move', { component_id: widget.id, x: Math.min(x, 12 - widget.w), y, w: widget.w, h: widget.h })
  } catch (cause) { error.value = String(cause) }
}
const identity = { component_id: controlIdSchema }
const bindingFields = { panel_id: controlIdSchema, action: { type: 'string', maxLength: 128 }, state_path: { type: 'string', maxLength: 512 }, args_json: { type: 'string', maxLength: 8192 } }
function catalog(): SemanticAction[] {
  return [
    { name: 'component.types', description: 'List build-registered component types and readable design dimensions', args: objectSchema(), effect: 'view' },
    { name: 'component.add', description: 'Add an unbound component without executing business logic', args: objectSchema({ type: { type: 'string', enum: Object.keys(controlTypes) }, title: { type: 'string', maxLength: 200 } }), effect: 'view' },
    { name: 'component.remove', description: 'Remove a component without stopping business tasks', args: objectSchema(identity), effect: 'view' },
    { name: 'component.editor', description: 'Open or close the configuration editor for this component', args: objectSchema({ ...identity, open: { type: 'boolean' } }), effect: 'view' },
    { name: 'component.configure', description: 'Configure title, geometry and optional explicit binding atomically', args: objectSchema({ ...identity, title: { type: 'string', maxLength: 200 }, ...controlGeometrySchema, ...bindingFields }, ['component_id']), effect: 'view' },
    { name: 'component.move', description: 'Move or resize a component while respecting readable dimensions', args: objectSchema({ ...identity, ...controlGeometrySchema }), effect: 'view' },
    { name: 'component.bind', description: 'Bind an advertised action or public state field and freeze its contract', args: objectSchema({ ...identity, ...bindingFields }, ['component_id', 'panel_id']), effect: 'view' },
    { name: 'component.unbind', description: 'Remove the binding without executing it', args: objectSchema(identity), effect: 'view' },
    { name: 'component.input', description: 'Set transient typed form input without executing or saving it', args: objectSchema({ ...identity, args_json: { type: 'string', maxLength: 8192 } }), effect: 'view' },
    { name: 'component.invoke', description: 'Execute the original bound business action once with typed arguments', args: objectSchema({ ...identity, args_json: { type: 'string', maxLength: 8192 } }, ['component_id']), effect: 'device' },
    { name: 'component.read', description: 'Read a bound public state field on demand; no action is executed', args: objectSchema(identity), effect: 'view' },
  ]
}
async function execute(action: string, args: JsonObject = {}, context?: SemanticExecutionContext): Promise<unknown> {
  const descriptor = catalog().find(item => item.name === action)
  if (!descriptor) throw new Error('Unknown component operation')
  interaction.validateArgs(args, descriptor.args)
  if (action === 'component.types') return Object.entries(controlTypes).map(([type, { renderer: _renderer, ...definition }]) => ({ type, version: 1, ...definition }))
  if (action === 'component.add') { const widget = createControl(localWidgets.value, args.type, args.title); publish([...localWidgets.value, widget]); await nextTick(); return widget }
  const widget = find(args.component_id)
  if (action === 'component.editor') { if (args.open) edit(widget); else editing.value = ''; await nextTick(); return { editing: editing.value || null } }
  if (action === 'component.remove') { publish(localWidgets.value.filter(item => item.id !== widget.id)); transient.clear(widget.id); await nextTick(); return { removed: widget.id } }
  if (action === 'component.input') {
    if (controlTypes[widget.type]?.presentation !== 'form') throw new Error('Only parameter forms accept transient input')
    const descriptor = bindingAction(requiredHost(), widget.binding), input = parseArguments(args.args_json)
    interaction.validateArgs(input, { ...descriptor.args, required: [] })
    drafts[widget.id] = Object.fromEntries(Object.entries(input).map(([name, value]) => [name, typeof value === 'object' ? JSON.stringify(value) : String(value)]))
    await nextTick(); return { component_id: widget.id, fields: Object.keys(input), input_updated: true }
  }
  if (action === 'component.read') {
    if (controlTypes[widget.type]?.presentation !== 'value') throw new Error('Only state components support component.read')
    const value = readBoundValue(requiredHost(), widget.binding); values[widget.id] = value; return { component_id: widget.id, value }
  }
  if (action === 'component.invoke') {
    if (controlTypes[widget.type]?.presentation === 'value') throw new Error('A state component cannot invoke a business action')
    if (statuses[widget.id]?.status === 'running' || statuses[widget.id]?.status === 'unknown') throw new Error('The original operation is running or unknown; inspect its receipt before retrying')
    const overrides = args.args_json !== undefined ? parseArguments(args.args_json) : controlTypes[widget.type]?.presentation === 'form' ? formArguments(widget) : {}
    const operation = crypto.randomUUID(); operations[widget.id] = operation
    delete results[widget.id]
    statuses[widget.id] = { status: 'running' }
    try {
      const result = await invokeBinding(requiredHost(), widget.binding, overrides, context)
      if (operations[widget.id] === operation) { statuses[widget.id] = { status: 'completed' }; results[widget.id] = result }
      return result
    } catch (cause) {
      if (operations[widget.id] === operation) statuses[widget.id] = { status: (cause as { unknown?: boolean }).unknown ? 'unknown' : 'failed', message: String(cause).slice(0, 2000) }
      throw cause
    }
  }
  let binding: ControlBinding = widget.binding
  if (action === 'component.unbind') binding = {}
  else if (action === 'component.bind' || action === 'component.configure' && Object.keys(bindingFields).some(key => args[key] !== undefined)) {
    const panelId = args.panel_id ?? widget.binding.panel_id
    const presentation = controlTypes[widget.type]!.presentation
    const requested: ControlBinding = panelId ? presentation === 'value' ? { panel_id: panelId, state_path: args.state_path ?? widget.binding.state_path }
      : { panel_id: panelId, action: args.action ?? widget.binding.action, args: args.args_json !== undefined ? parseArguments(args.args_json) : widget.binding.args || {}, contract: widget.binding.contract } : {}
    binding = action === 'component.configure' && sameBinding(requested, widget.binding) ? widget.binding : panelId ? makeBinding(requiredHost(), presentation, requested) : {}
    if (!panelId && args.panel_id !== '') throw new Error('Choose a binding target before changing its parameters')
  }
  const bindingChanged = !sameBinding(binding, widget.binding)
  if (bindingChanged && ['running', 'unknown'].includes(statuses[widget.id]?.status || '')) throw new Error('The original operation is running or unknown; its binding cannot be replaced or cleared')
  const next = { ...widget, binding }
  for (const key of ['title', ...geometryKeys] as const) if (args[key] !== undefined) (next as any)[key] = args[key]
  const placed = placeControl(localWidgets.value, next)
  publish(localWidgets.value.map(item => item.id === widget.id ? placed : item))
  if (bindingChanged) transient.clear(widget.id)
  if (controlTypes[placed.type]?.presentation === 'value' && placed.binding.panel_id) {
    try { values[widget.id] = readBoundValue(requiredHost(), placed.binding) } catch { delete values[widget.id] }
  }
  await nextTick()
  return placed
}
async function userExecute(action: string, args: JsonObject) { try { await execute(action, args); error.value = ''; return true } catch (cause) { error.value = String(cause); return false } }
function userAdd() { void userExecute('component.add', { type: newType.value, title: controlTypes[newType.value]!.title }) }
function read() { return { widgets: JSON.parse(JSON.stringify(localWidgets.value)), editing: editing.value || null, statuses: Object.fromEntries(localWidgets.value.filter(widget => statuses[widget.id]).map(widget => [widget.id, { ...statuses[widget.id], operation_id: operations[widget.id], ...(results[widget.id] !== undefined ? { result_summary: formatValue(results[widget.id]).slice(0, 2000) } : {}) }])) } }
defineExpose({ catalog, read, execute })
onMounted(() => refreshValues())
onUnmounted(() => { disposed = true; clearTimeout(valueTimer); if (!providedState) for (const widget of localWidgets.value) transient.clear(widget.id) })
</script>

<style scoped>
.control-panel { position:relative; display:flex; flex-direction:column; min-height:240px; padding:8px; gap:8px; }
.component-toolbar, .control-widget > header, .component-editor > header { display:flex; align-items:center; gap:6px; flex-wrap:wrap; }
.component-toolbar small { color:var(--muted); font-size:11px; }
.component-grid { display:grid; grid-template-columns:repeat(12,minmax(0,1fr)); grid-auto-rows:80px; gap:8px; min-height:160px; }
.control-widget { min-width:0; overflow:auto; border:1px solid var(--border); border-radius:6px; background:var(--surface); }
.control-widget > header { padding:4px 6px; background:var(--bg); cursor:grab; }
.control-widget strong, .component-editor strong { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; font-size:12px; }
.control-body { padding:6px; display:flex; flex-direction:column; gap:6px; }
.control-body output { font:600 18px var(--font-mono); white-space:pre-wrap; overflow-wrap:anywhere; }
button, select, input, textarea { color:var(--fg); background:var(--input-bg); border:1px solid var(--border); border-radius:4px; padding:4px 6px; min-width:0; max-width:100%; box-sizing:border-box; }
button { cursor:pointer; } button:disabled { opacity:.5; cursor:not-allowed; }
.binding-error, [role=alert] { color:var(--danger); font-size:11px; overflow-wrap:anywhere; }
.argument-field, .component-editor label { display:flex; flex-direction:column; gap:3px; font-size:12px; margin-bottom:6px; }
.argument-field textarea { min-height:55px; resize:vertical; }
.control-result { max-height:160px; overflow:auto; margin:0; white-space:pre-wrap; overflow-wrap:anywhere; font-size:11px; }
.empty-controls { grid-column:1/-1; color:var(--muted); font-size:12px; }
.component-editor { position:absolute; z-index:8; inset:45px 8px auto; max-height:calc(100% - 55px); overflow:auto; padding:10px; background:var(--surface); border:1px solid var(--border); border-radius:6px; box-shadow:0 8px 24px #0006; }
.component-editor textarea { min-height:65px; }.component-editor > button { margin-right:6px; }
.component-geometry { display:flex; gap:6px; }.component-geometry label { flex:1; min-width:0; }
@media(max-width:700px) { .component-grid { display:flex; flex-direction:column; }.control-widget { min-height:80px; }.component-editor { position:relative; inset:auto; max-height:none; } }
</style>
