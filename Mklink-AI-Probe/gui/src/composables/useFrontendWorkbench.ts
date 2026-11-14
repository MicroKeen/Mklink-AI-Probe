import { ref, onMounted, onUnmounted, nextTick, provide, type Ref } from 'vue'
import { connectFrontend, frontendRequest, objectSchema, interaction, withFrontendTarget, type FrontendRuntime, type FrontendTarget, type SemanticSurface, type JsonObject } from '../lib/frontendControl'
import { bindingHostKey } from '../lib/workbenchBindings'
import { applyConnectionClock, readConnectionClock } from '../lib/connectionClock'
import { IS_REMOTE } from '../lib/runtimeEndpoint'

interface PanelEntry { id: string; title: string; type: string; source?: unknown; surface?: SemanticSurface | null }
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
  const connected = ref(false), error = ref(''), busy = ref(false)
  const runtime = ref<FrontendRuntime | null>(null), target = ref<FrontendTarget | null>(null)
  const sessionEpoch = ref(0)
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
      { id: 'workbench', title: 'Workbench', type: 'layout', surface: workbench.value },
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
  function resolveAction(panelId: string, name: string, args: JsonObject) {
    const panel = entries().find(panel => panel.id === panelId)
    const action = panel?.surface?.catalog().find(action => action.name === name)
    if (!panel?.surface || !action) throw new Error('Bound capability is unavailable; rebind this control')
    interaction.validateArgs(args, action.args)
    panel.surface.validate?.(name, args)
    return panel.surface
  }
  provide(bindingHostKey, {
    targets: () => entries().map(entry => ({ ...entry, surface: entry.surface! })),
    invoke: async (panelId, name, args, context) => {
      const surface = resolveAction(panelId, name, args)
      if (!connected.value || !runtime.value || !target.value) throw new Error('Frontend control is not connected')
      if (!context?.frontendGuarded && busy.value) throw new Error('An operation is already running')
      if (!context?.frontendGuarded) busy.value = true
      try { return await withFrontendTarget(runtime.value.report().session_id, target.value, () => surface.execute(name, args), context?.frontendGuarded) }
      finally { if (!context?.frontendGuarded) busy.value = false }
    },
  })
  const adapter = {
    title: 'MKLink Web Workbench',
    catalog: () => ({ panels: entries().map(({ surface, ...panel }) => ({ ...panel, actions: Object.entries(actions()).filter(([, entry]) => entry.panel.id === panel.id).map(([id, entry]) => ({ id, name: entry.name })) })), intents: ['explain', 'inspect', 'plan'] }),
    get actions() { return Object.fromEntries(Object.entries(actions()).map(([id, entry]) => [id, entry.descriptor])) },
    read: () => ({ tab: tab.value, panels: entries().map(panel => ({ id: panel.id, state: panel.surface!.read() })) }),
    execute: async (id: string, args: JsonObject) => {
      const entry = actions()[id]
      if (!entry) throw new Error('Panel or action no longer exists')
      return entry.panel.surface!.execute(entry.name, args, { frontendGuarded: true })
    },
  }
  onMounted(() => {
    stop = connectFrontend({ adapter,
      ready: (value, binding) => { runtime.value = value; target.value = binding; connected.value = true },
      reset: () => { runtime.value = null; target.value = null; connected.value = false; sessionEpoch.value++ },
      error: message => { error.value = message; connected.value = !message && runtime.value !== null },
      busy: value => { busy.value = value },
    })
  })
  onUnmounted(() => stop?.())
  async function submitIntent(requestId: string, objectId: string, intent: string, message: string, pending?: JsonObject) {
    if (pending) return recoverPendingIntent(pending)
    if (!runtime.value || !connected.value) throw new Error('Frontend control is not connected')
    const report = runtime.value.report()
    const exchange = await frontendRequest('exchange', { report, receipts: [] })
    if (exchange.command) {
      runtime.value.execute(exchange.command)
      throw new Error('An Agent action is pending. Wait for its result before sending this request.')
    }
    const payload = { request_id: requestId, session_id: report.session_id, page_id: report.page_id, revision: report.state.revision, object_id: objectId, intent, message }
    try { return await frontendRequest('intent', payload) }
    catch (cause) {
      const status = (cause as { status?: number }).status
      throw Object.assign(cause as Error, { pending: !status || status >= 500 ? payload : undefined })
    }
  }
  return { connected, error, busy, sessionEpoch, runtime, target, entries, submitIntent }
}
