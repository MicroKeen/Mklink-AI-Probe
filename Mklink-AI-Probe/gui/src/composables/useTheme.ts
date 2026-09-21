import { readonly, ref } from 'vue'

export type ThemePreference = 'light' | 'dark' | 'system'
const KEY = 'mklink_theme'
const preference = ref<ThemePreference>('dark')
const resolved = ref<'light' | 'dark'>('dark')
let stop: (() => void) | undefined
let media: MediaQueryList | undefined
const valid = (value: unknown): value is ThemePreference => ['light', 'dark', 'system'].includes(String(value))

function apply(): void {
  resolved.value = preference.value === 'system' ? (media?.matches ? 'dark' : 'light') : preference.value
  document.documentElement.dataset.theme = resolved.value
  document.documentElement.style.colorScheme = resolved.value
  window.dispatchEvent(new CustomEvent('mklink-theme-change', { detail: resolved.value }))
}

export function initializeTheme(): () => void {
  stop?.()
  try {
    const saved = localStorage.getItem(KEY)
    preference.value = valid(saved) ? saved : 'dark'
  } catch { preference.value = 'dark' }
  media = window.matchMedia?.('(prefers-color-scheme: dark)')
  const changed = () => { if (preference.value === 'system') apply() }
  const storage = (event: StorageEvent) => {
    if (event.key !== KEY && event.key !== null) return
    preference.value = valid(event.newValue) ? event.newValue : 'dark'
    apply()
  }
  media?.addEventListener('change', changed)
  window.addEventListener('storage', storage)
  const currentMedia = media
  stop = () => {
    currentMedia?.removeEventListener('change', changed)
    window.removeEventListener('storage', storage)
  }
  apply()
  return stop
}

export function setTheme(value: ThemePreference): void {
  if (!valid(value)) return
  preference.value = value
  try { localStorage.setItem(KEY, value) } catch { /* Keep this session usable without storage. */ }
  apply()
}

export const themePreference = readonly(preference)
export const resolvedTheme = readonly(resolved)
