import { describe, expect, it, vi } from 'vitest'
import { recoverPendingIntent, useFrontendWorkbench } from './useFrontendWorkbench'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, defineComponent, inject, h } from 'vue'
import { workbenchActivityKey, type WorkbenchActivity } from '../lib/workbenchActivity'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createGuiAutomation } from '../lib/guiAutomation'

it('maps the selected GUI window to its current semantic page without publishing credentials', async () => {
  const target = { instance_id: 'runtime-one', probe_id: 'lobby', device_generation: 0, project_root: 'D:/project' }
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith('/pages')
    ? { protocol: 'agent-frontend/1', session_id: 'session-one', target, pages: [] } : { command: null }))))
  let frontend: ReturnType<typeof useFrontendWorkbench>
  const wrapper = mount({ setup() { frontend = useFrontendWorkbench(ref('workbench'), ref(null), ref(null)) }, template: '<div/>' })
  try {
    await flushPromises()
    const gui = createGuiAutomation(createRouter({ history: createMemoryHistory(), routes: [] }), () => ({}))
    expect(gui.snapshot().panels.workbench).toEqual({ connected: true, protocol: 'agent-frontend/1',
      session_id: 'session-one', page_id: frontend!.runtime.value!.report().page_id, target })
    wrapper.unmount()
    expect(gui.snapshot().panels).not.toHaveProperty('workbench')
  } finally { wrapper.unmount(); vi.unstubAllGlobals() }
})

const pending = { request_id: 'original_request', session_id: 'original_target', page_id: 'original_page',
  revision: 3, object_id: 'panel', intent: 'inspect', message: 'Inspect the captured state' }

describe('pending frontend intent recovery', () => {
  it('reads a persisted original request after the target changes without resubmitting', async () => {
    const saved = { request_id: pending.request_id, request: pending, status: 'pending', revision: 0 }
    const request = vi.fn().mockResolvedValue(saved)
    expect(await recoverPendingIntent(pending, request)).toBe(saved)
    expect(request.mock.calls).toEqual([['intent?request_id=original_request']])
  })
  it('permits explicit abandonment when the original request is absent and its target ended', async () => {
    const request = vi.fn().mockRejectedValueOnce(Object.assign(new Error('Missing'), { status: 404 }))
      .mockResolvedValueOnce({ session_id: 'new_target', pages: [] })
    await expect(recoverPendingIntent(pending, request)).rejects.toMatchObject({ pending, canDiscard: true })
    expect(request.mock.calls).toEqual([['intent?request_id=original_request'], ['pages']])
  })
  it('only retries the exact original request when its original page is still live', async () => {
    const request = vi.fn().mockRejectedValueOnce(Object.assign(new Error('Missing'), { status: 404 }))
      .mockResolvedValueOnce({ session_id: pending.session_id, pages: [{ page_id: pending.page_id, online: true }] })
      .mockResolvedValueOnce({ request_id: pending.request_id, status: 'pending' })
    await recoverPendingIntent(pending, request)
    expect(request).toHaveBeenLastCalledWith('intent', pending)
    expect(request.mock.calls[2]![1]).toBe(pending)
  })
  it('keeps unknown reads unresolved without creating or retrying a request', async () => {
    const request = vi.fn().mockRejectedValue(new TypeError('Connection lost'))
    await expect(recoverPendingIntent(pending, request)).rejects.toThrow('Connection lost')
    expect(request).toHaveBeenCalledTimes(1)
  })
})

it('receives a complete delayed answer after the question dialog is closed, without sending another request', async () => {
  vi.useFakeTimers()
  sessionStorage.clear()
  const target = { instance_id: 'runtime-one', probe_id: 'lobby', device_generation: 0, project_root: 'D:/project' }
  const reply = 'Answer '.repeat(1000)
  let answered = false, frontend: ReturnType<typeof useFrontendWorkbench>, activity: WorkbenchActivity
  const fetcher = vi.fn(async (url: string) => {
    const result = url.endsWith('/pages') ? { protocol: 'agent-frontend/1', session_id: 'session-one', target, pages: [] }
      : url.endsWith('/intent') ? { request_id: 'question_one', status: 'pending' }
      : url.includes('/intent?') ? { request_id: 'question_one', status: answered ? 'replied' : 'pending', reply }
      : { command: null }
    return new Response(JSON.stringify(result))
  })
  vi.stubGlobal('fetch', fetcher)
  const Child = defineComponent({ setup() { activity = inject(workbenchActivityKey)!; return () => h('div', activity.latestAnswer()?.text) } })
  const wrapper = mount({ setup() { frontend = useFrontendWorkbench(ref('workbench'), ref(null), ref(null)); return () => h(Child) } })
  try {
    await flushPromises()
    await frontend!.submitIntent('question_one', 'dashboard', 'inspect', 'Explain the result')
    expect(activity!.state.entries[0]?.kind).toBe('question')
    answered = true
    await vi.advanceTimersByTimeAsync(1600); await flushPromises()
    expect(wrapper.text()).toBe(reply.trim())
    expect(activity!.state.entries.filter(entry => entry.kind === 'answer')).toHaveLength(1)
    await vi.advanceTimersByTimeAsync(1600)
    expect(fetcher.mock.calls.filter(([url]) => url.endsWith('/intent'))).toHaveLength(1)
    expect(activity!.state.entries.filter(entry => entry.kind === 'answer')).toHaveLength(1)
  } finally { wrapper.unmount(); vi.useRealTimers(); vi.unstubAllGlobals(); sessionStorage.clear() }
})
