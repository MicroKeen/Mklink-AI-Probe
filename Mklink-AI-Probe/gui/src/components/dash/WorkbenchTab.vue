<template>
  <section class="workbench" :class="{ 'is-editing': layoutEditing, 'is-reading': !!reading }" data-testid="workbench">
    <header class="workbench-toolbar">
      <div class="workbench-locator"><strong>{{ tr('灵活面板', 'Flexible Panels') }}</strong>
        <select v-if="layout.panels.length" :aria-label="tr('定位面板', 'Go to panel')" :value="reading || ''" @change="jump(($event.target as HTMLSelectElement).value); ($event.target as HTMLSelectElement).value = reading">
          <option disabled value="">{{ tr('定位面板…', 'Go to panel…') }}</option>
          <option v-for="panel in orderedPanels" :key="panel.id" :value="panel.id">{{ locatorLabel(panel) }}</option>
        </select>
        <button v-if="locateTarget && layout.panels.some(panel => panel.id === locateTarget)" type="button" class="locate-update" @click="jump(locateTarget); clearLocator()">{{ tr('定位到图表', 'Go to updated chart') }}</button>
        <button type="button" class="btn btn-secondary help-button" aria-haspopup="dialog" data-testid="workbench-help" @click="helpOpen = true">{{ tr('帮助', 'Help') }}</button>
      </div>
      <div v-if="reading" class="workbench-actions reading-actions">
        <button class="btn btn-secondary" type="button" :disabled="!floatSupported" :title="floatHint" @click="toggleFloat(reading)">{{ floating?.id === reading ? tr('收回浮窗', 'Return from float') : tr('浮窗置顶', 'Float on top') }}</button>
        <small v-if="!floatSupported" class="workbench-notice">{{ tr('此环境仅支持专注查看', 'Enlarged view only in this browser') }}</small>
        <button class="btn btn-primary" @click="viewPanel('')">{{ tr('返回布局', 'Back to layout') }}</button>
      </div>
      <div v-else class="workbench-actions">
        <button class="btn" :class="layoutEditing ? 'btn-primary' : 'btn-secondary'" :aria-pressed="layoutEditing" @click="layoutEditing = !layoutEditing"><LayoutDashboard :size="16" />{{ layoutEditing ? tr('完成布局', 'Done editing') : tr('编辑布局', 'Edit layout') }}</button>
        <select v-if="layoutEditing" v-model="newType" :aria-label="tr('新面板类型', 'New panel type')"><option v-for="type in panelTypes.filter(type => type !== 'tool')" :key="type" :value="type">{{ labels[type] }}</option><optgroup :label="tr('完整功能视图', 'Complete GUI views')"><option v-for="tool in availableTools" :key="tool" :value="'tool:' + tool">{{ toolLabel(tool) }}</option></optgroup></select>
        <button v-if="layoutEditing" class="btn btn-secondary" data-testid="add-panel" @click="userAdd">＋ {{ tr('添加面板', 'Add panel') }}</button>
        <button class="btn" :class="dirty ? 'btn-primary' : 'btn-secondary'" :disabled="loading || saving || !dirty" :title="dirty ? tr('保存未保存的更改', 'Save pending changes') : tr('当前布局已保存', 'No pending changes')" data-testid="save-layout" @click="userSave">{{ saving ? tr('保存中…', 'Saving…') : tr('保存布局', 'Save layout') }}</button>
        <button class="btn btn-secondary" :disabled="loading || saving" @click="libraryMode = 'save'">{{ tr('另存为…', 'Save as…') }}</button>
        <button v-if="layout.closed?.length" class="btn btn-secondary" type="button" data-testid="recently-closed" @click="showClosed = true">{{ tr('最近关闭', 'Recently closed') }} ({{ layout.closed.length }})</button>
        <button class="btn btn-secondary" :disabled="loading || saving" data-testid="load-layout" @click="libraryMode = 'load'">{{ tr('加载布局', 'Load layout') }}</button>
      </div>
    </header>
    <WorkbenchAgentFeedback :rejection="agentFeedback?.rejections.get('')" />
    <WorkbenchHelpDialog v-if="helpOpen" @close="helpOpen = false" />
    <WorkbenchSettingsDialog v-if="closing" :title="tr('关闭面板？', 'Close panel?')" @close="closing = ''">
      <p>{{ tr('关闭“' + find(closing).title + '”？稍后可从“最近关闭”恢复。', 'Close “' + find(closing).title + '”? You can restore it from Recently closed.') }}</p>
      <p v-if="layout.closed?.length === 32">{{ tr('将替换最早的一条关闭记录。', 'This will replace the oldest closed panel.') }}</p>
      <div class="dialog-actions"><button type="button" class="btn btn-secondary" autofocus @click="closing = ''">{{ tr('取消', 'Cancel') }}</button>
      <button type="button" class="btn btn-primary" data-testid="confirm-close-panel" @click="confirmClose">{{ tr('关闭面板', 'Close panel') }}</button></div>
    </WorkbenchSettingsDialog>
    <WorkbenchSettingsDialog v-if="showClosed" :title="tr('最近关闭', 'Recently closed')" @close="showClosed = false">
      <ul class="closed-panels"><li v-for="panel in layout.closed" :key="panel.id"><span>{{ panel.title }}<small v-if="panel.title !== labels[panel.type]">{{ labels[panel.type] }}</small></span>
        <button type="button" class="btn btn-secondary" :data-reopen-id="panel.id" @click="userReopen(panel.id)">{{ tr('恢复面板', 'Restore panel') }}</button></li></ul>
    </WorkbenchSettingsDialog>
    <WorkbenchLayoutDialog v-if="libraryMode" :mode="libraryMode" :search="searchLayouts" :save="(name, revision, scope) => saveNamed(name, revision, scope)" :load="(name, scope) => load(name, scope)" @close="libraryMode = null" @restore="libraryMode = null; reloadPrompt = true" />
    <div v-if="reloadPrompt" class="workbench-notice" role="alert">
      {{ tr('恢复会替换当前未保存的面板配置。', 'Restoring replaces the current unsaved panel configuration.') }}
      <button class="btn btn-secondary" @click="userLoad">{{ tr('恢复', 'Restore') }}</button><button class="btn btn-secondary" @click="reloadPrompt = false">{{ tr('取消', 'Cancel') }}</button>
    </div>
    <p v-if="error" class="workbench-error" role="alert">{{ error }}</p>
    <p v-if="notice && !(dirty && notice === savedNotice)" class="workbench-notice" role="status">{{ notice }}</p>
    <p v-if="layoutEditing && !reading" class="workbench-notice layout-help">{{ tr('拖动标题移动，拖动把手到另一面板可分栏或合并标签。', 'Drag a title to move, or drag its grip onto another panel to split or group tabs.') }}</p>
    <p v-if="layoutEditing && !reading" class="workbench-notice narrow-help">{{ tr('窄窗口可拖动标题排序，拖动底边调整高度。', 'Drag a title to reorder the column, or drag the bottom edge to adjust height.') }}</p>
    <p v-if="loading">{{ tr('正在加载布局…', 'Loading layout…') }}</p>
    <div ref="viewport" class="workbench-viewport">
    <div ref="grid" class="workbench-grid grid-stack" :aria-busy="loading">
      <article :class="{ 'reading-card': reading === panel.id }" v-for="panel in orderedPanels" :key="restoreGeneration + ':' + panel.id + ':' + JSON.stringify(panel.source)" v-show="!dockFor(layout, panel.id) || dockFor(layout, panel.id)?.active === panel.id" class="grid-stack-item" @dragover="rowOver($event)" @drop="rowDrop($event, panel.id)" :data-panel-id="panel.id" :style="{ '--panel-height': windowPanel(layout, panel.id).h * gridRowHeight + 'px' }" :data-grid-id="(!dockFor(layout, panel.id) || dockFor(layout, panel.id)?.active === panel.id) ? windowPanel(layout, panel.id).id : undefined">
        <div class="grid-stack-item-content workbench-card" :data-agent-target="panel.id">
        <header tabindex="0" aria-keyshortcuts="Alt+ArrowUp Alt+ArrowDown" class="workbench-card-header grid-drag-handle" :title="reading ? undefined : tr('拖动标题移动面板；Alt + 上下键调整顺序', 'Drag the title to move; Alt + Up or Down to reorder')" @keydown.alt.up.self.prevent="shiftRow(panel.id, -1)" @keydown.alt.down.self.prevent="shiftRow(panel.id, 1)">
          <button v-if="layoutEditing && !reading" class="dock-grip" type="button" draggable="true" :aria-label="tr('吸附到面板', 'Snap to panel')" :title="tr('拖到另一面板分栏或合并标签，点击可选目标', 'Drag onto another panel to split or group tabs, or click to choose')"
            @click="edit(panel)" @dragstart.stop="startSnap($event, panel.id)" @dragend="snapSource = ''"><GripVertical :size="15" /></button>
          <div class="panel-heading-text"><strong :title="panel.title" :draggable="narrow && !reading" @dragstart="rowStart($event, panel.id)" @dragend="rowSource = ''">{{ panel.title }}</strong>
            <WorkbenchAgentFeedback v-if="floating?.id !== panel.id" :update="agentFeedback?.updates.get(panel.id)" />
          </div>
          <span v-if="panel.title !== (panel.source.tool ? toolLabel(panel.source.tool) : labels[panel.type])" class="panel-kind">{{ panel.source.tool ? toolLabel(panel.source.tool) : labels[panel.type] }}</span>
          <div class="workbench-header-actions">
            <button type="button" :aria-label="tr('请求 Agent 分析', 'Ask Agent')" @click="emit('intent', panel.id)">Agent</button>
            <button v-if="!reading" type="button" class="panel-read" :aria-label="tr('专注查看', 'Enlarge panel')" :title="tr('专注查看', 'Enlarge panel')" @click="viewPanel(panel.id)"><Maximize2 :size="15" /></button>
            <button v-if="layoutEditing && !reading" type="button" :aria-label="tr('配置面板', 'Configure panel')" :aria-expanded="editing === panel.id" @click="edit(panel)"><SlidersHorizontal :size="14" />{{ tr('面板配置', 'Settings') }}</button>
            <button type="button" :title="tr('关闭面板', 'Close panel')" :aria-label="tr('关闭面板', 'Close panel')" @click="closing = panel.id"><X :size="16" /></button>
          </div>
        </header>
        <WorkbenchAgentFeedback v-if="floating?.id !== panel.id" :rejection="agentFeedback?.rejections.get(panel.id)" :focused="reading === panel.id" />
        <div v-if="dockFor(layout, panel.id)" class="dock-tabs" role="tablist" :aria-label="tr('停靠窗口', 'Docked window')">
          <button v-for="id in dockFor(layout, panel.id)!.panels" :key="id" role="tab" :aria-selected="id === panel.id" :tabindex="id === panel.id ? 0 : -1" @click="selectTab(id)" @keydown="tabKey($event, id)">{{ find(id).title }}</button>
          <button v-if="layoutEditing" type="button" :aria-label="tr('分离当前面板', 'Undock current panel')" @click="undock(panel.id)">↗</button>
        </div>
        <WorkbenchSettingsDialog v-if="editing === panel.id" :title="tr('面板配置 · ', 'Panel settings · ') + panel.title" @close="editing = ''">
        <form class="panel-editor" @submit.prevent="applyEdit(panel)">
      <p v-if="error" role="alert">{{ error }}</p>
          <label>{{ tr('标题', 'Title') }}<input v-model="draft.title" maxlength="200" /></label>
          <label v-if="panel.type === 'watch' || panel.type === 'variables'">{{ tr('信号路径（逗号分隔；留空显示全部）', 'Signal paths (comma separated; empty means all)') }}<input v-model="draft.signals" /></label>
          <label v-if="panel.type === 'rtt'">RTT {{ tr('通道', 'channel') }}<input v-model.number="draft.channel" type="number" min="0" max="255" /></label>
          <label v-if="panel.type === 'serial'">{{ tr('串口', 'Port') }}<input v-model="draft.port" placeholder="COM3" /></label>
          <div class="geometry-fields"><label v-for="key in geometryKeys" :key="key">{{ geometryLabels[key] }}<input v-model.number="draft[key]" type="number" :min="key === 'x' || key === 'y' ? 0 : 1" :max="geometrySchema[key].maximum" /></label></div>
          <label>{{ tr('组合窗口', 'Arrange with panel') }}<select v-model="dockTarget"><option value="">{{ tr('选择窗口', 'Choose window') }}</option><option v-for="other in layout.panels.filter(item => item.id !== panel.id)" :key="other.id" :value="other.id">{{ other.title }}</option></select></label>
          <button type="button" class="btn btn-secondary" :disabled="!dockTarget || windowPanel(layout, panel.id) === windowPanel(layout, dockTarget)" @click="userSplit(panel.id)">{{ tr('左右分栏', 'Split side by side') }}</button>
          <button type="button" class="btn btn-secondary" :disabled="!dockTarget" @click="userDock(panel.id)">{{ tr('停靠', 'Dock') }}</button>
          <button class="btn btn-primary" type="submit">{{ tr('应用', 'Apply') }}</button><button class="btn btn-secondary" type="button" @click="editing = ''">{{ tr('取消', 'Cancel') }}</button>
        </form>
        </WorkbenchSettingsDialog>
        <div v-if="snapSource && windowPanel(layout, snapSource) !== windowPanel(layout, panel.id)" class="panel-drop-zones">
          <button v-for="edge in snapEdges" :key="edge" type="button" tabindex="-1" :data-snap-edge="edge"
            @dragover.prevent @drop.prevent.stop="snapDrop($event, panel.id, edge)">{{ edge === 'left' ? tr('左分栏', 'Split left') : edge === 'right' ? tr('右分栏', 'Split right') : tr('合并标签', 'Group tabs') }}</button>
        </div>
        <button v-if="floating?.id === panel.id" type="button" class="float-placeholder btn btn-secondary" @click="returnFloat">{{ tr('正在浮窗中显示 · 收回', 'Showing in floating window · Return') }}</button>
        <Teleport :to="floating?.id === panel.id ? floating.mount : 'body'" :disabled="floating?.id !== panel.id">
        <header v-if="floating?.id === panel.id" class="float-heading">
          <div class="panel-heading-text"><strong>{{ panel.title }}</strong><WorkbenchAgentFeedback :update="agentFeedback?.updates.get(panel.id)" /></div>
          <button type="button" class="btn btn-secondary" @click="returnFloat">{{ tr('返回布局', 'Back to layout') }}</button></header>
        <WorkbenchAgentFeedback v-if="floating?.id === panel.id" :rejection="agentFeedback?.rejections.get(panel.id)" :focused="reading === panel.id" />
        <div class="workbench-card-content" @dragover.prevent @drop="dropControl($event, panel.id)">
          <WorkbenchPanel :ref="value => register(panel.id, value)" :panel="panel" :active="floating?.id === panel.id || (active !== false && (!dockFor(layout, panel.id) || dockFor(layout, panel.id)?.active === panel.id))" :device-connected="deviceConnected" :symbol-loaded="symbolLoaded" :symbol-error="symbolError" :latest-values="latestValues" :rtt="rtt" :snapshot-path="snapshotPath" :commit-widgets="widgets => setWidgets(panel.id, widgets)" @view-interaction="watchView(panel.id)" @values="values => Object.assign(latestValues, values)" @snapshot="setSnapshotPath" @transfer="transfer => userTransfer(transfer.widgetId, transfer.targetPanelId)" />
        </div>
        </Teleport>
        <NarrowPanelResize v-if="!reading" :height="windowPanel(layout, panel.id).h" :minimum="windowMinimum(layout, panel.id).h" @resize="height => resizePanel(panel.id, height)" />
        </div>
        <PanelColumnDivider v-if="!reading && dividers[panel.id]" v-bind="dividers[panel.id]!" @resize="width => resizePair(panel.id, width)" />
      </article>
      <p v-if="!layout.panels.length" class="workbench-empty">{{ tr('添加波形、变量、RTT 或串口面板，组成你的工作区。', 'Add waveform, variable, RTT or serial panels to build your workspace.') }}</p>
    </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted, onUnmounted, nextTick, watch, provide } from 'vue'
import { tr } from '../../composables/useLanguage'
import { API_BASE, IS_REMOTE } from '../../lib/runtimeEndpoint'
import { frontendRequest, objectSchema, interaction, type JsonObject, type SemanticSurface, type SemanticAction, type SemanticExecutionContext } from '../../lib/frontendControl'
import { addPanel, splitPanels, visibleWindows, dockFor, dockPanel, undockPanel, removePanel, reopenPanel, reorderWindow, moveWindow, windowPanel, windowMinimum, upgradeLayout, geometrySchema, migrateLegacyWorkbench, panelInputSchema, panelSource, panelTypes, validateLayout, type PanelType, type WorkbenchLayout, type WorkbenchPanel as Panel } from '../../lib/workbenchLayout'
import { placeControl as placeWidget, controlStateKey, createControlState, type ControlWidget } from '../../lib/workbenchControls'
import { sameBinding } from '../../lib/workbenchBindings'
import { useWatchWorkspace } from '../../composables/useWatchWorkspace'
import { usePanelFloat } from '../../composables/usePanelFloat'
import PanelColumnDivider from './PanelColumnDivider.vue'
import NarrowPanelResize from './NarrowPanelResize.vue'
import WorkbenchPanel from './WorkbenchPanel.vue'
import WorkbenchLayoutDialog from './WorkbenchLayoutDialog.vue'
import WorkbenchSettingsDialog from '../WorkbenchSettingsDialog.vue'
import WorkbenchHelpDialog from './WorkbenchHelpDialog.vue'
import '../../assets/workbench.css'
import WorkbenchAgentFeedback from './WorkbenchAgentFeedback.vue'
import type { PanelFeedback } from '../../composables/useFrontendWorkbench'
import { Maximize2, GripVertical, SlidersHorizontal, X, LayoutDashboard } from '@lucide/vue'
import { geometryKeys, geometryLabels, gridRowHeight, useWorkbenchGrid } from '../../composables/useWorkbenchGrid'
import { layoutEditingKey } from '../../lib/workbenchControls'
import { toolTypes, toolLabel, remoteTools, type WorkbenchTool } from '../../lib/workbenchTools'
import { inject } from 'vue'
import { createWorkbenchActivity, workbenchActivityKey } from '../../lib/workbenchActivity'
const props = withDefaults(defineProps<{ deviceConnected: boolean; symbolLoaded: boolean; symbolError?: string; active?: boolean; agentFeedback?: PanelFeedback }>(), { active: true })
const { current: floating, open: openFloat, close: returnFloat, supported: floatSupported } = usePanelFloat()
const floatHint = computed(() => floatSupported ? tr('在其他应用上方查看这个面板', 'View this panel above other apps') : tr('当前环境不支持系统级画中画，可用专注查看', 'System picture-in-picture unavailable; use enlarged view'))
const helpOpen = ref(false)
const reading = ref('')
const closing = ref(''), showClosed = ref(false)
const narrowWidth = window.matchMedia('(max-width: 700px)')
const narrow = ref(narrowWidth.matches), rowSource = ref('')
function widthChanged() { narrow.value = narrowWidth.matches }
function rowStart(e: DragEvent, id: string) {
  if (!narrow.value || reading.value || !e.dataTransfer) return
  rowSource.value = id
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('application/x-mklink-row', id)
}
function rowOver(e: DragEvent) { if (rowSource.value) e.preventDefault() }
function rowDrop(e: DragEvent, target: string) {
  const id = rowSource.value
  if (!id || e.dataTransfer?.getData('application/x-mklink-row') !== id) return
  e.preventDefault(); rowSource.value = ''
  reorder(id, target)
}
function reorder(id: string, target: string) {
  try { change(draft => reorderWindow(draft, id, target)); jump(id) } catch (cause) { error.value = String(cause) }
}
function shiftRow(id: string, step: number) {
  if (reading.value) return
  const windows = orderedPanels.value.filter(panel => windowPanel(layout.value, panel.id).id === panel.id)
  const target = windows[windows.indexOf(windowPanel(layout.value, id)) + step]
  if (target) reorder(id, target.id)
}

const viewport = ref<HTMLElement | null>(null)
const layoutEditing = ref(false)
provide(layoutEditingKey, layoutEditing)
provide(workbenchActivityKey, inject(workbenchActivityKey, null) || createWorkbenchActivity())
const availableTools = computed(() => IS_REMOTE ? remoteTools : toolTypes)
const controlState = createControlState()
provide(controlStateKey, controlState)
const emit = defineEmits<{ intent: [panelId: string] }>()
const labels = computed(() => ({ watch: 'SuperWatch', variables: tr('变量', 'Variables'), rtt: 'RTT', serial: tr('串口', 'Serial'), controls: tr('控制面板', 'Controls'), capability: tr('操作与信息', 'Actions and information'), tool: tr('功能面板', 'GUI tool'), log: tr('日志与问答', 'Log and conversation'), information: tr('信息面板', 'Information'), chart: tr('分析图表', 'Analysis chart') }))
const layout = ref<WorkbenchLayout>({ version: 2, revision: 0, panels: [], docks: [] })
const orderedPanels = computed(() => [...layout.value.panels].sort((a, b) => {
  const first = windowPanel(layout.value, a.id), second = windowPanel(layout.value, b.id)
  return first.y - second.y || first.x - second.x
}))
function locatorLabel(panel: WorkbenchLayout['panels'][number]) {
  const matches = orderedPanels.value.filter(other => other.title === panel.title)
  return matches.length > 1 ? panel.title + ' (' + (matches.indexOf(panel) + 1) + '/' + matches.length + ')' : panel.title
}
const restoreGeneration = ref(0)
const loading = ref(false), saving = ref(false), error = ref(''), notice = ref(''), reloadPrompt = ref(false)
const libraryMode = ref<'save' | 'load' | null>(null)
const newType = ref<string>('watch'), editing = ref('')
const dockTarget = ref('')
const draft = reactive({ title: '', signals: '', channel: 0, port: '', x: 0, y: 0, w: 6, h: 4 })
const grid = ref<HTMLElement | null>(null)
const surfaces = new Map<string, SemanticSurface>()
const latestValues = reactive<Record<string, number>>({}), rtt = ref<JsonObject>({})
const snapshotPath = ref<string | null>(null)
let snapshotRevision = 0
function setSnapshotPath(path: string | null) { snapshotRevision++; snapshotPath.value = path }
let statusTimer: ReturnType<typeof setTimeout> | undefined, disposed = false
useWorkbenchGrid(grid, () => layout.value.panels.filter(panel => !dockFor(layout.value, panel.id) || dockFor(layout.value, panel.id)?.active === panel.id).map(panel => {
  const host = windowPanel(layout.value, panel.id), min = windowMinimum(layout.value, panel.id)
  return { id: host.id, x: host.x, y: host.y, w: host.w, h: host.h, minW: min.w, minH: min.h, maxW: 12, maxH: geometrySchema.h.maximum }
}), computed(() => !reading.value), positions => change(draft => {
  for (const position of positions) Object.assign(windowPanel(draft, position.id), position)
}), cause => { error.value = String(cause) })
const dividers = computed(() => {
  const result: Record<string, { width: number; span: number; minimum: number; maximum: number; rightId: string }> = {}
  const windows = visibleWindows(layout.value)
  for (const left of windows) {
    const right = windows.find(p => p.x === left.x + left.w && p.y === left.y && p.h === left.h)
    if (!right) continue
    const span = left.w + right.w, minimum = windowMinimum(layout.value, left.id).w, maximum = span - windowMinimum(layout.value, right.id).w
    if (minimum < maximum) result[dockFor(layout.value, left.id)?.active || left.id] = { width: left.w, span, minimum, maximum, rightId: right.id }
  }
  return result
})
function resizePair(left: string, width: number) {
  const pair = dividers.value[left]
  if (pair) try { change(draft => splitPanels(draft, left, pair.rightId, width)) } catch (cause) { error.value = String(cause) }
}
const snapSource = ref('')
const snapEdges = ['left','tabs','right'] as const
function startSnap(event: DragEvent, id: string) {
  if (!event.dataTransfer) return
  snapSource.value = id
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('application/x-mklink-panel', id)
}
function snapDrop(event: DragEvent, target: string, edge: typeof snapEdges[number]) {
  const source = snapSource.value
  snapSource.value = ''
  if (!source || event.dataTransfer?.getData('application/x-mklink-panel') !== source) return
  try {
    if (edge === 'tabs') dock(source, target)
    else change(draft => edge === 'left' ? splitPanels(draft, source, target) : splitPanels(draft, target, source))
    jump(source)
  } catch (cause) { error.value = String(cause) }
}
function userSplit(id: string) {
  try { change(draft => splitPanels(draft, id, dockTarget.value)); editing.value = ''; jump(id) } catch (cause) { error.value = String(cause) }
}
function selectTab(id: string) {
  focus(id)
  void nextTick(() => card(id)?.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]')?.focus({ preventScroll: true }))
}
function tabKey(event: KeyboardEvent, id: string) {
  const tabs = dockFor(layout.value, id)?.panels
  if (!tabs?.length) return
  const i = tabs.indexOf(id)
  const positions: Record<string, number> = { ArrowLeft: (i + tabs.length - 1) % tabs.length, ArrowRight: (i + 1) % tabs.length, Home: 0, End: tabs.length - 1 }
  if (!(event.key in positions)) return
  event.preventDefault()
  selectTab(tabs[positions[event.key]!]!)
}
function card(id: string) { return grid.value?.querySelector<HTMLElement>('article[data-panel-id="' + CSS.escape(id) + '"]') }
const locateTarget = ref('')
let locateTimer: ReturnType<typeof setTimeout> | undefined
let locateObserver: IntersectionObserver | undefined
function clearLocator() {
  clearTimeout(locateTimer)
  locateObserver?.disconnect()
  locateTarget.value = ''
}
watch(() => Array.from(props.agentFeedback?.updates.values() ?? []), (updates, previous) => {
  const latest = updates.filter(item => !previous.some(old => old.id === item.id)).pop()
  if (!latest) return
  clearLocator()
  const id = latest.target
  if (floating.value?.id === id || !layout.value.panels.some(panel => panel.id === id && panel.type === 'chart')) return
  const header = card(id)?.querySelector('header')
  if (!header || !viewport.value || typeof IntersectionObserver === 'undefined') return
  locateObserver = new IntersectionObserver(([entry]) => {
    if (!entry) return
    if (entry.isIntersecting && entry.intersectionRect.height > 0) clearLocator()
    else locateTarget.value = id
  }, { root: viewport.value })
  locateObserver.observe(header)
  locateTimer = setTimeout(clearLocator, 8000)
}, { flush: 'post' })
onUnmounted(clearLocator)
function jump(id: string) {
  focus(id)
  void nextTick(() => {
    const header = card(id)?.querySelector<HTMLElement>('.workbench-card-header')
    header?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' })
    header?.focus({ preventScroll: true })
  })
}
let previousScroll = 0
function viewPanel(id: string) {
  const previous = reading.value
  if (id) {
    if (!previous) previousScroll = viewport.value?.scrollTop || 0
    reading.value = id; jump(id)
  } else {
    reading.value = ''
    void nextTick(() => {
      if (viewport.value) viewport.value.scrollTop = previousScroll
      card(previous)?.querySelector<HTMLElement>('.panel-read')?.focus({ preventScroll: true })
    })
  }
}
async function toggleFloat(id: string) {
  if (floating.value?.id === id) { returnFloat(); return }
  try {
    const origin = card(id)
    if (origin) { await openFloat(id, find(id).title, origin); if (floating.value?.id === id) viewPanel('') }
  } catch (cause) {
    error.value = cause instanceof DOMException && ['NotAllowedError', 'NotSupportedError'].includes(cause.name)
      ? tr('当前窗口未允许置顶，可继续专注查看。', 'This window could not open an always-on-top view. Enlarged view is available.')
      : String(cause)
  }
}
function leaveReading(event: KeyboardEvent) {
  if (event.key !== 'Escape' || !reading.value || event.defaultPrevented) return
  const dialogs = document.querySelectorAll('dialog[open], [aria-modal="true"]')
  if (!Array.from(dialogs).some(el => el.getClientRects().length)) viewPanel('')
}
function register(id: string, value: unknown) { if (value) surfaces.set(id, value as SemanticSurface); else surfaces.delete(id) }
// Only compare persisted view fields after interaction. Sensor readings, logs and playback clocks are excluded.
const watchedViews = new Map<string, string | undefined>()
const changedViews = ref(false)
let viewTimer: ReturnType<typeof setTimeout> | undefined
const viewKey = (id: string) => JSON.stringify(surfaces.get(id)?.read?.().view)
function watchView(id: string) {
  if (!watchedViews.has(id)) watchedViews.set(id, viewKey(id))
  clearTimeout(viewTimer)
  viewTimer = setTimeout(checkViews, 0)
}
function checkViews() {
  changedViews.value = Array.from(watchedViews).some(([id, baseline]) => surfaces.has(id) && viewKey(id) !== baseline)
}
function layoutKey(value: WorkbenchLayout) {
  return JSON.stringify([value.panels.map(({ view, ...panel }) => panel).sort((a, b) => a.id.localeCompare(b.id)), value.docks, value.closed || []])
}
const savedKey = ref(layoutKey(layout.value)), imported = ref(false)
const dirty = computed(() => imported.value || changedViews.value || layoutKey(layout.value) !== savedKey.value)
const savedNotice = computed(() => tr('布局已保存。恢复布局不会启动采集或连接设备。', 'Layout saved. Restoring it does not start acquisition or connect devices.'))
function entries() { return layout.value.panels.map(panel => ({ id: panel.id, title: panel.title, type: panel.type, source: panel.source, surface: surfaces.get(panel.id) })) }
function read() { return { layout: layout.value, dirty: dirty.value, snapshotPath: snapshotPath.value, loading: loading.value, saving: saving.value, error: error.value, editing: editing.value, enlarged: reading.value, floating: floating.value?.id || null } }
function find(id: string) { const panel = layout.value.panels.find(item => item.id === id); if (!panel) throw new Error('Panel no longer exists'); return panel }
function change<T>(mutate: (draft: WorkbenchLayout) => T): T {
  const draft = JSON.parse(JSON.stringify(layout.value)) as WorkbenchLayout
  const result = mutate(draft)
  layout.value = validateLayout(draft)
  return result
}
function remove(id: string) {
  if (snapSource.value === id) snapSource.value = ''
  const panel = find(id), widgets = panel.widgets || []
  if (widgets.some(widget => ['running','unknown'].includes(controlState.statuses[widget.id]?.status || ''))) throw new Error(tr('请先核对进行中或结果未知的操作。', 'Inspect the pending or unknown operation before closing.'))
  const view = surfaces.get(id)?.read?.().view || panel.view
  const { x, y, w, h } = windowPanel(layout.value, id)
  const dockWith = dockFor(layout.value, id)?.panels.find(member => member !== id)
  change(draft => {
    removePanel(draft, id)
    draft.closed = [{ ...panel, x, y, w, h, ...(dockWith ? { dockWith } : {}), ...(view ? { view } : {}) }, ...(draft.closed || [])].slice(0, 32)
  })
  for (const tracked of watchedViews.keys()) if (!layout.value.panels.some(p => p.id === tracked) && !layout.value.closed?.some(p => p.id === tracked)) watchedViews.delete(tracked)
  checkViews()
  if (closing.value === id) closing.value = ''
  for (const widget of widgets) controlState.clear(widget.id)
  if (reading.value === id) viewPanel('')
  if (floating.value?.id === id) returnFloat()
  if (editing.value === id) editing.value = ''
}
function confirmClose() {
  try { remove(closing.value); void nextTick(() => viewport.value?.parentElement?.querySelector<HTMLElement>('[data-testid=recently-closed]')?.focus({ preventScroll: true })) }
  catch (cause) { closing.value = ''; error.value = String(cause) }
}
function reopen(id: string) {
  const panel = change(draft => reopenPanel(draft, id))
  showClosed.value = false; jump(id)
  return panel
}
function userReopen(id: string) { try { reopen(id) } catch (cause) { showClosed.value = false; error.value = String(cause) } }
function move(id: string, geometry: JsonObject) { return change(draft => moveWindow(draft, id, geometry)) }
function resizePanel(id: string, h: number) {
  try { move(id, { h }); error.value = '' } catch (cause) { error.value = String(cause) }
}
function dock(id: string, target: string) { change(draft => dockPanel(draft, id, target)); editing.value = '' }
function undock(id: string) { change(draft => undockPanel(draft, id)) }
function focus(id: string) {
  find(id)
  const dock = dockFor(layout.value, id)
  if (dock) dock.active = id
  if (reading.value) reading.value = id
}
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
async function save(context?: SemanticExecutionContext) {
  saving.value = true; error.value = ''; notice.value = ''
  try {
    const payload = capture(), generation = restoreGeneration.value
    const saved = validateLayout(await frontendRequest('layout', payload, 'PUT', context))
    if (generation !== restoreGeneration.value) return { revision: saved.revision }
    savedKey.value = layoutKey(payload); imported.value = false
    for (const id of watchedViews.keys()) watchedViews.set(id, JSON.stringify(payload.panels.find(panel => panel.id === id)?.view))
    checkViews()
    layout.value.revision = saved.revision
    notice.value = savedNotice.value
    return { revision: saved.revision }
  } finally { saving.value = false }
}
async function searchLayouts(query = '', scope = 'project', context?: SemanticExecutionContext) {
  return frontendRequest(`layouts?scope=${scope}&query=${encodeURIComponent(query)}`, undefined, 'GET', context)
}
async function saveNamed(name: string, revision = 0, scope = 'project', context?: SemanticExecutionContext) {
  saving.value = true; error.value = ''; notice.value = ''
  try {
    const result = await frontendRequest('layouts', { name, revision, scope, layout: capture() }, 'POST', context)
    const destination = scope === 'global' ? tr('全局模板', 'global templates') : tr('工程布局库', 'project layout library')
    notice.value = tr(`布局“${result.name}”已保存到${destination}。`, `Saved “${result.name}” to ${destination}.`)
    return { ...result, scope }
  } finally { saving.value = false }
}
async function load(name?: string, scope = 'project', context?: SemanticExecutionContext) {
  loading.value = true; error.value = ''; notice.value = ''; reloadPrompt.value = false
  try {
    const saved = name
      ? { ...validateLayout((await frontendRequest(`layouts/item?scope=${scope}&name=${encodeURIComponent(name)}`, undefined, 'GET', context)).layout), revision: layout.value.revision }
      : validateLayout(await frontendRequest('layout', undefined, 'GET', context))
    let migration: ReturnType<typeof migrateLegacyWorkbench> | undefined
    if (!name && saved.revision === 0 && saved.panels.length === 0) {
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
    returnFloat(); reading.value = ''; snapSource.value = ''; closing.value = ''; showClosed.value = false; rowSource.value = ''
    watchedViews.clear(); changedViews.value = false
    if (!name) savedKey.value = layoutKey(upgraded)
    imported.value = !!name || !!migration?.migrated
    layout.value = upgraded
    if (name) notice.value = tr(`已加载“${name}”；点击“保存布局”可将它设为下次打开的当前布局。`, `Loaded “${name}”; Save layout to make it the current layout on next opening.`)
    if (saved.version === 1 && !migration) notice.value = tr('旧布局已适配组件最小尺寸；保存后升级为版本 2。', 'Legacy layout adapted to component minimum sizes; save to upgrade to version 2.')
    restoreGeneration.value++
    await nextTick()
    return { revision: saved.revision, panels: layout.value.panels.length, layout_loaded: true, name: name || null, migrated: migration?.migrated || false, unsaved: !!name || migration?.migrated || false, view_restoration: 'Components restore display settings as they become ready; inspect each panel state.' }
  } finally { loading.value = false }
}
async function userSave() { try { await save() } catch (cause) { error.value = String(cause) } }
async function userLoad() { try { await load() } catch (cause) { error.value = String(cause) } }
function userAdd() {
  try { const tool = newType.value.startsWith('tool:') ? newType.value.slice(5) as WorkbenchTool : null; create({ type: tool ? 'tool' : newType.value, title: tool ? toolLabel(tool) : `${labels.value[newType.value as PanelType]} ${layout.value.panels.length + 1}`, ...(tool ? { tool } : {}) }) } catch (cause) { error.value = String(cause) }
}
function create(args: JsonObject) {
  if (IS_REMOTE && (args.type === 'serial' || args.type === 'tool' && !remoteTools.includes(args.tool))) throw new Error('Serial panels require a local workspace')
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
    const args = { title: draft.title, ...(panel.type === 'rtt' ? { channel: draft.channel } : panel.type === 'serial' ? { port: draft.port } : panel.type === 'tool' ? { tool: panel.source.tool } : !['watch', 'variables'].includes(panel.type) ? {} : { signals: draft.signals.split(',').map(value => value.trim()).filter(Boolean) }) }
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
  const scope = { type: 'string', enum: ['project', 'global'] }
  return [
    { name: 'panel.add', description: 'Add an independent view; does not connect or start acquisition', args: panelInputSchema, effect: 'view' },
    { name: 'panel.closed', description: 'List recently closed panel IDs, titles and types, newest first', args: objectSchema(), effect: 'view' },
    { name: 'panel.reopen', description: 'Restore a recently closed panel by stable ID from layout.closed', args: objectSchema(idProperty), effect: 'view' },
    { name: 'panel.remove', description: 'Close a view to Recently closed without stopping shared acquisition', args: objectSchema(idProperty), effect: 'view' },
    { name: 'panel.move', description: 'Move or resize a panel in the twelve-column grid', args: objectSchema({ ...idProperty, ...geometrySchema }), effect: 'view' },
    { name: 'panel.dock', description: 'Dock a panel as a tab beside the target panel without restarting its view', args: objectSchema({ ...idProperty, target_panel_id: { type: 'string', maxLength: 80 } }), effect: 'view' },
    { name: 'panel.undock', description: 'Detach a tab to an independent window', args: objectSchema(idProperty), effect: 'view' },
    { name: 'panel.split', description: 'Place panels side by side or adjust their shared divider in grid columns', args: objectSchema({ ...idProperty, target_panel_id: { type: 'string', maxLength: 80 }, columns: geometrySchema.w }, ['panel_id','target_panel_id']), effect: 'view' },
    { name: 'panel.enlarge', description: 'Enlarge a live view or return to the workbench; OS pinning requires a user click', args: objectSchema({ ...idProperty, open: {type:'boolean'} }), effect: 'view' },
    { name: 'panel.focus', description: 'Show a panel tab in its existing window', args: objectSchema(idProperty), effect: 'view' },
    { name: 'panel.editor', description: 'Open or close a panel settings editor', args: objectSchema({ ...idProperty, open: { type: 'boolean' } }), effect: 'view' },
    { name: 'component.transfer', description: 'Move a control to another controls panel, retaining its identity and binding', args: objectSchema({ component_id: { type: 'string', maxLength: 80 }, target_panel_id: { type: 'string', maxLength: 80 } }), effect: 'view' },
    { name: 'panel.configure', description: 'Set a panel title and source; empty signal list follows all selected signals', args: objectSchema({ ...idProperty, ...sourceProperties }, ['panel_id', 'title']), effect: 'view' },
    { name: 'layout.save', description: 'Save current layout for next opening. With name, save to project library (default) or global templates; search first and supply its revision to replace an existing name', args: objectSchema({ name: { type: 'string', maxLength: 80 }, revision: { type: 'integer', minimum: 0 }, scope }, []), effect: 'file' },
    { name: 'layout.search', description: 'Search project layouts (default) or global templates including built-ins; returns storage location, names, revisions, timestamps and panel counts', args: objectSchema({ query: { type: 'string', maxLength: 80 }, scope }, []), effect: 'view' },
    { name: 'layout.load', description: 'Load a named layout found with layout.search using the same scope, replacing unsaved views without device actions; save current layout afterwards to retain it on next opening', args: objectSchema({ name: { type: 'string', maxLength: 80 }, scope }, ['name']), effect: 'view' },
    { name: 'layout.restore', description: 'Replace unsaved views with saved layout; no device actions', args: objectSchema(), effect: 'view' },
  ]
}
async function execute(action: string, args: JsonObject, context?: SemanticExecutionContext) {
  const descriptor = catalog().find(item => item.name === action)
  if (!descriptor) throw new Error('Unknown workbench action')
  interaction.validateArgs(args, descriptor.args)
  if (args.name !== undefined && !args.name.trim()) throw new Error('Enter a nonempty layout name')
  if (action === 'panel.add') return create(args)
  if (action === 'panel.closed') return { panels: (layout.value.closed || []).map(({ id, title, type }) => ({ id, title, type })) }
  if (action === 'panel.reopen') return reopen(args.panel_id)
  if (action === 'panel.remove') { remove(args.panel_id); return { removed: args.panel_id } }
  if (action === 'panel.move') { const { panel_id, ...geometry } = args; return move(panel_id, geometry) }
  if (action === 'panel.dock') { dock(args.panel_id, args.target_panel_id); return read() }
  if (action === 'panel.undock') { undock(args.panel_id); return read() }
  if (action === 'panel.split') return change(draft => splitPanels(draft, args.panel_id, args.target_panel_id, args.columns))
  if (action === 'panel.enlarge') { find(args.panel_id); viewPanel(args.open ? args.panel_id : ''); return { enlarged: reading.value } }
  if (action === 'panel.focus') { jump(args.panel_id); return { active: args.panel_id } }
  if (action === 'panel.editor') { if (args.open) { focus(args.panel_id); if (editing.value !== args.panel_id) edit(find(args.panel_id)) } else editing.value = ''; return { editing: editing.value } }
  if (action === 'component.transfer') return transferControl(args.component_id, args.target_panel_id)
  if (action === 'panel.configure') { const { panel_id, ...values } = args; return configure(panel_id, values) }
  if (action === 'layout.save') {
    if ((args.revision !== undefined || args.scope !== undefined) && !args.name) throw new Error('A saved revision or scope requires a layout name')
    return args.name ? saveNamed(args.name, args.revision, args.scope, context) : save(context)
  }
  if (action === 'layout.search') return searchLayouts(args.query, args.scope, context)
  return load(action === 'layout.load' ? args.name : undefined, args.scope, context)
}
async function pollStatus() {
  try {
    const response = await fetch(`${API_BASE}/api/dash/rtt/status`)
    if (response.ok && !disposed) rtt.value = await response.json()
  } catch { /* Connection state stays with the existing RTT controls. */ }
  await refreshSnapshot()
  if (!disposed) { checkViews(); statusTimer = setTimeout(pollStatus, 1500) }
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
watch(() => props.active, active => { if (active === false && reading.value) viewPanel('') })
watch(() => props.deviceConnected, () => { snapshotRevision++; void refreshSnapshot() })
onMounted(() => { narrowWidth.addEventListener('change', widthChanged); document.addEventListener('keydown', leaveReading); void userLoad(); void pollStatus() })
onUnmounted(() => { narrowWidth.removeEventListener('change', widthChanged); clearTimeout(viewTimer); document.removeEventListener('keydown', leaveReading); disposed = true; clearTimeout(statusTimer) })
defineExpose({ catalog, read, execute, entries, load })
</script>

<style scoped>
.workbench { display:flex; flex-direction:column; min-height:0; flex:1; gap:8px; padding:12px; overflow:hidden; }
.workbench-toolbar,.workbench-actions { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.workbench-toolbar { justify-content:space-between; }.workbench-toolbar small { display:block; color:var(--muted); font-size:12px; margin-top:4px; }
.locate-update { flex:none; background:none; border:0; color:var(--accent); text-decoration:underline; cursor:pointer; }
.workbench-card-header,.float-heading { position:relative; isolation:isolate; }
.panel-heading-text { flex:1 1 4em; min-width:0; display:flex; align-items:baseline; overflow:hidden; gap:8px; }
.workbench-viewport { min-height:0; flex:1; overflow:auto; scrollbar-gutter:stable; }
.workbench-grid { min-height:350px; }
.workbench-locator { display:flex; align-items:center; gap:8px; min-width:0; max-width:100%; }
.workbench-locator strong,.help-button { flex:none; }
.help-button { box-sizing:border-box; height:32px; min-height:32px; padding-block:0; }
.workbench-locator select { min-width:0; max-width:min(220px,46vw); min-height:32px; color:var(--fg); background:var(--input-bg); border:1px solid var(--border); border-radius:4px; }
/* Remove surrounding navigation from layout and keyboard order while reading. */
:global(.app-root:has(.dash-workbench .workbench.is-reading) > .app-header),
:global(.app-root:has(.dash-workbench .workbench.is-reading) > .app-footer),
:global(.dash-workbench:has(.workbench.is-reading) .dashboard-nav-row) { display:none; }
:global(.app-main:has(.dash-workbench .workbench.is-reading)) { padding:0; }
:global(.dash-workbench:has(.workbench.is-reading)) { height:100%; min-height:0; }
:global(.dash-workbench:has(.workbench.is-reading) .card-full) { flex:1; min-height:0; padding:0; }
.workbench.is-reading .workbench-viewport { flex:1; height:auto; }
.workbench.is-reading .workbench-grid { display:block; height:100%!important; min-height:0; }
.workbench.is-reading .workbench-grid > article:not(.reading-card),.workbench.is-reading .workbench-grid > article > :deep(.ui-resizable-handle) { display:none!important; }
.workbench.is-reading .workbench-grid > .reading-card { position:relative!important; inset:auto!important; width:100%!important; height:100%!important; }
.workbench-card-header:focus-visible { outline:2px solid var(--accent); outline-offset:-2px; }
.workbench-card-header .dock-grip { cursor:grab; padding:2px; min-width:24px; }
.panel-drop-zones { position:absolute; z-index:16; inset:15% 6%; display:flex; align-items:center; justify-content:center; gap:4px; }
.panel-drop-zones button { flex:1; min-width:0; min-height:56px; border:2px dashed var(--accent); border-radius:4px; background:var(--surface); color:var(--fg); }
.panel-drop-zones button:hover { background:var(--accent); color:var(--bg); }
.float-placeholder { margin:auto; }
.float-heading { display:flex; flex:none; align-items:center; justify-content:space-between; gap:8px; padding:6px 12px; border-bottom:1px solid var(--border); }
:global(.workbench-float-host) { display:flex; flex-direction:column; height:100dvh; color:var(--fg); background:var(--surface); }

.workbench-card { display:flex; flex-direction:column; min-width:0; min-height:0; background:var(--surface); border:1px solid var(--border); border-radius:var(--radius,8px); overflow:hidden; }
.workbench-card-header { display:flex; flex-wrap:wrap; align-items:center; flex:none; gap:8px; padding:8px 12px; min-height:44px; background:var(--bg); border-bottom:1px solid var(--border); } .workbench:not(.is-reading) .workbench-card-header { cursor:grab; }.workbench:not(.is-reading) .workbench-card-header:active { cursor:grabbing; }
.workbench-header-actions { display:flex; align-items:center; flex-wrap:wrap; gap:8px; }
.panel-heading-text > strong { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:14px; }.workbench-card-header button { display:inline-flex; align-items:center; justify-content:center; gap:5px; min-height:28px; min-width:28px; padding:4px 7px; background:transparent; color:var(--fg); border:1px solid var(--border); border-radius:4px; cursor:pointer; }
.dock-tabs { display:flex; flex:none; gap:4px; padding:8px 12px; overflow:auto; border-bottom:1px solid var(--border); }.dock-tabs button { border:1px solid var(--border); border-radius:4px; padding:4px 8px; color:var(--fg); background:var(--surface); white-space:nowrap; cursor:pointer; }.dock-tabs button[aria-selected=true] { border-color:var(--accent); color:var(--accent); }
.panel-kind { color:var(--muted); font-size:12px; }.drag-handle { color:var(--muted); }
.workbench-card-content { position:relative; flex:1; min-height:0; overflow:auto; display:flex; flex-direction:column; }.workbench-card-content :deep(.symbol-panel) { width:100%; min-width:0; max-width:none; flex:1; }.workbench-card-content :deep(.waveform-viewer) { flex:1; min-height:240px; }.workbench-card-content :deep(.rtt-channel-panel) { flex:1; min-height:0; }
.panel-editor { padding:0; }.panel-editor label { display:flex; flex-direction:column; gap:8px; font-size:14px; margin-bottom:16px; }.panel-editor input { width:100%; min-width:0; box-sizing:border-box; }.geometry-fields { display:flex; gap:8px; }.geometry-fields label { flex:1; }.panel-editor button { margin-right:6px; }
.workbench-error { color:var(--danger,#e76b6b); margin:0; }.workbench-notice { font-size:12px; color:var(--muted); margin:0; }.workbench-empty { grid-column:1/-1; color:var(--muted); padding:36px; text-align:center; }
.workbench-actions > button { display:inline-flex; gap:6px; align-items:center; }
.workbench-card :is(button,input,select):focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
.workbench-grid :deep(.grid-stack-placeholder > .placeholder-content) { background:color-mix(in srgb,var(--accent) 12%,transparent); border:2px dashed var(--accent); border-radius:8px; }
.workbench-grid :deep(.ui-resizable-handle) { z-index:10; }
.workbench-grid > .grid-stack-item > :deep(.ui-resizable-s) { bottom:0; height:10px; cursor:ns-resize; }
.workbench-grid > .grid-stack-item > :deep(.ui-resizable-s::after) { content:''; display:block; width:32px; height:2px; margin:4px auto; background:var(--muted); border-radius:2px; opacity:.55; }
.workbench-grid :deep(.ui-resizable-se), .workbench-grid :deep(.ui-resizable-sw) { background-image:none; transform:none; width:18px; height:18px; }
.workbench-grid :deep(.ui-resizable-se::after), .workbench-grid :deep(.ui-resizable-sw::after) { content:''; position:absolute; inset:5px; border-bottom:1px solid var(--muted); opacity:0; }
.workbench-grid :deep(.ui-resizable-se::after) { border-right:1px solid var(--muted); }
.workbench-grid :deep(.ui-resizable-sw::after) { border-left:1px solid var(--muted); }
.workbench-grid :deep(.grid-stack-item:hover > .ui-resizable-handle::after), .workbench-grid :deep(.grid-stack-item:focus-within > .ui-resizable-handle::after) { opacity:.55; }
.dialog-actions,.closed-panels li { display:flex; align-items:center; gap:8px; }
.dialog-actions { justify-content:flex-end; }.closed-panels { list-style:none; padding:0; margin:0; }
.closed-panels li { justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--border); }
.closed-panels span { min-width:0; overflow-wrap:anywhere; }.closed-panels small { display:block; color:var(--muted); }.closed-panels button { flex:none; }
.narrow-help { display:none; }
@media(prefers-reduced-motion:reduce) { .workbench-grid :deep(.grid-stack-item) { transition:none!important; } }
@media(max-width:700px) { .layout-help { display:none; }.narrow-help { display:block; } .workbench-grid { display:flex; flex-direction:column; height:auto!important; flex-shrink:0; gap:8px; }.workbench-grid > .grid-stack-item { position:relative!important; inset:auto!important; width:100%!important; height:var(--drag-height,var(--panel-height))!important; flex-shrink:0; }.workbench-card { inset:0!important; }.workbench-grid :deep(.ui-resizable-handle) { display:none; } }
</style>
