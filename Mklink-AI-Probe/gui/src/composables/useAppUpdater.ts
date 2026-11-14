import { isTauri } from '@tauri-apps/api/core'
import { relaunch } from '@tauri-apps/plugin-process'
import { check, type Update } from '@tauri-apps/plugin-updater'
import { ref } from 'vue'
import { reserveHostUpdate } from '../lib/updateCoordination'
import { tr } from './useLanguage'

export type AppUpdateState = 'idle' | 'checking' | 'downloading' | 'ready' | 'installing' | 'restart-required' | 'unavailable' | 'error'

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

export function useAppUpdater(canInstall: () => boolean = () => true) {
  const state = ref<AppUpdateState>('idle')
  const version = ref('')
  const progress = ref<number | null>(null)
  const error = ref('')
  const blocked = ref('')
  let availableUpdate: Update | null = null
  let installed = false

  async function checkForUpdates() {
    if (!isTauri()) return
    if (['checking', 'downloading', 'installing', 'restart-required'].includes(state.value)) return

    state.value = 'checking'
    version.value = ''
    progress.value = null
    error.value = ''
    blocked.value = ''
    availableUpdate = null

    try {
      const update = await check({ timeout: 8000 })
      if (!update) {
        state.value = 'idle'
        return
      }

      availableUpdate = update
      version.value = update.version
      state.value = 'downloading'
      let contentLength = 0
      let downloaded = 0
      await update.download(event => {
        if (event.event === 'Started') {
          contentLength = event.data.contentLength ?? 0
          progress.value = contentLength > 0 ? 0 : null
        } else if (event.event === 'Progress') {
          downloaded += event.data.chunkLength
          progress.value = contentLength > 0 ? Math.min(1, downloaded / contentLength) : null
        } else {
          progress.value = 1
        }
      })
      state.value = 'ready'
    } catch (value) {
      const detail = message(value)
      // Only the updater's missing-platform response is informational. Network,
      // signature and download failures must remain visible errors.
      const missingPlatform = availableUpdate === null && /^None of the fallback platforms .+ were found in the response .platforms. object$/.test(detail)
      error.value = missingPlatform ? '' : detail
      state.value = missingPlatform ? 'unavailable' : 'error'
    }
  }

  async function installAndRelaunch() {
    if (!availableUpdate || !['ready', 'restart-required'].includes(state.value) || !canInstall()) return
    state.value = 'installing'
    error.value = ''
    blocked.value = ''
    let release: (() => Promise<void>) | undefined
    try {
      release = await reserveHostUpdate()
    } catch (value) {
      blocked.value = message(value)
      state.value = installed ? 'restart-required' : 'ready'
      return
    }
    try {
      if (!installed) {
        await availableUpdate.install()
        installed = true
      }
      await relaunch()
    } catch (value) {
      error.value = installed ? tr('更新已安装，请重新启动上位机后再升级固件。', 'The update is installed. Restart the app before updating firmware.') : message(value)
      state.value = installed ? 'restart-required' : 'error'
    } finally {
      await release()
    }
  }

  return {
    state,
    version,
    progress,
    error,
    blocked,
    checkForUpdates,
    retry: checkForUpdates,
    installAndRelaunch,
  }
}
