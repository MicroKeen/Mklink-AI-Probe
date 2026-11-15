import { ref, type InjectionKey, type Ref } from 'vue'
import { API_BASE } from './runtimeEndpoint'
import { tr } from '../composables/useLanguage'

export interface UpdateCoordination {
  clientPending: Ref<boolean>
  clientInstalling: Ref<boolean>
  firmwareBusy: Ref<boolean>
}
export const updateCoordinationKey: InjectionKey<UpdateCoordination> = Symbol('updateCoordination')
export function idleUpdateCoordination(): UpdateCoordination {
  return { clientPending: ref(false), clientInstalling: ref(false), firmwareBusy: ref(false) }
}

export async function reserveHostUpdate(): Promise<() => Promise<void>> {
  async function request(action: string, token?: string) {
    const response = await fetch(`${API_BASE}/api/runtime/host-update/${action}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: token ? JSON.stringify(token) : undefined,
      signal: AbortSignal.timeout(5000),
    })
    if (!response.ok) throw new Error(tr(
      '暂不能安装更新。请停止采集、断开探针，等待固件升级或其他设备操作结束，并关闭其他 MKLink 窗口和空闲后台后重试。若后台仍不可用，请关闭程序后使用安装包更新。',
      'Cannot install yet. Stop acquisition, disconnect the probe, wait for device or firmware operations, and close other MKLink windows and idle backends. Retry, or close the app and use the installer if the backend remains unavailable.',
    ))
    return response.json()
  }
  const { token } = await request('prepare')
  if (typeof token !== 'string' || !token) throw new Error(tr('未能确认更新前的设备状态。', 'Device activity could not be confirmed before updating.'))
  // Keep admission closed during the native install. A crashed window leaves
  // only a bounded reservation; network failures never trigger a device action.
  const timer = setInterval(() => { void request('renew', token).catch(() => undefined) }, 30000)
  return async () => {
    clearInterval(timer)
    await request('release', token).catch(() => undefined)
  }
}
