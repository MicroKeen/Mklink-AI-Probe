<template>
  <section class="workbench" data-testid="workbench">
    <header class="workbench-toolbar">
      <div><strong>{{ tr('组合工作台', 'Workbench') }}</strong><small>{{ tr('独立视图 · 共享采集', 'Independent views · shared acquisition') }}</small></div>
      <div class="workbench-actions">
        <select v-model="newType" :aria-label="tr('新面板类型', 'New panel type')"><option v-for="type in panelTypes" :key="type" :value="type">{{ labels[type] }}</option></select>
        <button class="btn btn-secondary" data-testid="add-panel" @click="userAdd">＋ {{ tr('添加面板', 'Add panel') }}</button>
        <button class="btn btn-primary" :disabled="loading || saving" data-testid="save-layout" @click="userSave">{{ saving ? tr('保存中…', 'Saving…') : tr('保存布局', 'Save layout') }}</button>
        <button class="btn btn-secondary" :disabled="loading || saving" @click="reloadPrompt = true">{{ tr('恢复已保存布局', 'Restore saved layout') }}</button>
      </div>
    </header>
    <div v-if="reloadPrompt" class="workbench-notice" role="alert">
      {{ tr('恢复会替换当前未保存的面板配置。', 'Restoring replaces the current unsaved panel configuration.') }}
      <button class="btn btn-secondary" @click="userLoad">{{ tr('恢复', 'Restore') }}</button><button class="btn btn-secondary" @click="reloadPrompt = false">{{ tr('取消', 'Cancel') }}</button>
    </div>
    <p v-if="error" class="workbench-error" role="alert">{{ error }}</p>
    <p v-if="notice" class="workbench-notice" role="status">{{ notice }}</p>
    <p v-if="loading">{{ tr('正在加载布局…', 'Loading layout…') }}</p>
    <div ref="grid" class="workbench-grid" :aria-busy="loading" @dragover.prevent @drop.prevent="drop">
      <article v-for="panel in layout.panels" :key="restoreGeneration + ':' + panel.id + ':' + JSON.stringify(panel.source)" v-show="!dockFor(layout, panel.id) || dockFor(layout, panel.id)?.active === panel.id" class="workbench-card" :data-panel-id="panel.id"
        :style="windowStyle(panel.id)">
        <header class="workbench-card-header" draggable="true" @dragstart="drag($event, panel.id)" @dragover.prevent @drop.stop.prevent="dropDock($event, panel.id)">
          <span class="drag-handle" :title="tr('拖动调整位置', 'Drag to move')">⠿</span><strong>{{ panel.title }}</strong>
          <span class="panel-kind">{{ labels[panel.type] }}</span>
          <button type="button" :aria-label="tr('请求 Agent 分析', 'Ask Agent')" @click="emit('intent', panel.id)">Agent</button>
          <button type="button" :aria-label="tr('配置面板', 'Configure panel')" :aria-expanded="editing === panel.id" @click="edit(panel)">⚙</button>
          <button type="button" :aria-label="tr('关闭面板', 'Close panel')" @click="remove(panel.id)">×</button>
        </header>
        <div v-if="dockFor(layout, panel.id)" class="dock-tabs" role="tablist" :aria-label="tr('停靠窗口', 'Docked window')">
          <button v-for="id in dockFor(layout, panel.id)!.panels" :key="id" role="tab" :aria-selected="id === panel.id" draggable="true" @dragstart.stop="drag($event, id)" @click="focus(id)">{{ find(id).title }}</button>
          <button type="button" :aria-label="tr('分离当前面板', 'Undock current panel')" @click="undock(panel.id)">↗</button>
        </div>
        <form v-if="editing === panel.id" class="panel-editor" @submit.prevent="applyEdit(panel)">
          <label>{{ tr('标题', 'Title') }}<input v-model="draft.title" maxlength="200" /></label>
          <label v-if="panel.type === 'watch' || panel.type === 'variables'">{{ tr('信号路径（逗号分隔；留空显示全部）', 'Signal paths (comma separated; empty means all)') }}<input v-model="draft.signals" /></label>
          <label v-if="panel.type === 'rtt'">RTT {{ tr('通道', 'channel') }}<input v-model.number="draft.channel" type="number" min="0" max="255" /></label>
          <label v-if="panel.type === 'serial'">{{ tr('串口', 'Port') }}<input v-model="draft.port" placeholder="COM3" /></label>
          <div class="geometry-fields"><label v-for="key in geometryKeys" :key="key">{{ key }}<input v-model.number="draft[key]" type="number" :min="key === 'x' || key === 'y' ? 0 : 1" :max="key === 'y' ? 200 : key === 'x' ? 11 : 12" /></label></div>
          <label>{{ tr('停靠到窗口（标签组）', 'Dock with window (tabs)') }}<select v-model="dockTarget"><option value="">{{ tr('选择窗口', 'Choose window') }}</option><option v-for="other in layout.panels.filter(item => item.id !== panel.id)" :key="other.id" :value="other.id">{{ other.title }}</option></select></label>
          <button type="button" class="btn btn-secondary" :disabled="!dockTarget" @click="userDock(panel.id)">{{ tr('停靠', 'Dock') }}</button>
          <button class="btn btn-primary" type="submit">{{ tr('应用', 'Apply') }}</button><button class="btn btn-secondary" type="button" @click="editing = ''">{{ tr('取消', 'Cancel') }}</button>
        </form>
        <div class="workbench-card-content" @dragover.prevent @drop="dropControl($event, panel.id)">
          <WorkbenchPanel :ref="value => register(panel.id, value)" :panel="panel" :active="active !== false && (!dockFor(layout, panel.id) || dockFor(layout, panel.id)?.active === panel.id)" :device-connected="deviceConnected" :symbol-loaded="symbolLoaded" :symbol-error="symbolError" :latest-values="latestValues" :rtt="rtt" :snapshot-path="snapshotPath" :commit-widgets="widgets => setWidgets(panel.id, widgets)" @values="values => Object.assign(latestValues, values)" @snapshot="setSnapshotPath" @transfer="transfer => userTransfer(transfer.widgetId, transfer.targetPanelId)" />
        </div>
        <button class="panel-resize" :aria-label="tr('拖动调整大小；也可在配置中输入宽高', 'Drag to resize; width and height are also available in settings')" @pointerdown.prevent="resize($event, panel)">◢</button>
      </article>
      <p v-if="!layout.panels.length" class="workbench-empty">{{ tr('添加波形、变量、RTT 或串口面板，组成你的工作区。', 'Add waveform, variable, RTT or serial panels to build your workspace.') }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, nextTick, watch, provide } from 'vue'
import { tr } from '../../composables/useLanguage'
import { API_BASE, IS_REMOTE } from '../../lib/runtimeEndpoint'
import { frontendRequest, objectSchema, interaction, type JsonObject, type SemanticSurface, type SemanticAction } from '../../lib/frontendControl'
import { addPanel, dockFor, dockPanel, undockPanel, removePanel, moveWindow, windowPanel, windowMinimum, upgradeLayout, geometrySchema, migrateLegacyWorkbench, panelInputSchema, panelSource, panelTypes, validateLayout, type PanelType, type WorkbenchLayout, type WorkbenchPanel as Panel } from '../../lib/workbenchLayout'
import { placeControl as placeWidget, controlStateKey, createControlState, type ControlWidget } from '../../lib/workbenchControls'
import { sameBinding } from '../../lib/workbenchBindings'
import { useWatchWorkspace } from '../../composables/useWatchWorkspace'
import WorkbenchPanel from './WorkbenchPanel.vue'
const props = withDefaults(defineProps<{ deviceConnected: boolean; symbolLoaded: boolean; symbolError?: string; active?: boolean }>(), { active: true })
const controlState = createControlState()
provide(controlStateKey, controlState)
const emit = defineEmits<{ intent: [panelId: string] }>()
const labels = { watch: 'SuperWatch', variables: tr('变量', 'Variables'), rtt: 'RTT', serial: tr('串口', 'Serial'), controls: tr('控制面板', 'Controls') }
const layout = ref<WorkbenchLayout>({ version: 2, revision: 0, panels: [], docks: [] })
const restoreGeneration = ref(0)
const loading = ref(false), saving = ref(false), error = ref(''), notice = ref(''), reloadPrompt = ref(false)
const newType = ref<PanelType>('watch'), editing = ref('')
const dockTarget = ref('')
const draft = reactive({ title: '', signals: '', channel: 0, port: '', x: 0, y: 0, w: 6, h: 4 })
const geometryKeys = ['x', 'y', 'w', 'h'] as const
const grid = ref<HTMLElement | null>(null)
const surfaces = new Map<string, SemanticSurface>()
const latestValues = reactive<Record<string, number>>({}), rtt = ref<JsonObject>({})
const snapshotPath = ref<string | null>(null)
let snapshotRevision = 0
function setSnapshotPath(path: string | null) { snapshotRevision++; snapshotPath.value = path }
let statusTimer: ReturnType<typeof setTimeout> | undefined, disposed = false
let cancelResize: (() => void) | null = null
function register(id: string, value: unknown) { if (value) surfaces.set(id, value as SemanticSurface); else surfaces.delete(id) }
function entries() { return layout.value.panels.map(panel => ({ id: panel.id, title: panel.title, type: panel.type, source: panel.source, surface: surfaces.get(panel.id) })) }
function read() { return { layout: layout.value, snapshotPath: snapshotPath.value, loading: loading.value, saving: saving.value, error: error.value, editing: editing.value } }
function find(id: string) { const panel = layout.value.panels.find(item => item.id === id); if (!panel) throw new Error('Panel no longer exists'); return panel }
function change<T>(mutate: (draft: WorkbenchLayout) => T): T {
  const draft = JSON.parse(JSON.stringify(layout.value)) as WorkbenchLayout
  const result = mutate(draft)
  layout.value = validateLayout(draft)
  return result
}
function remove(id: string) {
  const widgets = find(id).widgets || []
  change(draft => removePanel(draft, id))
  for (const widget of widgets) controlState.clear(widget.id)
  if (editing.value === id) editing.value = ''
}
function move(id: string, geometry: JsonObject) { return change(draft => moveWindow(draft, id, geometry)) }
function dock(id: string, target: string) { change(draft => dockPanel(draft, id, target)); editing.value = '' }
function undock(id: string) { change(draft => undockPanel(draft, id)) }
function focus(id: string) { find(id); const dock = dockFor(layout.value, id); if (dock) dock.active = id }
function windowStyle(id: string) { const panel = windowPanel(layout.value, id); return { gridColumn: `${panel.x + 1} / span ${panel.w}`, gridRow: `${panel.y + 1} / span ${panel.h}` } }
function setWidgets(id: string, widgets: ControlWidget[]) { change(draft => { const panel = draft.panels.find(panel => panel.id === id); if (panel?.type !== 'controls') throw new Error('Choose a controls panel'); panel.widgets = widgets }) }
function transferControl(id: string, targetId: string) {
  return change(draft => {
    const source = draft.panels.find(panel => panel.widgets?.some(widget => widget.id === id)), target = draft.panels.find(panel => panel.id === targetId)
    if (!source || target?.type !== 'controls' || source.id === targetId) throw new Error('Choose a different existing controls panel')
    const widget = source.widgets!.find(widget => widget.id === id)!
    const moved = placeWidget(target.widgets || [], { ...widget, x: 0, y: 0 })
    source.widgets = source.widgets!.filter(widget => widget.id !== id)
    ;(target.widgets ||= []).push(moved)
    return { component_id: id, panel_id: targetId }
  })
}
function userTransfer(id: string, target: string) { try { transferControl(id, target) } catch (cause) { error.value = String(cause) } }
function capture(): WorkbenchLayout {
  return validateLayout({ ...layout.value, panels: layout.value.panels.map(panel => {
    const view = surfaces.get(panel.id)?.read?.().view
    return { ...panel, ...(view ? { view } : {}) }
  }) })
}
async function save() {
  saving.value = true; error.value = ''; notice.value = ''
  try {
    const saved = validateLayout(await frontendRequest('layout', capture(), 'PUT'))
    layout.value.revision = saved.revision
    notice.value = tr('布局已保存。恢复布局不会启动采集或连接设备。', 'Layout saved. Restoring it does not start acquisition or connect devices.')
    return { revision: saved.revision }
  } finally { saving.value = false }
}
async function load() {
  loading.value = true; error.value = ''; notice.value = ''; reloadPrompt.value = false
  try {
    const saved = validateLayout(await frontendRequest('layout'))
    let migration: ReturnType<typeof migrateLegacyWorkbench> | undefined
    if (saved.revision === 0 && saved.panels.length === 0) {
      const prefs = useWatchWorkspace()
      await prefs.load()
      if (!prefs.ready.value) throw new Error(prefs.error.value || 'Existing SuperWatch groups could not be read')
      let selected: string[] = []
      try {
        const response = await fetch(`${API_BASE}/api/dash/superwatch/items`)
        if (response.ok) {
          const data = await response.json()
          selected = Array.isArray(data.items) ? data.items.map((item: JsonObject) => item.name).filter((name: unknown) => typeof name === 'string') : []
        }
      } catch { /* Stored styles still provide stable paths when live items are unavailable. */ }
      migration = migrateLegacyWorkbench(saved, prefs.workspace.value, selected)
      migration.layout.panels[0]!.title = tr('变量', 'Variables')
      notice.value = tr('已从现有 SuperWatch 分组建立初始工作台，尚未保存。原分组和样式保持不变。', 'Created an unsaved initial workbench from existing SuperWatch groups. Original groups and styles are retained.')
      if (migration.omittedGroups || migration.omittedSignals) notice.value += tr(` 受布局上限影响，另有 ${migration.omittedGroups} 组、${migration.omittedSignals} 个信号未生成卡片；原配置仍保留。`, ` Layout limits left ${migration.omittedGroups} groups and ${migration.omittedSignals} signals without cards; original settings remain intact.`)
    }
    const upgraded = upgradeLayout(migration?.layout || saved)
    const restored = new Map(upgraded.panels.flatMap(panel => (panel.widgets || []).map(widget => [widget.id, widget] as const)))
    const changed = layout.value.panels.flatMap(panel => panel.widgets || []).filter(widget => {
      const next = restored.get(widget.id)
      return !next || next.type !== widget.type || !sameBinding(next.binding, widget.binding)
    })
    if (changed.some(widget => ['running', 'unknown'].includes(controlState.statuses[widget.id]?.status || ''))) throw new Error('Restoring would replace a running or unknown control operation; inspect its original receipt first')
    for (const widget of changed) controlState.clear(widget.id)
    layout.value = upgraded
    if (saved.version === 1 && !migration) notice.value = tr('旧布局已适配组件最小尺寸；保存后升级为版本 2。', 'Legacy layout adapted to component minimum sizes; save to upgrade to version 2.')
    restoreGeneration.value++
    await nextTick()
    return { revision: saved.revision, panels: layout.value.panels.length, layout_loaded: true, migrated: migration?.migrated || false, unsaved: migration?.migrated || false, view_restoration: 'Components restore display settings as they become ready; inspect each panel state.' }
  } finally { loading.value = false }
}
async function userSave() { try { await save() } catch (cause) { error.value = String(cause) } }
async function userLoad() { try { await load() } catch (cause) { error.value = String(cause) } }
function userAdd() {
  try { create({ type: newType.value, title: `${labels[newType.value]} ${layout.value.panels.length + 1}` }) } catch (cause) { error.value = String(cause) }
}
function create(args: JsonObject) {
  if (args.type === 'serial' && IS_REMOTE) throw new Error('Serial panels require a local workspace')
  return change(draft => addPanel(draft, args))
}
function edit(panel: Panel) {
  editing.value = editing.value === panel.id ? '' : panel.id
  const host = windowPanel(layout.value, panel.id)
  dockTarget.value = ''
  Object.assign(draft, { title: panel.title, signals: (panel.source.signals || []).join(', '), channel: panel.source.channel ?? 0, port: panel.source.port || '', x: host.x, y: host.y, w: host.w, h: host.h })
}
function configure(id: string, args: JsonObject) {
  const panel = find(id)
  interaction.validateArgs({ ...args, type: panel.type }, panelInputSchema)
  return change(draft => { const panel = draft.panels.find(panel => panel.id === id)!; Object.assign(panel, { title: args.title, source: panelSource(panel.type, args) }); delete panel.view; return panel })
}
function applyEdit(panel: Panel) {
  try {
    const args = { title: draft.title, ...(panel.type === 'rtt' ? { channel: draft.channel } : panel.type === 'serial' ? { port: draft.port } : panel.type === 'controls' ? {} : { signals: draft.signals.split(',').map(value => value.trim()).filter(Boolean) }) }
    interaction.validateArgs({ ...args, type: panel.type }, panelInputSchema)
    change(layout => {
      moveWindow(layout, panel.id, { x: draft.x, y: draft.y, w: draft.w, h: draft.h })
      const current = layout.panels.find(item => item.id === panel.id)!
      Object.assign(current, { title: args.title, source: panelSource(panel.type, args) }); delete current.view
    })
    editing.value = ''; error.value = ''
  } catch (cause) { error.value = String(cause) }
}
function drag(event: DragEvent, id: string) { event.dataTransfer?.setData('application/x-mklink-panel', id) }
function userDock(id: string) { try { dock(id, dockTarget.value) } catch (cause) { error.value = String(cause) } }
function dropDock(event: DragEvent, target: string) { const id = event.dataTransfer?.getData('application/x-mklink-panel'); if (id && id !== target) { try { dock(id, target) } catch (cause) { error.value = String(cause) } } }
function dropControl(event: DragEvent, target: string) {
  const raw = event.dataTransfer?.getData('application/x-mklink-control')
  if (!raw || find(target).type !== 'controls') return
  event.stopPropagation(); event.preventDefault()
  try { const item = JSON.parse(raw); if (item.panel_id !== target) transferControl(item.widget_id, target) } catch (cause) { error.value = String(cause) }
}
function drop(event: DragEvent) {
  const id = event.dataTransfer?.getData('application/x-mklink-panel')
  if (!id || !grid.value) return
  try {
    const panel = find(id), bounds = grid.value.getBoundingClientRect()
    const x = Math.min(12 - panel.w, Math.max(0, Math.floor((event.clientX - bounds.left) / (bounds.width / 12))))
    const y = Math.min(200, Math.max(0, Math.floor((event.clientY - bounds.top) / 88)))
    change(draft => { if (dockFor(draft, id)) undockPanel(draft, id); moveWindow(draft, id, { x, y }) })
  } catch (cause) { error.value = String(cause) }
}
function resize(event: PointerEvent, panel: Panel) {
  if (!grid.value) return
  cancelResize?.()
  const host = windowPanel(layout.value, panel.id), min = windowMinimum(layout.value, panel.id)
  const startX = event.clientX, startY = event.clientY, column = grid.value.clientWidth / 12
  const finish = (end: PointerEvent) => {
    cleanup()
    try { move(panel.id, { w: Math.min(12 - host.x, Math.max(min.w, host.w + Math.round((end.clientX - startX) / column))), h: Math.min(12, Math.max(min.h, host.h + Math.round((end.clientY - startY) / 88))) }) }
    catch (cause) { error.value = String(cause) }
  }
  const cleanup = () => { window.removeEventListener('pointerup', finish); window.removeEventListener('pointercancel', cleanup); cancelResize = null }
  cancelResize = cleanup; window.addEventListener('pointerup', finish); window.addEventListener('pointercancel', cleanup)
}
const idProperty = { panel_id: { type: 'string', maxLength: 80 } }
function catalog(): SemanticAction[] {
  const { type: _type, ...sourceProperties } = panelInputSchema.properties
  return [
    { name: 'panel.add', description: 'Add an independent view; does not connect or start acquisition', args: panelInputSchema, effect: 'view' },
    { name: 'panel.remove', description: 'Close a view without stopping shared acquisition', args: objectSchema(idProperty), effect: 'view' },
    { name: 'panel.move', description: 'Move or resize a panel in the twelve-column grid', args: objectSchema({ ...idProperty, ...geometrySchema }), effect: 'view' },
    { name: 'panel.dock', description: 'Dock a panel as a tab beside the target panel without restarting its view', args: objectSchema({ ...idProperty, target_panel_id: { type: 'string', maxLength: 80 } }), effect: 'view' },
    { name: 'panel.undock', description: 'Detach a tab to an independent window', args: objectSchema(idProperty), effect: 'view' },
    { name: 'panel.focus', description: 'Show a panel tab in its existing window', args: objectSchema(idProperty), effect: 'view' },
    { name: 'panel.editor', description: 'Open or close a panel settings editor', args: objectSchema({ ...idProperty, open: { type: 'boolean' } }), effect: 'view' },
    { name: 'component.transfer', description: 'Move a control to another controls panel, retaining its identity and binding', args: objectSchema({ component_id: { type: 'string', maxLength: 80 }, target_panel_id: { type: 'string', maxLength: 80 } }), effect: 'view' },
    { name: 'panel.configure', description: 'Set a panel title and source; empty signal list follows all selected signals', args: objectSchema({ ...idProperty, ...sourceProperties }, ['panel_id', 'title']), effect: 'view' },
    { name: 'layout.save', description: 'Save this layout with optimistic revision checking', args: objectSchema(), effect: 'file' },
    { name: 'layout.restore', description: 'Replace unsaved views with saved layout; no device actions', args: objectSchema(), effect: 'view' },
  ]
}
async function execute(action: string, args: JsonObject) {
  const descriptor = catalog().find(item => item.name === action)
  if (!descriptor) throw new Error('Unknown workbench action')
  interaction.validateArgs(args, descriptor.args)
  if (action === 'panel.add') return create(args)
  if (action === 'panel.remove') { remove(args.panel_id); return { removed: args.panel_id } }
  if (action === 'panel.move') { const { panel_id, ...geometry } = args; return move(panel_id, geometry) }
  if (action === 'panel.dock') { dock(args.panel_id, args.target_panel_id); return read() }
  if (action === 'panel.undock') { undock(args.panel_id); return read() }
  if (action === 'panel.focus') { focus(args.panel_id); return { active: args.panel_id } }
  if (action === 'panel.editor') { if (args.open) { focus(args.panel_id); if (editing.value !== args.panel_id) edit(find(args.panel_id)) } else editing.value = ''; return { editing: editing.value } }
  if (action === 'component.transfer') return transferControl(args.component_id, args.target_panel_id)
  if (action === 'panel.configure') { const { panel_id, ...values } = args; return configure(panel_id, values) }
  if (action === 'layout.save') return save()
  return load()
}
async function pollStatus() {
  try {
    const response = await fetch(`${API_BASE}/api/dash/rtt/status`)
    if (response.ok && !disposed) rtt.value = await response.json()
  } catch { /* Connection state stays with the existing RTT controls. */ }
  await refreshSnapshot()
  if (!disposed) statusTimer = setTimeout(pollStatus, 1500)
}
async function refreshSnapshot() {
  if (!props.deviceConnected) { if (snapshotPath.value !== null) setSnapshotPath(null); return }
  const revision = snapshotRevision
  try {
    const response = await fetch(`${API_BASE}/api/dash/superwatch/array-snapshot`)
    if (response.ok) {
      const data = await response.json()
      if (!disposed && revision === snapshotRevision) snapshotPath.value = typeof data.snapshot?.name === 'string' ? data.snapshot.name : null
    }
  } catch { /* Existing snapshot selection remains visible during transient failure. */ }
}
watch(() => props.deviceConnected, () => { snapshotRevision++; void refreshSnapshot() })
onMounted(() => { void userLoad(); void pollStatus() })
onUnmounted(() => { disposed = true; clearTimeout(statusTimer); cancelResize?.() })
defineExpose({ catalog, read, execute, entries, load })
</script>

<style scoped>
.workbench { display:flex; flex-direction:column; min-height:500px; gap:12px; padding:12px; overflow:auto; }
.workbench-toolbar,.workbench-actions { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.workbench-toolbar { justify-content:space-between; }.workbench-toolbar small { display:block; color:var(--muted); font-size:11px; margin-top:4px; }
.workbench-grid { display:grid; grid-template-columns:repeat(12,minmax(0,1fr)); grid-auto-rows:80px; gap:8px; align-items:stretch; min-height:350px; }
.workbench-card { position:relative; display:flex; flex-direction:column; min-width:0; min-height:0; background:var(--surface); border:1px solid var(--border); border-radius:var(--radius,8px); overflow:hidden; }
.workbench-card-header { display:flex; align-items:center; flex:none; gap:7px; padding:7px 8px; background:var(--bg); border-bottom:1px solid var(--border); cursor:grab; }
.workbench-card-header strong { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:12px; }.workbench-card-header button { padding:2px 5px; background:transparent; color:var(--fg); border:1px solid var(--border); border-radius:4px; cursor:pointer; }
.dock-tabs { display:flex; flex:none; gap:4px; padding:4px; overflow:auto; border-bottom:1px solid var(--border); }.dock-tabs button { border:1px solid var(--border); border-radius:4px; padding:4px 8px; color:var(--fg); background:var(--surface); white-space:nowrap; cursor:pointer; }.dock-tabs button[aria-selected=true] { border-color:var(--accent); color:var(--accent); }
.panel-kind { color:var(--muted); font-size:10px; }.drag-handle { color:var(--muted); }
.workbench-card-content { position:relative; flex:1; min-height:0; overflow:auto; display:flex; flex-direction:column; }.workbench-card-content :deep(.symbol-panel) { width:100%; min-width:0; max-width:none; flex:1; }.workbench-card-content :deep(.waveform-viewer) { flex:1; min-height:240px; }.workbench-card-content :deep(.rtt-channel-panel) { flex:1; min-height:0; }
.panel-editor { position:absolute; z-index:5; inset:37px 0 auto; padding:10px; background:var(--surface); border-bottom:1px solid var(--border); box-shadow:0 4px 12px #0003; }.panel-editor label { display:flex; flex-direction:column; gap:3px; font-size:11px; margin-bottom:6px; }.panel-editor input { width:100%; min-width:0; box-sizing:border-box; }.geometry-fields { display:flex; gap:8px; }.geometry-fields label { flex:1; }.panel-editor button { margin-right:6px; }
.panel-resize { position:absolute; right:1px; bottom:1px; border:0; background:var(--surface); color:var(--muted); cursor:nwse-resize; width:20px; height:20px; touch-action:none; }
.workbench-error { color:var(--danger,#e76b6b); margin:0; }.workbench-notice { font-size:12px; color:var(--muted); margin:0; }.workbench-empty { grid-column:1/-1; color:var(--muted); padding:36px; text-align:center; }
@media(max-width:700px) { .workbench-grid { display:flex; flex-direction:column; }.workbench-card { min-height:360px; }.panel-resize { display:none; } }
</style>
