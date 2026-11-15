import { API_BASE } from './runtimeEndpoint'

export async function readConnectionClock() {
  const response = await fetch(`${API_BASE}/api/device/debug-speed`)
  const payload = await response.json()
  if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : payload.detail?.message || response.statusText)
  if (!Array.isArray(payload.clocks_hz)) throw new Error('The backend does not support connection clock settings')
  return payload
}

export async function applyConnectionClock(status: any, mode: string, requested: number, applyToProbe: boolean) {
  const supported = status.interfaces?.[mode]?.clocks_hz || status.clocks_hz
  if (!['SWD', 'JTAG'].includes(mode) || !supported?.includes(requested)) throw new Error('Unsupported connection clock')
  const response = await fetch(`${API_BASE}${applyToProbe ? '/api/device/debug-speed' : '/api/config'}`, {
    method: applyToProbe ? 'POST' : 'PUT',
    headers: { 'Content-Type': 'application/json', ...(status.device_generation !== undefined ? { 'X-MKLink-Device-Generation': String(status.device_generation) } : {}) },
    body: JSON.stringify(applyToProbe ? { interface: mode, clock_hz: requested, save: true } : { clock_interface: mode, clock_hz: requested }),
  })
  const payload = await response.json()
  if (!response.ok) {
    throw Object.assign(new Error(typeof payload.detail === 'string' ? payload.detail : payload.detail?.message || response.statusText), { detail: payload.detail })
  }
  if (applyToProbe
    ? payload.interface !== mode || payload.configured_hz !== requested || !['configured', 'applied', 'acknowledged'].includes(payload.apply_state)
    : payload.clock_interface !== mode || Number(payload[`${mode.toLowerCase()}_clock`]) !== requested) throw new Error('The probe did not confirm the selected clock; check its current status.')
  return payload
}
