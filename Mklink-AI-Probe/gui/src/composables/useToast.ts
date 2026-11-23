import { ref, inject, getCurrentInstance } from 'vue'
import { workbenchActivityKey, activitySourceKey } from '../lib/workbenchActivity'

export interface Toast {
  id: number
  type: 'success' | 'error' | 'warn' | 'info'
  message: string
  duration: number
}

const toasts = ref<Toast[]>([])
let nextId = 0

export function useToast() {
  const activity = getCurrentInstance() ? inject(workbenchActivityKey, null) : null
  const source = getCurrentInstance() ? inject(activitySourceKey, '') : ''
  function show(type: Toast['type'], message: string, duration = 4000) {
    const id = nextId++
    toasts.value.push({ id, type, message, duration })
    if (activity && source) activity.append({ kind: type === 'error' ? 'error' : 'note', source, title: message.slice(0, 200), text: message.length > 200 ? message.slice(0, 4000) : '', status: type === 'error' ? 'failed' : type === 'success' ? 'completed' : type })
    if (duration > 0) {
      setTimeout(() => dismiss(id), duration)
    }
  }

  function dismiss(id: number) {
    const i = toasts.value.findIndex(t => t.id === id)
    if (i >= 0) toasts.value.splice(i, 1)
  }

  function success(msg: string, duration?: number) { show('success', msg, duration) }
  function error(msg: string, duration?: number) { show('error', msg, duration ?? 6000) }
  function warn(msg: string, duration?: number) { show('warn', msg, duration) }
  function info(msg: string, duration?: number) { show('info', msg, duration) }

  return { toasts, show, dismiss, success, error, warn, info }
}
