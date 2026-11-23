import '../assets/agent_interaction.js'
import { API_BASE } from './runtimeEndpoint'

export type JsonObject = Record<string, any>
export interface SemanticAction { name: string; description: string; args: JsonObject; effect?: string }
export interface SemanticExecutionContext { frontendGuarded: true; fetch: typeof fetch }
export interface SemanticSurface {
  catalog(): SemanticAction[]
  read(): JsonObject
  readValues?(): Record<string, import('./numericValue').NumericSample>
  execute(action: string, args: JsonObject, context?: SemanticExecutionContext): unknown | Promise<unknown>
  validate?(action: string, args: JsonObject): void
  restore?(view: JsonObject): unknown | Promise<unknown>
}
export interface FrontendTarget { instance_id: string; probe_id: string; device_generation: number; project_root: string }
export interface FrontendReport { protocol: string; session_id: string; page_id: string; title: string; catalog: unknown; actions: JsonObject; state: { revision: number; value: unknown } }
export interface FrontendRuntime {
  report(): FrontendReport
  execute(command: JsonObject): JsonObject
  receipts(): JsonObject[]
  invalidate(): void
  dispose(): void
}
export interface FrontendFeedback {
  command_id: string
  action: string
  status: string
  code?: string
  target_panel?: string
  open?: boolean
}
interface InteractionApi {
  create(options: { session_id: string; page_id: string; adapter: JsonObject; onReceipt?: (event: FrontendFeedback) => void }): FrontendRuntime
  validateArgs(args: unknown, schema: JsonObject): void
}
export const interaction = (globalThis as unknown as { AgentInteraction: InteractionApi }).AgentInteraction
export const objectSchema = (properties: JsonObject = {}, required = Object.keys(properties)) => ({ type: 'object', properties, required, additionalProperties: false })

export async function frontendRequest(path: string, body?: unknown, method = body === undefined ? 'GET' : 'POST', context?: SemanticExecutionContext): Promise<any> {
  const response = await (context?.fetch || fetch)(`${API_BASE}/api/runtime/frontend/${path}`, {
    method, signal: AbortSignal.timeout(5000), ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  })
  const payload = await response.json()
  if (!response.ok) throw Object.assign(new Error(typeof payload.detail === 'string' ? payload.detail : payload.detail?.message || response.statusText), { status: response.status, code: payload.detail?.code })
  return payload
}

type Operation = SemanticExecutionContext & { session: string; target: FrontendTarget; uncertain?: string; pending: Set<Promise<Response>> }
let activeTarget: Operation | null = null
let dispatchContext: SemanticExecutionContext | undefined

// Only the synchronous dispatch stack inherits a request owner. Async workflows
// pass their context explicitly; timers, saves and polling never inherit it.
export function dispatchFrontend<T>(context: SemanticExecutionContext | undefined, execute: () => T): T {
  const previous = dispatchContext
  dispatchContext = context
  try { return execute() } finally { dispatchContext = previous }
}
export const frontendFetch: typeof fetch = (...args) => (dispatchContext?.fetch || fetch)(...args)

export async function withFrontendTarget<T>(session: string, target: FrontendTarget, execute: (context: SemanticExecutionContext) => T | Promise<T>, inherited?: SemanticExecutionContext): Promise<T> {
  if (inherited) {
    if (inherited !== activeTarget || activeTarget.session !== session || Object.keys(target).some(key => activeTarget!.target[key as keyof FrontendTarget] !== target[key as keyof FrontendTarget])) throw new Error('The original frontend operation target is no longer active')
  } else if (activeTarget) throw new Error('A frontend operation is still running')
  const context: Operation = inherited as Operation || { frontendGuarded: true, session, target: { ...target }, pending: new Set(), fetch: (input, init) => {
    const pending = request(input, init)
    context.pending.add(pending)
    void pending.finally(() => context.pending.delete(pending)).catch(() => {})
    return pending
  } }
  async function request(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
    if (activeTarget !== context) throw new Error('The original frontend operation target is no longer active')
    if (context.uncertain) throw Object.assign(new Error(context.uncertain), { unknown: true })
    const url = new URL(input instanceof Request ? input.url : String(input), location.href)
    const base = new URL(API_BASE || '.', location.href)
    if (url.origin !== base.origin || !url.pathname.startsWith(`${base.pathname.replace(/\/$/, '')}/api/`)) throw new Error('Operation requests must use the runtime API')
    const headers = new Headers(init?.headers || (input instanceof Request ? input.headers : undefined))
    headers.set('X-MKLink-Frontend-Session', session)
    headers.set('X-MKLink-Probe', context.target.probe_id)
    headers.set('X-MKLink-Device-Generation', String(context.target.device_generation))
    const method = init?.method || (input instanceof Request ? input.method : 'GET')
    const mutation = !['GET', 'HEAD', 'OPTIONS'].includes(method.toUpperCase())
    try {
      const response = await fetch(input, { ...init, headers })
      if (mutation && response.status >= 500) context.uncertain = `HTTP ${response.status}; check the original operation before retrying`
      if (mutation && response.headers.get('Content-Type')?.includes('json')) {
        try { await response.clone().json() } catch { context.uncertain = 'The operation response could not be read; check the original operation before retrying' }
      }
      return response
    } catch (error) {
      if (mutation) context.uncertain = 'The operation response was lost; check the original operation before retrying'
      throw error
    }
  }
  if (!inherited) activeTarget = context
  try {
    if (context.uncertain) throw new Error(context.uncertain)
    const result = await dispatchFrontend(context, () => execute(context))
    while (context.pending.size) await Promise.allSettled([...context.pending])
    if (context.uncertain) throw new Error(context.uncertain)
    return result
  } catch (error) {
    while (context.pending.size) await Promise.allSettled([...context.pending])
    if (context.uncertain) throw Object.assign(new Error(context.uncertain), { unknown: true, cause: error })
    throw error
  } finally { if (!inherited) activeTarget = null }
}

export function connectFrontend(options: {
  adapter: JsonObject
  ready(runtime: FrontendRuntime, target: FrontendTarget): void
  reset(): void
  error(message: string): void
  busy(value: boolean): void
  feedback?(event: FrontendFeedback): void
}) {
  let runtime: FrontendRuntime | null = null
  let target: FrontendTarget | null = null
  let timer: ReturnType<typeof setTimeout> | undefined
  let stopped = false
  const sent = new Map<string, string>()
  let iteration = 0
  let feedbackAck = 0
  async function tick() {
    try {
      // Re-discover periodically even while idle, including backend restarts/project switches.
      if (!runtime || iteration++ % 4 === 0) {
        const discovery = await frontendRequest('pages')
        if (stopped) return
        if (discovery.protocol !== 'agent-frontend/1') throw new Error('Unsupported frontend protocol')
        if (runtime && runtime.report().session_id !== discovery.session_id) {
          runtime.dispose(); runtime = null; sent.clear(); options.reset()
        }
        if (!runtime) {
          target = discovery.target
          const session = discovery.session_id
          feedbackAck = 0
          runtime = interaction.create({ session_id: session, page_id: crypto.randomUUID(), onReceipt: options.feedback, adapter: {
            ...options.adapter,
            get actions() { return options.adapter.actions },
            execute: async (action: string, args: JsonObject) => {
              options.busy(true)
              try { return await withFrontendTarget(session, target!, context => options.adapter.execute(action, args, context)) }
              finally { options.busy(false) }
            },
          } })
          options.ready(runtime, target!)
        }
      }
      const current = runtime!
      const receipts = current.receipts().filter(receipt => sent.get(receipt.command_id) !== JSON.stringify(receipt))
      const exchange = await frontendRequest('exchange', { report: current.report(), receipts, ...(feedbackAck ? { feedback_ack: feedbackAck } : {}) })
      if (stopped || current !== runtime) return
      for (const receipt of receipts) sent.set(receipt.command_id, JSON.stringify(receipt))
      if (exchange.command) current.execute(exchange.command)
      // Process the command against the reported revision before appending UI history.
      for (const event of exchange.feedback || []) {
        if (event.seq > feedbackAck) {
          options.feedback?.(event)
          feedbackAck = event.seq
        }
      }
      options.error('')
    } catch (error) {
      options.error(String(error))
      if ((error as { code?: string }).code === 'WRONG_TARGET') {
        runtime?.dispose(); runtime = null; sent.clear(); options.reset()
      }
    } finally { if (!stopped) timer = setTimeout(tick, 500) }
  }
  const invalidate = (event: Event) => { if (event.isTrusted) runtime?.invalidate() }
  for (const event of ['click', 'input', 'change', 'keydown', 'wheel']) document.addEventListener(event, invalidate, true)
  void tick()
  return () => {
    stopped = true; clearTimeout(timer); runtime?.dispose()
    for (const event of ['click', 'input', 'change', 'keydown', 'wheel']) document.removeEventListener(event, invalidate, true)
  }
}
