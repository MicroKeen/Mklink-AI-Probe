import { ref, onUnmounted } from 'vue'
import {
  API_BASE,
  IS_TAURI,
  applyReportedBackendPort,
  restartRuntimeBackend,
  runtimeBackendPort,
  refreshRuntimeEndpoint,
  backendStartupError,
} from '../lib/runtimeEndpoint'

/** 'starting' = backend not yet checked / currently booting */
const backendState = ref<'starting' | 'alive' | 'dead'>('starting')
export const sharedRuntime = ref(false)
const authenticationRequired = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null
let refCount = 0
let firstCheckDone = false
let restarting = false
let healthEpoch = 0
let pendingHealth: Promise<void> | null = null

async function checkBackendHealth(epoch = healthEpoch): Promise<boolean | null> {
  const endpoint = API_BASE
  const current = () => epoch === healthEpoch && endpoint === API_BASE
  try {
    const res = await fetch(`${endpoint}/api/health`, { signal: AbortSignal.timeout(3000) })
    if (!current()) return null
    authenticationRequired.value = res.status === 401
    if (!res.ok) return false
    const payload = await res.json().catch(() => null)
    if (!current()) return null
    if (payload && typeof payload === 'object') {
      applyReportedBackendPort((payload as { backend_port?: unknown }).backend_port)
      sharedRuntime.value = (payload as { shared_runtime?: unknown }).shared_runtime === true
    }
    return true
  } catch {
    if (!current()) return null
    authenticationRequired.value = false
    return false
  }
}

async function performHealthCheck(epoch: number) {
  if (restarting) return
  const alive = IS_TAURI
    ? await checkViaTauri(epoch)
    : await checkBackendHealth(epoch)

  if (restarting || epoch !== healthEpoch || alive === null) return
  if (alive) {
    backendState.value = 'alive'
    firstCheckDone = true
  } else if (firstCheckDone || authenticationRequired.value || backendStartupError.value) {
    // Network startup failures get a grace period; a 401 needs action immediately.
    backendState.value = 'dead'
  }
  // If !firstCheckDone && !alive, keep 'starting'
}

function refreshHealth(): Promise<void> {
  if (restarting) return Promise.resolve()
  // Startup ticks and manual refresh share one bounded request. A slow older
  // response must never overwrite a newer result or a restarted endpoint.
  if (pendingHealth) return pendingHealth
  const request = performHealthCheck(healthEpoch).finally(() => {
    if (pendingHealth === request) pendingHealth = null
  })
  pendingHealth = request
  return request
}

async function checkViaTauri(epoch: number): Promise<boolean | null> {
  // Events can be missed during WebView initialization or a proxy restart.
  // Always resolve this window's owned endpoint through the supported v2 IPC,
  // never keep probing port zero or an obsolete proxy address indefinitely.
  if (!await refreshRuntimeEndpoint()) return false
  if (epoch !== healthEpoch) return null
  return await checkBackendHealth(epoch)
}

function startHealthPolling(intervalMs = 5000) {
  if (pollTimer) return
  // Fast polling during startup (every 1s), then settle to intervalMs
  let fastPolls = 0
  const maxFastPolls = 15 // 15 × 1s = 15s of fast polling

  refreshHealth()
  pollTimer = setInterval(async () => {
    const epoch = healthEpoch
    fastPolls++
    await refreshHealth()
    if (epoch !== healthEpoch) return
    if (!restarting && fastPolls >= maxFastPolls && backendState.value === 'starting') {
      backendState.value = 'dead'
      firstCheckDone = true
    }
    // Switch to slower interval after first success or after max fast polls
    if ((backendState.value === 'alive' || fastPolls >= maxFastPolls) && pollTimer) {
      clearInterval(pollTimer)
      pollTimer = setInterval(refreshHealth, intervalMs)
    }
  }, 1000)
}

function stopHealthPolling() {
  healthEpoch++
  pendingHealth = null
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function restart(): Promise<void> {
  if (restarting) return
  restarting = true
  healthEpoch++
  pendingHealth = null
  try {
    backendState.value = 'starting'
    firstCheckDone = false
    if (IS_TAURI) {
      try {
        await restartRuntimeBackend()
      } catch (e) {
        console.error('[useBackendHealth] restart failed:', e)
        backendStartupError.value = String(e)
        backendState.value = 'dead'
        firstCheckDone = true
        return
      }
    }
    // Endpoint publication can precede HTTP readiness by a short interval.
    for (let i = 0; i < 30; i++) {
      await new Promise(r => setTimeout(r, 500))
      if (await checkBackendHealth()) {
        backendState.value = 'alive'
        firstCheckDone = true
        break
      }
    }
    if (backendState.value === 'starting') {
      backendState.value = 'dead'
      firstCheckDone = true
    }
  } finally {
    restarting = false
  }
}

export function useBackendHealth() {
  refCount++
  onUnmounted(() => {
    refCount--
    if (refCount <= 0) {
      stopHealthPolling()
      refCount = 0
    }
  })

  return {
    backendState,
    sharedRuntime,
    authenticationRequired,
    backendStartupError,
    backendPort: runtimeBackendPort,
    isTauri: IS_TAURI,
    startHealthPolling,
    stopHealthPolling,
    restart,
    refreshHealth,
  }
}
