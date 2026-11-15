<template>
  <section class="workbench" :class="{ 'is-editing': layoutEditing }" data-testid="workbench">
    <header class="workbench-toolbar">
      <div><strong>{{ tr('组合工作台', 'Workbench') }}</strong><small>{{ tr('独立视图 · 共享采集', 'Independent views · shared acquisition') }}</small></div>
      <div class="workbench-actions">
        <button class="btn" :class="layoutEditing ? 'btn-primary' : 'btn-secondary'" :aria-pressed="layoutEditing" @click="layoutEditing = !layoutEditing"><LayoutDashboard :size="16" />{{ layoutEditing ? tr('完成布局', 'Done editing') : tr('编辑布局', 'Edit layout') }}</button>
        <select v-if="layoutEditing" v-model="newType" :aria-label="tr('新面板类型', 'New panel type')"><option v-for="type in panelTypes" :key="type" :value="type">{{ labels[type] }}</option></select>
        <button v-if="layoutEditing" class="btn btn-secondary" data-testid="add-panel" @click="userAdd">＋ {{ tr('添加面板', 'Add panel') }}</button>
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
    <p v-if="layoutEditing" class="workbench-notice layout-help">{{ tr('拖动标题栏移动，拖动边缘缩放；通过“面板配置”调整标题、信号和标签分组。', 'Drag a header to move, an edge to resize. Panel settings manage titles, signals and tabs.') }}</p>
    <p v-if="layoutEditing" class="workbench-notice narrow-help">{{ tr('窄窗口以单列显示，可通过“面板配置”输入位置和尺寸。', 'Narrow windows use one column. Use Settings to enter positions and dimensions.') }}</p>
    <p v-if="loading">{{ tr('正在加载布局…', 'Loading layout…') }}</p>
    <div ref="grid" class="workbench-grid grid-stack" :aria-busy="loading">
      <article v-for="panel in orderedPanels" :key="restoreGeneration + ':' + panel.id + ':' + JSON.stringify(panel.source)" v-show="!dockFor(layout, panel.id) || dockFor(layout, panel.id)?.active === panel.id" class="grid-stack-item" :data-panel-id="panel.id" :data-grid-id="(!dockFor(layout, panel.id) || dockFor(layout, panel.id)?.active === panel.id) ? windowPanel(layout, panel.id).id : undefined">
        <div class="grid-stack-item-content workbench-card">
        <header class="workbench-card-header grid-drag-handle">
          <GripVertical v-if="layoutEditing" class="drag-handle" :size="16" aria-hidden="true" /><strong>{{ panel.title }}</strong>
          <span class="panel-kind">{{ labels[panel.type] }}</span>
          <button type="button" :aria-label="tr('请求 Agent 分析', 'Ask Agent')" @click="emit('intent', panel.id)">Agent</button>
          <button v-if="layoutEditing" type="button" :aria-label="tr('配置面板', 'Configure panel')" :aria-expanded="editing === panel.id" @click="edit(panel)"><SlidersHorizontal :size="14" />{{ tr('面板配置', 'Settings') }}</button>
          <button v-if="layoutEditing" type="button" :aria-label="tr('关闭面板', 'Close panel')" @click="remove(panel.id)"><X :size="16" /></button>
        </header>
        <div v-if="dockFor(layout, panel.id)" class="dock-tabs" role="tablist" :aria-label="tr('停靠窗口', 'Docked window')">
          <button v-for="id in dockFor(layout, panel.id)!.panels" :key="id" role="tab" :aria-selected="id === panel.id" @click="focus(id)">{{ find(id).title }}</button>
          <button v-if="layoutEditing" type="button" :aria-label="tr('分离当前面板', 'Undock current panel')" @click="undock(panel.id)">↗</button>
        </div>
        <WorkbenchSettingsDialog v-if="editing === panel.id" :title="tr('面板配置 · ', 'Panel settings · ') + panel.title" @close="editing = ''">
        <form class="panel-editor" @submit.prevent="applyEdit(panel)">
      <p v-if="error" role="alert">{{ error }}</p>
          <label>{{ tr('标题', 'Title') }}<input v-model="draft.title" maxlength="200" /></label>
          <label v-if="panel.type === 'watch' || panel.type === 'variables'">{{ tr('信号路径（逗号分隔；留空显示全部）', 'Signal paths (comma separated; empty means all)') }}<input v-model="draft.signals" /></label>
          <label v-if="panel.type === 'rtt'">RTT {{ tr('通道', 'channel') }}<input v-model.number="draft.channel" type="number" min="0" max="255" /></label>
          <label v-if="panel.type === 'serial'">{{ tr('串口', 'Port') }}<input v-model="draft.port" placeholder="COM3" /></label>
          <div class="geometry-fields"><label v-for="key in geometryKeys" :key="key">{{ geometryLabels[key] }}<input v-model.number="draft[key]" type="number" :min="key === 'x' || key === 'y' ? 0 : 1" :max="key === 'y' ? 200 : key === 'x' ? 11 : 12" /></label></div>
          <label>{{ tr('停靠到窗口（标签组）', 'Dock with window (tabs)') }}<select v-model="dockTarget"><option value="">{{ tr('选择窗口', 'Choose window') }}</option><option v-for="other in layout.panels.filter(item => item.id !== panel.id)" :key="other.id" :value="other.id">{{ other.title }}</option></select></label>
          <button type="button" class="btn btn-secondary" :disabled="!dockTarget" @click="userDock(panel.id)">{{ tr('停靠', 'Dock') }}</button>
          <button class="btn btn-primary" type="submit">{{ tr('应用', 'Apply') }}</button><button class="btn btn-secondary" type="button" @click="editing = ''">{{ tr('取消', 'Cancel') }}</button>
        </form>
        </WorkbenchSettingsDialog>
        <div class="workbench-card-content" @dragover.prevent @drop="dropControl($event, panel.id)">
          <WorkbenchPanel :ref="value => register(panel.id, value)" :panel="panel" :active="active !== false && (!dockFor(layout, panel.id) || dockFor(layout, panel.id)?.active === panel.id)" :device-connected="deviceConnected" :symbol-loaded="symbolLoaded" :symbol-error="symbolError" :latest-values="latestValues" :rtt="rtt" :snapshot-path="snapshotPath" :commit-widgets="widgets => setWidgets(panel.id, widgets)" @values="values => Object.assign(latestValues, values)" @snapshot="setSnapshotPath" @transfer="transfer => userTransfer(transfer.widgetId, transfer.targetPanelId)" />
        </div>
        </div>
      </article>
      <p v-if="!layout.panels.length" class="workbench-empty">{{ tr('添加波形、变量、RTT 或串口面板，组成你的工作区。', 'Add waveform, variable, RTT or serial panels to build your workspace.') }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted, onUnmounted, nextTick, watch, provide } from 'vue'
import { tr } from '../../composables/useLanguage'
import { API_BASE, IS_REMOTE } from '../../lib/runtimeEndpoint'
import { frontendRequest, objectSchema, interaction, type JsonObject, type SemanticSurface, type SemanticAction } from '../../lib/frontendControl'
import { addPanel, dockFor, dockPanel, undockPanel, removePanel, moveWindow, windowPanel, windowMinimum, upgradeLayout, geometrySchema, migrateLegacyWorkbench, panelInputSchema, panelSource, panelTypes, validateLayout, type PanelType, type WorkbenchLayout, type WorkbenchPanel as Panel } from '../../lib/workbenchLayout'
import { placeControl as placeWidget, controlStateKey, createControlState, type ControlWidget } from '../../lib/workbenchControls'
import { sameBinding } from '../../lib/workbenchBindings'
import { useWatchWorkspace } from '../../composables/useWatchWorkspace'
import WorkbenchPanel from './WorkbenchPanel.vue'
import WorkbenchSettingsDialog from '../WorkbenchSettingsDialog.vue'
import '../../assets/workbench.css'
import { GripVertical, SlidersHorizontal, X, LayoutDashboard } from '@lucide/vue'
import { useWorkbenchGrid } from '../../composables/useWorkbenchGrid'
import { layoutEditingKey } from '../../lib/workbenchControls'
const props = withDefaults(defineProps<{ deviceConnected: boolean; symbolLoaded: boolean; symbolError?: string; active?: boolean }>(), { active: true })
const layoutEditing = ref(false)
provide(layoutEditingKey, layoutEditing)
const controlState = createControlState()
provide(controlStateKey, controlState)
const emit = defineEmits<{ intent: [panelId: string] }>()
const labels = { watch: 'SuperWatch', variables: tr('变量', 'Variables'), rtt: 'RTT', serial: tr('串口', 'Serial'), controls: tr('控制面板', 'Controls'), capability: tr('操作与信息', 'Actions and information') }
const layout = ref<WorkbenchLayout>({ version: 2, revision: 0, panels: [], docks: [] })
const orderedPanels = computed(() => [...layout.value.panels].sort((a, b) => {
  const first = windowPanel(layout.value, a.id), second = windowPanel(layout.value, b.id)
  return first.y - second.y || first.x - second.x
}))
const restoreGeneration = ref(0)
const loading = ref(false), saving = ref(false), error = ref(''), notice = ref(''), reloadPrompt = ref(false)
const newType = ref<PanelType>('watch'), editing = ref('')
const dockTarget = ref('')
const draft = reactive({ title: '', signals: '', channel: 0, port: '', x: 0, y: 0, w: 6, h: 4 })
const geometryKeys = ['x', 'y', 'w', 'h'] as const
const geometryLabels = { x: tr('列位置', 'Column'), y: tr('行位置', 'Row'), w: tr('宽度（列）', 'Width (columns)'), h: tr('高度（行）', 'Height (rows)') }
const grid = ref<HTMLElement | null>(null)
const surfaces = new Map<string, SemanticSurface>()
const latestValues = reactive<Record<string, number>>({}), rtt = ref<JsonObject>({})
const snapshotPath = ref<string | null>(null)
let snapshotRevision = 0
function setSnapshotPath(path: string | null) { snapshotRevision++; snapshotPath.value = path }
let statusTimer: ReturnType<typeof setTimeout> | undefined, disposed = false
useWorkbenchGrid(grid, () => layout.value.panels.filter(panel => !dockFor(layout.value, panel.id) || dockFor(layout.value, panel.id)?.active === panel.id).map(panel => {
  const host = windowPanel(layout.value, panel.id), min = windowMinimum(layout.value, panel.id)
  return { id: host.id, x: host.x, y: host.y, w: host.w, h: host.h, minW: min.w, minH: min.h, maxW: 12, maxH: 12 }
}), layoutEditing, positions => change(draft => {
  for (const position of positions) Object.assign(windowPanel(draft, position.id), position)
}), cause => { error.value = String(cause) })
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
  layoutEditing.value = true
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
    const args = { title: draft.title, ...(panel.type === 'rtt' ? { channel: draft.channel } : panel.type === 'serial' ? { port: draft.port } : ['controls', 'capability'].includes(panel.type) ? {} : { signals: draft.signals.split(',').map(value => value.trim()).filter(Boolean) }) }
    interaction.validateArgs({ ...args, type: panel.type }, panelInputSchema)
    change(layout => {
      moveWindow(layout, panel.id, { x: draft.x, y: draft.y, w: draft.w, h: draft.h })
      const current = layout.panels.find(item => item.id === panel.id)!
      Object.assign(current, { title: args.title, source: panelSource(panel.type, args) }); delete current.view
    })
    editing.value = ''; error.value = ''
  } catch (cause) { error.value = String(cause) }
}
function userDock(id: string) { try { dock(id, dockTarget.value) } catch (cause) { error.value = String(cause) } }
function dropControl(event: DragEvent, target: string) {
  const raw = event.dataTransfer?.getData('application/x-mklink-control')
  if (!raw || find(target).type !== 'controls') return
  event.stopPropagation(); event.preventDefault()
  try { const item = JSON.parse(raw); if (item.panel_id !== target) transferControl(item.widget_id, target) } catch (cause) { error.value = String(cause) }
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
onUnmounted(() => { disposed = true; clearTimeout(statusTimer) })
defineExpose({ catalog, read, execute, entries, load })
</script>

<style scoped>
.workbench { display:flex; flex-direction:column; min-height:500px; gap:12px; padding:12px; overflow:auto; }
.workbench-toolbar,.workbench-actions { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.workbench-toolbar { justify-content:space-between; }.workbench-toolbar small { display:block; color:var(--muted); font-size:12px; margin-top:4px; }
.workbench-grid { min-height:350px; }
.workbench-card { display:flex; flex-direction:column; min-width:0; min-height:0; background:var(--surface); border:1px solid var(--border); border-radius:var(--radius,8px); overflow:hidden; }
.workbench-card-header { display:flex; align-items:center; flex:none; gap:8px; padding:8px 12px; min-height:44px; background:var(--bg); border-bottom:1px solid var(--border); } .is-editing .workbench-card-header { cursor:grab; }
.workbench-card-header strong { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:14px; }.workbench-card-header button { display:inline-flex; align-items:center; justify-content:center; gap:5px; min-height:28px; min-width:28px; padding:4px 7px; background:transparent; color:var(--fg); border:1px solid var(--border); border-radius:4px; cursor:pointer; }
.dock-tabs { display:flex; flex:none; gap:4px; padding:8px 12px; overflow:auto; border-bottom:1px solid var(--border); }.dock-tabs button { border:1px solid var(--border); border-radius:4px; padding:4px 8px; color:var(--fg); background:var(--surface); white-space:nowrap; cursor:pointer; }.dock-tabs button[aria-selected=true] { border-color:var(--accent); color:var(--accent); }
.panel-kind { color:var(--muted); font-size:12px; }.drag-handle { color:var(--muted); }
.workbench-card-content { position:relative; flex:1; min-height:0; overflow:auto; display:flex; flex-direction:column; }.workbench-card-content :deep(.symbol-panel) { width:100%; min-width:0; max-width:none; flex:1; }.workbench-card-content :deep(.waveform-viewer) { flex:1; min-height:240px; }.workbench-card-content :deep(.rtt-channel-panel) { flex:1; min-height:0; }
.panel-editor { padding:0; }.panel-editor label { display:flex; flex-direction:column; gap:8px; font-size:14px; margin-bottom:16px; }.panel-editor input { width:100%; min-width:0; box-sizing:border-box; }.geometry-fields { display:flex; gap:8px; }.geometry-fields label { flex:1; }.panel-editor button { margin-right:6px; }
.workbench-error { color:var(--danger,#e76b6b); margin:0; }.workbench-notice { font-size:12px; color:var(--muted); margin:0; }.workbench-empty { grid-column:1/-1; color:var(--muted); padding:36px; text-align:center; }
.workbench-actions > button { display:inline-flex; gap:6px; align-items:center; }
.workbench-card :is(button,input,select):focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
.workbench-grid :deep(.grid-stack-placeholder > .placeholder-content) { background:color-mix(in srgb,var(--accent) 12%,transparent); border:2px dashed var(--accent); border-radius:8px; }
.workbench-grid :deep(.ui-resizable-handle) { z-index:10; }
.workbench-grid :deep(.ui-resizable-se), .workbench-grid :deep(.ui-resizable-sw) { background-image:none; transform:none; width:18px; height:18px; }
.workbench-grid :deep(.ui-resizable-se::after), .workbench-grid :deep(.ui-resizable-sw::after) { content:''; position:absolute; inset:5px; border-bottom:1px solid var(--muted); opacity:0; }
.workbench-grid :deep(.ui-resizable-se::after) { border-right:1px solid var(--muted); }
.workbench-grid :deep(.ui-resizable-sw::after) { border-left:1px solid var(--muted); }
.workbench-grid :deep(.grid-stack-item:hover > .ui-resizable-handle::after), .workbench-grid :deep(.grid-stack-item:focus-within > .ui-resizable-handle::after) { opacity:.55; }
.narrow-help { display:none; }
@media(prefers-reduced-motion:reduce) { .workbench-grid :deep(.grid-stack-item) { transition:none!important; } }
@media(max-width:700px) { .layout-help { display:none; }.narrow-help { display:block; } .workbench-grid { display:flex; flex-direction:column; height:auto!important; flex-shrink:0; gap:8px; }.workbench-grid > .grid-stack-item { position:relative!important; inset:auto!important; width:100%!important; height:480px!important; flex-shrink:0; }.workbench-card { inset:0!important; }.workbench-grid :deep(.ui-resizable-handle) { display:none; } }
</style>
