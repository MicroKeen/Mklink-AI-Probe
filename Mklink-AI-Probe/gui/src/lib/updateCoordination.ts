import { ref, type InjectionKey, type Ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'

export interface UpdateCoordination {
  clientPending: Ref<boolean>
  clientInstalling: Ref<boolean>
  firmwareBusy: Ref<boolean>
}
export const updateCoordinationKey: InjectionKey<UpdateCoordination> = Symbol('updateCoordination')
export function idleUpdateCoordination(): UpdateCoordination {
  return { clientPending: ref(false), clientInstalling: ref(false), firmwareBusy: ref(false) }
}

export async function reserveHostUpdate(): Promise<(() => Promise<void>) | undefined> {
  const acquired = await invoke<boolean>('begin_desktop_install')
  if (acquired) return () => invoke<void>('end_desktop_install')
}
