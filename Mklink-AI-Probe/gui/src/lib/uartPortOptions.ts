import type { PortInfo } from '../types/mklink'

type PortOption = Pick<PortInfo, 'device' | 'description' | 'uart_kind'>
type KnownKind = 'mklink_uart' | 'mklink_rs485'

export function uartPortLabel(port: PortOption): string {
  if (port.uart_kind === 'mklink_uart') return `MKLink UART (TTL) · ${port.device}`
  if (port.uart_kind === 'mklink_rs485') return `MKLink RS485 · ${port.device}`
  const description = port.description?.trim()
  return description && description.toLowerCase() !== 'n/a' ? `${port.device} · ${description}` : port.device
}

export function orderUartPorts(ports: PortInfo[], preferred: KnownKind): PortInfo[] {
  function rank(port: PortInfo) {
    if (port.uart_kind === preferred) return 0
    if (port.uart_kind === 'mklink_uart' || port.uart_kind === 'mklink_rs485') return 1
    return 2
  }
  return [...ports].sort((a, b) => rank(a) - rank(b))
}
