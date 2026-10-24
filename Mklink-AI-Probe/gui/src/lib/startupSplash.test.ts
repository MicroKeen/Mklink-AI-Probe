import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { startWorkspace } from './startupWorkflow'

const source = readFileSync(resolve(process.cwd(), 'index.html'), 'utf8')
const previous = window.location.href
beforeEach(() => {
  vi.useFakeTimers()
  vi.stubGlobal('localStorage', { getItem: () => null })
  document.body.innerHTML = source.slice(source.indexOf('<body>') + 6, source.indexOf('<script>'))
})
afterEach(() => {
  vi.clearAllTimers(); vi.useRealTimers(); vi.unstubAllGlobals()
  document.body.innerHTML = ''; history.replaceState(null, '', previous)
})
function startSplash() { new Function(source.split('<script>')[1]!.split('</script>')[0]!)() }
it('does not invent completed work while a service is delayed', async () => {
  startSplash()
  window.__MKLINK_STARTUP__!.step('backend', 'active')
  await vi.advanceTimersByTimeAsync(60_000)
  expect(document.querySelector('[role="progressbar"]')?.getAttribute('aria-valuenow')).toBe('30')
  expect(document.getElementById('startup-status')?.hidden).toBe(true)
  window.__MKLINK_STARTUP__!.step('modules', 'done')
  expect(document.querySelector('[role="progressbar"]')?.getAttribute('aria-valuenow')).toBe('60')
  await vi.advanceTimersByTimeAsync(60_000)
  expect(document.getElementById('startup-percent')?.textContent).toBe('60%')
  window.__MKLINK_STARTUP__!.fail()
  expect(document.getElementById('startup-status')?.hidden).toBe(false)
  expect(document.getElementById('startup-retry')?.hidden).toBe(false)
  expect(document.getElementById('startup-splash')?.getAttribute('role')).toBe('alert')
})
it.each(['backend', 'modules'] as const)('advances through four milestones when %s completes first', first => {
  startSplash()
  const startup = window.__MKLINK_STARTUP__!
  const percent = () => document.getElementById('startup-percent')?.textContent
  expect(percent()).toBe('30%')
  startup.step(first, 'done')
  expect(percent()).toBe('60%')
  startup.step(first === 'backend' ? 'modules' : 'backend', 'done')
  expect(percent()).toBe('90%')
  startup.step('workspace', 'active')
  expect(percent()).toBe('90%')
  startup.step('workspace', 'done')
  startup.finish()
  expect(percent()).toBe('100%')
  expect(document.getElementById('startup-progress-fill')?.style.width).toBe('100%')
  expect(document.querySelector('.startup-steps')).toBeNull()
  expect(document.getElementById('startup-status')?.hidden).toBe(true)
})
it('preserves the one-shot probe transition and removes the splash on completion', () => {
  history.replaceState(null, '', '/?runtime_transition=probe#/config')
  startSplash()
  window.__MKLINK_STARTUP__!.step('backend', 'active')
  expect(document.getElementById('startup-status')?.textContent).toContain('切换下载器')
  expect(window.location.search).toBe('')
  expect(window.location.hash).toBe('#/config')
  window.__MKLINK_STARTUP__!.finish()
  vi.runAllTimers()
  expect(document.getElementById('startup-splash')).toBeNull()
})
it('preloads modules concurrently but does not mount before the endpoint settles', async () => {
  let ready!: () => void
  const mount = vi.fn(async () => {})
  const load = vi.fn(async () => 'modules')
  const steps = vi.fn()
  const starting = startWorkspace({ backend: () => new Promise<void>(r => { ready = r }), load, mount, step: steps, backendFailed: vi.fn() })
  await Promise.resolve()
  expect(load).toHaveBeenCalledOnce()
  expect(mount).not.toHaveBeenCalled()
  ready(); await starting
  expect(mount).toHaveBeenCalledWith('modules')
  expect(steps).toHaveBeenLastCalledWith('workspace', 'done')
})
it('opens the recovery workspace when the backend fails without claiming it is ready', async () => {
  const steps = vi.fn(), failed = vi.fn(), mount = vi.fn(async () => {})
  await startWorkspace({ backend: async () => { throw Error('startup failed') }, load: async () => 'modules', mount, step: steps, backendFailed: failed })
  expect(steps).toHaveBeenCalledWith('backend', 'failed')
  expect(steps).not.toHaveBeenCalledWith('backend', 'done')
  expect(failed).toHaveBeenCalledOnce()
  expect(mount).toHaveBeenCalledOnce()
})
it('keeps a failed workspace from being marked complete', async () => {
  const steps = vi.fn()
  await expect(startWorkspace({ backend: async () => {}, load: async () => 'modules', mount: async () => { throw Error('render failed') }, step: steps, backendFailed: vi.fn() })).rejects.toThrow('render failed')
  expect(steps).toHaveBeenLastCalledWith('workspace', 'failed')
})
