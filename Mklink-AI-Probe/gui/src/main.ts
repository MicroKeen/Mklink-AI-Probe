import { createApp } from 'vue'
import { initializeTheme } from './composables/useTheme'
import './assets/theme.css'

initializeTheme()
import { initializeRuntimeEndpoint } from './lib/runtimeEndpoint'
import { IS_TAURI } from './lib/runtimeEndpoint'
import { invoke } from '@tauri-apps/api/core'
import { startWorkspace, type StartupStep, type StepState } from './lib/startupWorkflow'

type StartupController = {
  step: (step: StartupStep, state: StepState) => void
  fail: () => void
  finish: () => void
  timings: Record<string, number>
}

declare global {
  interface Window {
    __MKLINK_STARTUP__?: StartupController
  }
}

async function startApp() {
  try {
    await startWorkspace({
      backend: initializeRuntimeEndpoint,
      load: () => Promise.all([import('./App.vue'), import('./router')]),
      backendFailed: error => console.error('[main] backend endpoint initialization failed:', error),
      step: (step, state) => window.__MKLINK_STARTUP__?.step(step, state),
      mount: async ([{ default: App }, { default: router }]) => {
        const app = createApp(App).use(router)
        await router.isReady()
        app.mount('#app')
        await new Promise<void>(resolve => window.requestAnimationFrame(() => {
          window.requestAnimationFrame(() => resolve())
        }))
      },
    })
    window.__MKLINK_STARTUP__?.finish()
  } catch (error) {
    console.error('[main] workspace initialization failed:', error)
    window.__MKLINK_STARTUP__?.fail()
  }
  if (IS_TAURI) void invoke('record_startup_timing', {
    timings: window.__MKLINK_STARTUP__?.timings ?? {},
  }).catch(() => { /* Optional measurements must never block startup. */ })
}

void startApp()
