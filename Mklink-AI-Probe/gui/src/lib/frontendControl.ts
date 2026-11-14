import '../assets/agent_interaction.js'
import { API_BASE } from './runtimeEndpoint'

export type JsonObject = Record<string, any>
export interface SemanticAction { name: string; description: string; args: JsonObject; effect?: string }
export interface SemanticSurface {
  catalog(): SemanticAction[]
  read(): JsonObject
  execute(action: string, args: JsonObject): unknown | Promise<unknown>
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
interface InteractionApi {
  create(options: { session_id: string; page_id: string; adapter: JsonObject }): FrontendRuntime
  validateArgs(args: unknown, schema: JsonObject): void
}
export const interaction = (globalThis as unknown as { AgentInteraction: InteractionApi }).AgentInteraction
export const objectSchema = (properties: JsonObject = {}, required = Object.keys(properties)) => ({ type: 'object', properties, required, additionalProperties: false })

export async function frontendRequest(path: string, body?: unknown, method = body === undefined ? 'GET' : 'POST'): Promise<any> {
  const response = await fetch(`${API_BASE}/api/runtime/frontend/${path}`, {
    method, signal: AbortSignal.timeout(5000), ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  })
  const payload = await response.json()
  if (!response.ok) throw Object.assign(new Error(typeof payload.detail === 'string' ? payload.detail : payload.detail?.message || response.statusText), { status: response.status, code: payload.detail?.code })
  return payload
}

let activeTarget: { session: string; target: FrontendTarget; uncertain?: string } | null = null
let guardInstalled = false
function installTargetGuard() {
  if (guardInstalled) return
  guardInstalled = true
  const original = window.fetch.bind(window)
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(input instanceof Request ? input.url : String(input), location.href)
    const base = new URL(API_BASE || '.', location.href)
    if (!activeTarget || url.origin !== base.origin || !url.pathname.startsWith(`${base.pathname.replace(/\/$/, '')}/api/`)) return original(input, init)
    const context = activeTarget
    const headers = new Headers(init?.headers || (input instanceof Request ? input.headers : undefined))
    headers.set('X-MKLink-Frontend-Session', context.session)
    headers.set('X-MKLink-Probe', context.target.probe_id)
    headers.set('X-MKLink-Device-Generation', String(context.target.device_generation))
    const method = init?.method || (input instanceof Request ? input.method : 'GET')
    const mutation = !['GET', 'HEAD', 'OPTIONS'].includes(method.toUpperCase()) && !url.pathname.includes('/api/runtime/frontend/')
    try {
      const response = await original(input, { ...init, headers })
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
}

export async function withFrontendTarget<T>(session: string, target: FrontendTarget, execute: () => T | Promise<T>): Promise<T> {
  if (activeTarget) throw new Error('A frontend operation is still running')
  installTargetGuard()
  activeTarget = { session, target }
  const context = activeTarget
  try {
    const result = await execute()
    if (context.uncertain) throw new Error(context.uncertain)
    return result
  } catch (error) {
    if (context.uncertain) throw Object.assign(new Error(context.uncertain), { unknown: true, cause: error })
    throw error
  } finally { activeTarget = null }
}

export function connectFrontend(options: {
  adapter: JsonObject
  ready(runtime: FrontendRuntime, target: FrontendTarget): void
  reset(): void
  error(message: string): void
  busy(value: boolean): void
}) {
  let runtime: FrontendRuntime | null = null
  let target: FrontendTarget | null = null
  let timer: ReturnType<typeof setTimeout> | undefined
  let stopped = false
  const sent = new Map<string, string>()
  let iteration = 0
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
          runtime = interaction.create({ session_id: session, page_id: crypto.randomUUID(), adapter: {
            ...options.adapter,
            get actions() { return options.adapter.actions },
            execute: async (action: string, args: JsonObject) => {
              options.busy(true)
              try { return await withFrontendTarget(session, target!, () => options.adapter.execute(action, args)) }
              finally { options.busy(false) }
            },
          } })
          options.ready(runtime, target!)
        }
      }
      const current = runtime!
      const receipts = current.receipts().filter(receipt => sent.get(receipt.command_id) !== JSON.stringify(receipt))
      const exchange = await frontendRequest('exchange', { report: current.report(), receipts })
      if (stopped || current !== runtime) return
      for (const receipt of receipts) sent.set(receipt.command_id, JSON.stringify(receipt))
      if (exchange.command) current.execute(exchange.command)
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
