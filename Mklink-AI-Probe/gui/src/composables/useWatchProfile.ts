import { ref, shallowRef } from 'vue'
import { API_BASE } from '../lib/runtimeEndpoint'

type Section = { revision: string; [key: string]: any }
type Profile = { path: string; available?: boolean; error: string; missing: string[]; viewer: Section; layout: Section }
const profile = shallowRef<Profile | null>(null)
const error = ref(''), saving = ref(false)
let queue: Promise<unknown> = Promise.resolve(), pending = 0, loading = false
let stagedLayout: { path: string; value: Record<string, unknown> } | null = null
let layoutTimer: ReturnType<typeof setTimeout> | undefined

function applyViewer() {
  if (profile.value?.path && profile.value.available !== false)
    (window as any).__waveformViewers?.SuperWatch?.setProfilePreferences?.(profile.value.viewer.viewer, profile.value.path)
}

async function load() {
  if (loading || pending || stagedLayout) return
  loading = true
  try {
    const response = await fetch(API_BASE + '/api/dash/superwatch/profile')
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || response.statusText)
    if (typeof data.path !== 'string' || !data.viewer?.revision || !data.layout?.revision) return
    if (pending || stagedLayout) return // A GET started before a local edit must not overwrite that edit.
    const old = profile.value
    profile.value = data
    error.value = data.error || ''
    if (old?.path !== data.path || old?.viewer.revision !== data.viewer.revision
        || old?.viewer.viewer.interval !== data.viewer.viewer.interval) applyViewer()
    if (old?.path !== data.path)
      window.dispatchEvent(new CustomEvent('mklink:watch-profile-loaded'))
  } catch (e) { error.value = String(e) }
  finally { loading = false }
}

function save(section: 'viewer' | 'layout', value: Record<string, unknown>): Promise<void> {
  const current = profile.value
  if (!current?.path || current.available === false) return Promise.resolve()
  const snapshot = JSON.parse(JSON.stringify(value))
  if (JSON.stringify(snapshot) === JSON.stringify(current[section][section])) return Promise.resolve()
  pending++; saving.value = true
  const operation = queue.then(async () => {
    if (profile.value?.path !== current.path) throw new Error('AXF/ELF changed before settings were saved; reload settings')
    const body = JSON.stringify({ section, value: snapshot, revision: profile.value[section].revision })
    const response = await fetch(API_BASE + '/api/dash/superwatch/profile', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body, keepalive: new TextEncoder().encode(body).length < 60000,
    })
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || response.statusText)
    if (profile.value?.path === current.path) {
      profile.value = { ...profile.value, [section]: data }
      error.value = ''
    }
  }).catch(e => { error.value = String(e) }).finally(() => { pending--; saving.value = pending > 0 || !!stagedLayout })
  queue = operation
  return operation
}

function flushLayout() {
  clearTimeout(layoutTimer)
  const staged = stagedLayout
  stagedLayout = null
  if (staged && staged.path === profile.value?.path) void save('layout', staged.value)
  saving.value = pending > 0
}

function scheduleLayout(value: Record<string, unknown>) {
  if (!profile.value?.path || profile.value.available === false) return
  if (JSON.stringify(value) === JSON.stringify(profile.value.layout.layout)) return
  stagedLayout = { path: profile.value.path, value: JSON.parse(JSON.stringify(value)) }
  saving.value = true
  clearTimeout(layoutTimer)
  layoutTimer = setTimeout(flushLayout, 250)
}

export async function flushWatchProfile() {
  ;(window as any).__waveformViewers?.SuperWatch?.flushPreferences?.()
  flushLayout()
  await queue
}

if (typeof window !== 'undefined') {
  window.addEventListener('mklink:viewer-preferences', event => {
    void save('viewer', (event as CustomEvent).detail)
  })
  window.addEventListener('mklink:watch-viewer-ready', applyViewer)
  window.addEventListener('pagehide', () => { void flushWatchProfile() })
}

export function useWatchProfile() { return { profile, error, saving, load, save, scheduleLayout } }
