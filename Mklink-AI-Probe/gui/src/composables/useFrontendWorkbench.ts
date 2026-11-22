import { ref, onMounted, onUnmounted, nextTick, provide, type Ref } from 'vue'
import { connectFrontend, frontendRequest, objectSchema, interaction, withFrontendTarget, type SemanticExecutionContext, type FrontendFeedback, type FrontendRuntime, type FrontendTarget, type SemanticSurface, type JsonObject } from '../lib/frontendControl'
import { bindingHostKey } from '../lib/workbenchBindings'
import { applyConnectionClock, readConnectionClock } from '../lib/connectionClock'
import { IS_REMOTE } from '../lib/runtimeEndpoint'
import { useGuiPanel } from '../lib/guiAutomation'
import { tr } from './useLanguage'
import { createWorkbenchActivity, workbenchActivityKey } from '../lib/workbenchActivity'

interface PanelEntry { id: string; title: string; type: string; source?: unknown; surface?: SemanticSurface | null }
export interface WorkbenchFeedback {
  id: string
  target: string
  title: string
  detail: string
  rejected: boolean
}
interface WorkbenchSurface extends SemanticSurface { entries(): PanelEntry[] }

export async function recoverPendingIntent(pending: JsonObject, request = frontendRequest): Promise<JsonObject> {
  try {
    return await request(`intent?request_id=${encodeURIComponent(pending.request_id)}`)
  } catch (cause) {
    if ((cause as { status?: number }).status !== 404) throw cause
  }
  const discovery = await request('pages')
  if (discovery.session_id !== pending.session_id || !discovery.pages.some((page: JsonObject) => page.page_id === pending.page_id && page.online)) {
    throw Object.assign(new Error('The original request was not found and its target or page has ended. You may explicitly discard this pending request.'), { pending, canDiscard: true })
  }
  try {
    // An explicit retry preserves the original identity, target and message.
    return await request('intent', pending)
  } catch (cause) {
    const status = (cause as { status?: number }).status
    throw Object.assign(cause as Error, { pending, canDiscard: status === 404 || status === 409 || status === 422 })
  }
}

export function useFrontendWorkbench(tab: Ref<string>, superwatch: Ref<SemanticSurface | null>, workbench: Ref<WorkbenchSurface | null>) {
  let storage: Storage | undefined
  try { storage = window.sessionStorage } catch { /* History remains in memory if browser storage is unavailable. */ }
  const activity = createWorkbenchActivity(storage)
  provide(workbenchActivityKey, activity)
  let conversationTimer: ReturnType<typeof setTimeout> | undefined, conversationDisposed = false
  const connected = ref(false), error = ref(''), busy = ref(false)
  const runtime = ref<FrontendRuntime | null>(null), target = ref<FrontendTarget | null>(null)
  const sessionEpoch = ref(0)
  useGuiPanel('workbench', {
    snapshot: () => {
      const report = runtime.value?.report()
      return { connected: connected.value, protocol: report?.protocol, session_id: report?.session_id,
        page_id: report?.page_id, target: target.value }
    },
    actions: {},
  })
  let stop: (() => void) | undefined
  const navigation: SemanticSurface = {
    catalog: () => [
      { name: 'navigate', description: 'Show the SuperWatch page or the composable workbench', args: objectSchema({ tab: { type: 'string', enum: IS_REMOTE ? ['superwatch', 'workbench', 'rtt'] : ['superwatch', 'workbench', 'rtt', 'serial'] } }), effect: 'view' },
      { name: 'device.clock.read', description: 'Read the shared debug connection clock and supported frequencies', args: objectSchema(), effect: 'view' },
      { name: 'device.clock.set', description: 'Apply or save the shared connection clock using the original device guards', args: objectSchema({ interface: { type: 'string', enum: ['SWD', 'JTAG'] }, clock_hz: { type: 'integer', minimum: 1, maximum: 1000000000 } }), effect: 'device' },
    ],
    read: () => ({ tab: tab.value }),
    execute: async (action, args) => {
      if (action === 'device.clock.read') return readConnectionClock()
      if (action === 'device.clock.set') {
        const status = await readConnectionClock()
        return applyConnectionClock(status, args.interface, args.clock_hz, status.connected && (status.active_interface ?? status.interface) === args.interface)
      }
      tab.value = args.tab; await nextTick(); return { displayed: tab.value }
    },
  }
  function entries(): PanelEntry[] {
    return [
      { id: 'dashboard', title: 'MKLink Dashboard', type: 'navigation', surface: navigation },
      { id: 'superwatch', title: 'SuperWatch', type: 'superwatch', surface: superwatch.value },
      { id: 'workbench', title: tr('灵活面板', 'Flexible Panels'), type: 'layout', surface: workbench.value },
      ...(workbench.value?.entries() || []),
    ].filter(entry => entry.surface && typeof entry.surface.catalog === 'function')
  }
  function actions() {
    const mapped: Record<string, { panel: PanelEntry; name: string; descriptor: JsonObject }> = {}
    for (const panel of entries()) for (const action of panel.surface?.catalog() || []) {
      const key = `${panel.id}\u0000${action.name}`
      let hash = 2166136261
      for (let i = 0; i < key.length; i++) hash = Math.imul(hash ^ key.charCodeAt(i), 16777619)
      const id = `action_${(hash >>> 0).toString(16)}`
      if (id.length > 80 || !/^[a-zA-Z0-9_-]+$/.test(id) || mapped[id]) throw new Error(`Invalid or duplicate semantic action: ${id}`)
      mapped[id] = { panel, name: action.name, descriptor: { description: action.description, inputSchema: action.args, effect: action.effect || 'view', panel_id: panel.id, name: action.name } }
    }
    return mapped
  }
  const feedback = ref<WorkbenchFeedback | null>(null)
  let feedbackTimer: ReturnType<typeof setTimeout> | undefined
  function clearFeedback() {
    clearTimeout(feedbackTimer)
    feedback.value = null
  }
  function presentFeedback(event: FrontendFeedback) {
    const rejected = event.status === 'rejected'
    if (!rejected && event.status !== 'completed' && event.status !== 'applied') return
    const entry = actions()[event.action]
    if (!rejected && entry?.name !== 'content.set') return

    const panel = entry?.panel.id === 'workbench' && typeof event.target_panel === 'string'
      ? entries().find(item => item.id === event.target_panel) || entry.panel
      : entry?.panel
    const target = panel?.id || ''
    const label = panel?.title || tr('当前页面', 'this page')
    const id = 'agent:' + event.status + ':' + event.command_id
    if (activity.state.entries.some(item => item.id === id)) return
    let title: string
    let detail = ''
    if (rejected) {
      const declinedActions: Record<string, string> = {
        'panel.enlarge': event.open === false ? tr('已拒绝退出专注', 'Leaving focused view was declined') : tr('已拒绝进入专注', 'Entering focused view was declined'),
        'panel.split': tr('已拒绝调整分栏', 'Split adjustment declined'),
        'panel.remove': tr('已拒绝关闭面板', 'Closing the panel was declined'),
        'layout.save': tr('已拒绝保存布局', 'Saving the layout was declined'),
        'content.set': panel?.type === 'chart' ? tr('已拒绝更新图表', 'Chart update declined') : tr('已拒绝更新内容', 'Content update declined'),
      }
      title = declinedActions[entry?.name || ''] || tr('已拒绝 Agent 操作', 'Agent action declined')
      const reasons: Record<string, string> = {
        STALE_REVISION: entry?.panel.id === 'workbench' ? tr('布局已变化', 'The layout has changed') : tr('页面状态已变化', 'The page state has changed'),
        EXPIRED: tr('请求已过期', 'The request expired'),
        BUSY: tr('上一项操作尚未结束', 'A previous operation is still pending'),
        INVALID_INPUT: tr('参数与当前操作不匹配', 'The parameters do not match this action'),
        UNKNOWN_ACTION: tr('此操作已不可用', 'This action is no longer available'),
        SESSION_LIMIT: tr('当前会话的操作记录已满', 'The session history is full'),
      }
      const reason = reasons[event.code || ''] || tr('当前请求未通过校验', 'The request did not pass validation')
      detail = tr('「' + label + '」 · ' + reason + '，本次操作未执行。', '“' + label + '” · ' + reason + '. The action was not performed.')
    } else {
      title = panel?.type === 'chart' ? tr('Agent 已更新「' + label + '」的图表', 'Agent updated the chart in “' + label + '”')
        : tr('Agent 已更新「' + label + '」的内容', 'Agent updated the content in “' + label + '”')
    }
    activity.append({ id, kind: rejected ? 'error' : 'operation', source: 'Agent', title: title.slice(0, 200), text: detail, status: event.status })
    clearFeedback()
    feedback.value = { id, target, title, detail, rejected }
    feedbackTimer = setTimeout(clearFeedback, rejected ? 8000 : 4500)
  }
  function resolveAction(panelId: string, name: string, args: JsonObject) {
    const panel = entries().find(panel => panel.id === panelId)
    const action = panel?.surface?.catalog().find(action => action.name === name)
    if (!panel?.surface || !action) throw new Error('Bound capability is unavailable; rebind this control')
    interaction.validateArgs(args, action.args)
    panel.surface.validate?.(name, args)
    return panel.surface
  }
  async function runSurface(panelId: string, name: string, args: JsonObject, context?: SemanticExecutionContext, agent = false) {
    const surface = resolveAction(panelId, name, args)
    const source = entries().find(entry => entry.id === panelId)?.title || panelId
    const title = (surface.catalog().find(action => action.name === name)?.description || name).slice(0, 200)
    const quiet = ['view.controls', 'view.read', 'log.read'].includes(name)
    try {
      const result = await surface.execute(name, args, context) as JsonObject | undefined
      if (!quiet && !(agent && name === 'content.set')) activity.append({ kind: 'operation', source, title: (typeof result?.operation === 'string' ? result.operation : title).slice(0, 200), text: '', status: typeof result?.status === 'string' ? result.status.slice(0, 100) : result?.job_id || result?.runtime_job_id ? 'submitted' : 'completed' })
      return result
    } catch (cause) {
      activity.append({ kind: 'error', source, title, text: String(cause).slice(0, 4000), status: (cause as { unknown?: boolean }).unknown ? 'unknown' : 'failed' })
      throw cause
    }
  }
  provide(bindingHostKey, {
    targets: () => entries().map(entry => ({ ...entry, surface: entry.surface! })),
    invoke: async (panelId, name, args, context) => {
      resolveAction(panelId, name, args)
      if (!connected.value || !runtime.value || !target.value) throw new Error('Frontend control is not connected')
      if (!context?.frontendGuarded && busy.value) throw new Error('An operation is already running')
      if (!context?.frontendGuarded) busy.value = true
      try { return await withFrontendTarget(runtime.value.report().session_id, target.value, operation => runSurface(panelId, name, args, operation), context) }
      finally { if (!context?.frontendGuarded) busy.value = false }
    },
  })
  const adapter = {
    title: 'MKLink Web Workbench',
    catalog: () => ({ panels: entries().map(({ surface, ...panel }) => ({ ...panel, actions: Object.entries(actions()).filter(([, entry]) => entry.panel.id === panel.id).map(([id, entry]) => ({ id, name: entry.name })) })), intents: ['explain', 'inspect', 'plan'] }),
    get actions() { return Object.fromEntries(Object.entries(actions()).map(([id, entry]) => [id, entry.descriptor])) },
    read: () => ({ tab: tab.value, panels: entries().map(panel => ({ id: panel.id, state: panel.surface!.read() })) }),
    execute: async (id: string, args: JsonObject, context?: SemanticExecutionContext) => {
      const entry = actions()[id]
      if (!entry) throw new Error('Panel or action no longer exists')
      return runSurface(entry.panel.id, entry.name, args, context, true)
    },
  }
  onMounted(() => {
    stop = connectFrontend({ adapter,
      ready: (value, binding) => { runtime.value = value; target.value = binding; connected.value = true; activity.bind(`${value.report().session_id}:${binding.probe_id}:${binding.device_generation}`) },
      feedback: presentFeedback,
      reset: () => { clearFeedback(); runtime.value = null; target.value = null; connected.value = false; sessionEpoch.value++; activity.bind('') },
      error: message => { error.value = message; connected.value = !message && runtime.value !== null },
      busy: value => { busy.value = value },
    })
    void pollConversations()
  })
  onUnmounted(() => { clearFeedback(); conversationDisposed = true; clearTimeout(conversationTimer); stop?.() })
  function recordReply(result: JsonObject) {
    if (result.status === 'replied' && typeof result.reply === 'string') activity.append({ id: 'reply:' + result.request_id, kind: 'answer', source: 'Agent', title: tr('Agent 答复', 'Agent reply'), text: result.reply.slice(0, 16000), status: 'replied', requestId: result.request_id })
  }
  let conversationCursor = 0
  async function pollConversations() {
    if (connected.value) {
      const answered = new Set(activity.state.entries.filter(entry => entry.kind === 'answer').map(entry => entry.requestId))
      const pending = activity.state.entries.filter(entry => entry.kind === 'question' && entry.requestId && !answered.has(entry.requestId))
      if (conversationCursor >= pending.length) conversationCursor = 0
      const batch = pending.slice(conversationCursor, conversationCursor + 5)
      conversationCursor += batch.length
      for (const entry of batch) {
        const epoch = sessionEpoch.value
        try { const result = await frontendRequest(`intent?request_id=${encodeURIComponent(entry.requestId!)}`); if (!conversationDisposed && epoch === sessionEpoch.value) recordReply(result) }
        catch { /* Preserve the question and original request identity during disconnection. */ }
      }
    }
    if (!conversationDisposed) conversationTimer = setTimeout(pollConversations, 1500)
  }
  function recordQuestion(result: JsonObject, payload: JsonObject) {
    activity.append({ id: 'question:' + result.request_id, kind: 'question', source: tr('用户', 'User'), title: (tr('提问 · ', 'Question · ') + (entries().find(entry => entry.id === payload.object_id)?.title || payload.object_id)).slice(0, 200), text: String(payload.message).slice(0, 4000), status: 'waiting', requestId: result.request_id })
    recordReply(result)
    return result
  }
  async function submitIntent(requestId: string, objectId: string, intent: string, message: string, pending?: JsonObject) {
    if (pending) return recordQuestion(await recoverPendingIntent(pending), pending)
    if (!runtime.value || !connected.value) throw new Error('Frontend control is not connected')
    const report = runtime.value.report()
    const exchange = await frontendRequest('exchange', { report, receipts: [] })
    if (exchange.command) {
      runtime.value.execute(exchange.command)
      throw new Error('An Agent action is pending. Wait for its result before sending this request.')
    }
    const payload = { request_id: requestId, session_id: report.session_id, page_id: report.page_id, revision: report.state.revision, object_id: objectId, intent, message }
    try { return recordQuestion(await frontendRequest('intent', payload), payload) }
    catch (cause) {
      const status = (cause as { status?: number }).status
      throw Object.assign(cause as Error, { pending: !status || status >= 500 ? payload : undefined })
    }
  }
  return { connected, error, busy, feedback, sessionEpoch, runtime, target, entries, submitIntent }
}
