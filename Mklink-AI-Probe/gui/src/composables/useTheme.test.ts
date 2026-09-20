import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { initializeTheme, setTheme, themePreference, resolvedTheme } from './useTheme'
let cleanup: () => void
let change: () => void
let dark: boolean
beforeEach(() => {
 const values = new Map<string, string>()
 vi.stubGlobal('localStorage', { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value), clear: () => values.clear() })
 dark = false
 vi.stubGlobal('matchMedia', () => ({ get matches() { return dark }, addEventListener: (_: string, cb: () => void) => { change = cb }, removeEventListener: vi.fn() }))
})
afterEach(() => { cleanup?.(); vi.unstubAllGlobals() })
describe('appearance preference', () => {
 it('defaults to dark on a clean install even when the OS is light', () => {
  cleanup = initializeTheme()
  expect(themePreference.value).toBe('dark')
  expect(resolvedTheme.value).toBe('dark')
  change(); expect(resolvedTheme.value).toBe('dark')
 })
 it('follows OS changes only in system mode', () => {
  localStorage.setItem('mklink_theme', 'system')
  cleanup = initializeTheme(); expect(resolvedTheme.value).toBe('light')
  dark = true; change(); expect(document.documentElement.dataset.theme).toBe('dark')
  setTheme('light'); change(); expect(resolvedTheme.value).toBe('light')
  setTheme('system'); expect(resolvedTheme.value).toBe('dark')
 })
 it('persists explicit choice across initialization and notifies existing canvases', () => {
  cleanup = initializeTheme(); const notify = vi.fn(); window.addEventListener('mklink-theme-change', notify)
  setTheme('dark'); expect(notify).toHaveBeenCalledOnce(); expect(localStorage.getItem('mklink_theme')).toBe('dark')
  cleanup(); cleanup = initializeTheme(); expect(themePreference.value).toBe('dark')
  expect(document.documentElement.style.colorScheme).toBe('dark'); window.removeEventListener('mklink-theme-change', notify)
 })
 it('syncs other same-origin windows and safely handles an invalid stored preference', () => {
  localStorage.setItem('mklink_theme', 'invalid'); cleanup = initializeTheme(); expect(themePreference.value).toBe('dark')
  window.dispatchEvent(new StorageEvent('storage', { key: 'mklink_theme', newValue: 'dark' }))
  expect(resolvedTheme.value).toBe('dark')
 })
 it('still switches when storage is denied', () => {
  cleanup = initializeTheme(); const spy = vi.spyOn(localStorage, 'setItem').mockImplementation(() => { throw new Error('denied') })
  setTheme('dark'); expect(resolvedTheme.value).toBe('dark'); spy.mockRestore()
 })
})
