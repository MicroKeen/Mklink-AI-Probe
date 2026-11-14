/** Explicit per-window display operations. Hardware stays on the shared API. */
import { nextTick, onUnmounted } from 'vue'
import type { Router } from 'vue-router'
import { IS_TAURI } from './runtimeEndpoint'
import { listGuiControls, interactGuiControl } from './guiControls'
import { guiFileState, selectGuiFile, selectGuiDirectory, type GuiFile } from './guiFileSelection'

export type GuiCommand = { action: string; page?: string; tab?: string; section?: string; seconds?: number;
  control_id?: string; value?: unknown; offset?: number; expected_context?: string; file?: GuiFile; path?: string }
type Panel = { snapshot: () => unknown; actions: Record<string, (command: GuiCommand) => void | Promise<void>> }
const panels = new Map<string, Panel>()
export function useGuiPanel(name: string, panel: Panel) {
  panels.set(name, panel)
  onUnmounted(() => { if (panels.get(name) === panel) panels.delete(name) })
}

export function createGuiAutomation(router: Router, status: () => Record<string, unknown>) {
  const context = () => {
    const target = status()
    return JSON.stringify([router.currentRoute.value.fullPath, target.probe_id, target.device_generation])
  }
  const snapshot = () => ({
    ...status(), page: String(router.currentRoute.value.name || ''),
    tab: router.currentRoute.value.query.tab || null, section: router.currentRoute.value.query.section || null,
    visibility: document.visibilityState, focused: document.hasFocus(),
    context: context(),
    file: { ...guiFileState },
    panels: Object.fromEntries([...panels].map(([key, value]) => [key, value.snapshot()])),
    actions: ['snapshot', 'navigate', 'focus', 'controls', 'control.click', 'control.set', 'file.select', 'directory.select', ...[...panels.values()].flatMap(panel => Object.keys(panel.actions))],
    alerts: [...document.querySelectorAll('[role="alert"]')].slice(0, 8).map(el => el.textContent?.trim().slice(0, 256)),
  })
  const execute = async (command: GuiCommand) => {
    let result: unknown
    if (command.action === 'controls') result = listGuiControls(command.offset || 0)
    else if (command.action === 'directory.select') {
      if (command.expected_context !== context()) throw new Error('Page/target changed; read controls again')
      selectGuiDirectory(command.control_id!, command.path!)
    }
    else if (command.action === 'file.select') {
      if (command.expected_context !== context()) throw new Error('Page/target changed; read controls again')
      selectGuiFile(command.control_id!, command.file!, () => command.expected_context === context())
    } else if (command.action.startsWith('control.')) {
      if (command.expected_context !== context()) throw new Error('Page/target changed; read controls again')
      interactGuiControl(command.control_id!, command.action, command.value)
    } else
    if (command.action === 'navigate') {
      const page = command.page || 'dashboard'
      const pages = ['config', 'dashboard', 'online-flash', 'offline-flash', 'remote-service']
      const tabs = ['rtt', 'superwatch', 'hardfault', 'memory', 'serial', 'modbus', 'systemview', 'symbols']
      if (!pages.includes(page) || (command.tab && (page !== 'dashboard' || !tabs.includes(command.tab))) ||
          (command.section && (page !== 'config' || !['local', 'files', 'firmware', 'runtime'].includes(command.section)))) throw new Error('Unsupported destination')
      await router.push({ name: page, query: page === 'dashboard' ? { tab: command.tab || 'rtt' }
        : page === 'config' ? { section: command.section || 'local' } : {} })
      await nextTick()
      if (router.currentRoute.value.name !== page) throw new Error('Navigation was not applied')
    } else if (command.action === 'focus') {
      if (IS_TAURI) {
        const { getCurrentWindow } = await import('@tauri-apps/api/window')
        const win = getCurrentWindow()
        await win.show(); await win.unminimize(); await win.setFocus()
      } else window.focus() // Browser policy may refuse; snapshot reports actual focus.
    } else if (command.action !== 'snapshot') {
      const panel = [...panels.values()].find(value => value.actions[command.action])
      if (!panel) throw new Error('Panel is not mounted or this GUI action is unsupported; navigate first')
      await panel.actions[command.action]!(command)
    }
    await nextTick()
    return { ...snapshot(), ...(result ? { result } : {}) }
  }
  return { execute, snapshot }
}
