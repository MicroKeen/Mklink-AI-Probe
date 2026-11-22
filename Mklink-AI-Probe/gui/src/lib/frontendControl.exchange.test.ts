import { flushPromises } from '@vue/test-utils'
import { afterEach, expect, it, vi } from 'vitest'
import { connectFrontend, frontendRequest, type FrontendRuntime } from './frontendControl'

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })

it('retains the original page when an intent exchange overtakes a periodic report', async () => {
  vi.useFakeTimers()
  let current!: FrontendRuntime
  let releaseOlder!: () => void
  let publishedRevision = -1
  let first = true
  const reset = vi.fn()
  const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
  const exchange = (body: any) => {
    if (body.report.state.revision < publishedRevision) return response({ detail: { code: 'STALE_REVISION', message: 'Page revision went backwards' } }, 409)
    publishedRevision = body.report.state.revision
    return response({ command: null })
  }
  vi.stubGlobal('fetch', vi.fn(async (input: string, init?: RequestInit) => {
    if (input.endsWith('/pages')) return response({ protocol: 'agent-frontend/1', session_id: 'session', pages: [],
      target: { instance_id: 'instance', probe_id: 'probe', device_generation: 1, project_root: 'project' } })
    const body = JSON.parse(String(init?.body))
    if (first) {
      first = false
      return new Promise<Response>(resolve => { releaseOlder = () => resolve(exchange(body)) })
    }
    return exchange(body)
  }))
  const stop = connectFrontend({
    adapter: { title: 'Test', catalog: () => ({}), actions: {}, read: () => ({ selected: 'one' }), execute: vi.fn() },
    ready: runtime => { current = runtime }, reset, error: vi.fn(), busy: vi.fn(),
  })
  try {
    await flushPromises()
    const pageId = current.report().page_id
    current.invalidate()
    // submitIntent publishes this newer report before its durable request.
    await frontendRequest('exchange', { report: current.report(), receipts: [] })
    releaseOlder(); await flushPromises()
    expect(reset).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(500); await flushPromises()
    expect(current.report().page_id).toBe(pageId)
    expect(publishedRevision).toBe(1)
  } finally { stop() }
})

it('acknowledges a refusal in the original window and ignores redelivery', async () => {
  vi.useFakeTimers()
  const feedback = vi.fn()
  const exchanges: any[] = []
  const event = { seq: 17, command_id: 'outdated', action: 'enlarge', target_panel: 'chart',
    open: false, status: 'rejected', code: 'STALE_REVISION' }
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/pages')) return Response.json({ protocol: 'agent-frontend/1', session_id: 'one',
      target: { instance_id: 'instance', probe_id: 'lobby', device_generation: 1, project_root: 'project' } })
    exchanges.push(JSON.parse(String(init?.body)))
    return Response.json({ command: null, feedback: [event] })
  }))
  const stop = connectFrontend({
    adapter: { title: 'One window', catalog: () => ({}), actions: {}, read: () => ({}), execute: vi.fn() },
    ready: vi.fn(), reset: vi.fn(), error: vi.fn(), busy: vi.fn(), feedback,
  })
  try {
    await flushPromises()
    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()
    expect(exchanges[0]).not.toHaveProperty('feedback_ack')
    expect(exchanges[1].feedback_ack).toBe(17)
    expect(feedback.mock.calls).toEqual([[event]])
  } finally { stop() }
})
