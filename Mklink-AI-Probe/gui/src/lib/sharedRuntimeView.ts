import { API_BASE, IS_REMOTE, IS_TAURI } from './runtimeEndpoint'
import type { GuiCommand } from './guiAutomation'

/** A transport-owned presence survives background timer throttling. */
export function startSharedRuntimeView(present?: (tab: string) => Promise<void>,
  execute?: (command: GuiCommand) => Promise<Record<string, unknown>>): () => void {
  let socket: WebSocket | null = null
  let retry: ReturnType<typeof setTimeout> | undefined
  let stopped = false
  let suspended = false
  const resume = () => {
    if (stopped || suspended || socket !== null) return
    const url = new URL(IS_REMOTE ? `${API_BASE}/presence` : `${API_BASE}/api/runtime/control/view/${crypto.randomUUID()}`, window.location.href)
    if (!IS_REMOTE && present) url.searchParams.set('presentation', '1')
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    const current = new WebSocket(url.href)
    socket = current
    current.onopen = () => {
      if (execute && !IS_REMOTE && socket === current && !stopped) {
        current.send(JSON.stringify({ type: 'gui_hello', protocol: 2, kind: IS_TAURI ? 'desktop' : 'web' }))
      }
    }
    current.onmessage = async event => {
      if (socket !== current || stopped || suspended || IS_REMOTE || !present) return
      let message: any
      try { message = JSON.parse(event.data) } catch { return }
      if (message?.type === 'gui_request' && execute && typeof message.request_id === 'string' &&
          typeof message.expires_at === 'number' && message.expires_at * 1000 >= Date.now()) {
        let state: Record<string, unknown> = {}, error = '', ok = false
        try { state = await execute(message.command); ok = true }
        catch (e) { error = String(e).slice(0, 512) }
        if (socket === current && !stopped && !suspended && current.readyState === WebSocket.OPEN) {
          // Presence accepts bounded replies. Preserve action acknowledgement and
          // controls even when optional panel metadata is unusually large.
          if (JSON.stringify(state).length > 30_000) state = { ...state, panels: {}, panels_truncated: true }
          if (JSON.stringify(state).length > 30_000) state = { truncated: true, page: state.page, context: state.context }
          current.send(JSON.stringify({ type: 'gui_result', request_id: message.request_id, ok, state, error }))
        }
        return
      }
      if (!message || typeof message !== 'object' || message.type !== 'present' || typeof message.request_id !== 'string' ||
          !['superwatch', 'rtt', 'memory', 'symbols', 'hardfault', 'systemview'].includes(message.tab) ||
          typeof message.expires_at !== 'number' || message.expires_at * 1000 < Date.now()) return
      let ok = false
      try { await present(message.tab); ok = true } catch { /* Report failure without replay. */ }
      if (socket === current && !stopped && !suspended && current.readyState === WebSocket.OPEN) {
        current.send(JSON.stringify({ type: 'present_result', request_id: message.request_id, ok }))
      }
    }
    current.onclose = () => {
      if (socket !== current) return
      socket = null
      // Only presence is retried. Remote sessions require explicit reconnection.
      if (!stopped && !suspended && !IS_REMOTE) retry = setTimeout(resume, 1000)
    }
  }
  const suspend = () => {
    clearTimeout(retry)
    const current = socket
    socket = null
    current?.close()
  }
  const stop = () => {
    if (stopped) return
    stopped = true
    window.removeEventListener('pagehide', hide)
    window.removeEventListener('pageshow', show)
    suspend()
  }
  const hide = (event: PageTransitionEvent) => {
    if (event.persisted) { suspended = true; suspend() } else stop()
  }
  const show = (event: PageTransitionEvent) => {
    if (event.persisted) { suspended = false; resume() }
  }
  window.addEventListener('pagehide', hide)
  window.addEventListener('pageshow', show)
  resume()
  return stop
}
