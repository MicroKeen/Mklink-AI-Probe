import { computed, onUnmounted, ref, type Ref } from 'vue'
import type { PortInfo } from '../types/mklink'
import { API_BASE } from '../lib/runtimeEndpoint'
import { tr } from './useLanguage'
import { useToast } from './useToast'

// UART_BAUD_PROFILE=1 / RS485_BAUD_PROFILE=1, kept in sync with mklink.uart_baud.
// Without a matching firmware declaration these are candidates, not guarantees.
export const UART_BAUD_RATES = [
  300, 600, 1200, 2400, 4800, 9600, 14400, 19200, 38400,
  56000, 57600, 115200, 128000, 230400, 256000, 460800,
  512000, 750000, 921600, 1000000, 1500000, 2000000,
  2500000, 3000000, 3500000, 4000000, 4500000, 5000000,
  6000000, 7000000, 7500000, 8000000, 9000000, 10000000,
]

export function useUartBaudrates(ports: Ref<PortInfo[]>, portName: Readonly<Ref<string>>, busy: () => boolean) {
  const toast = useToast()
  const readingBaudrates = ref(false)
  const selectedPort = computed(() => ports.value.find(port => port.device === portName.value))
  const isProbePort = computed(() => ['mklink_uart', 'mklink_rs485'].includes(selectedPort.value?.uart_kind || ''))
  const canReadBaudrates = computed(() => isProbePort.value && Boolean(selectedPort.value?.command_port))
  const hasFirmwareBaudrates = computed(() => {
    const options = selectedPort.value?.uart_baud
    return isProbePort.value && options?.profile === 1 && options.source === 'firmware'
      && Array.isArray(options.rates) && options.rates.length > 0
      && new Set(options.rates).size === options.rates.length
      && options.rates.every(rate => UART_BAUD_RATES.includes(rate))
  })
  const baudrates = computed(() => hasFirmwareBaudrates.value
    ? [...selectedPort.value!.uart_baud!.rates].sort((a, b) => a - b) : UART_BAUD_RATES)
  const baudrateSourceLabel = computed(() => hasFirmwareBaudrates.value
    ? selectedPort.value?.uart_kind === 'mklink_rs485'
      ? tr('下载器固件声明的 RS485 档位', 'RS485 rates advertised by the probe firmware')
      : tr('下载器固件声明的普通 UART 档位', 'Ordinary UART rates advertised by the probe firmware')
    : tr('预设档位，实际支持以设备和驱动为准', 'Preset rates; actual support depends on the device and driver'))
  let disposed = false
  onUnmounted(() => { disposed = true })

  async function readBaudrates(): Promise<void> {
    if (readingBaudrates.value || busy() || !canReadBaudrates.value) return
    const requested = selectedPort.value!
    readingBaudrates.value = true
    try {
      const response = await fetch(`${API_BASE}/api/runtime/uart-baudrates`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ port: requested.device }),
      })
      const result = await response.json()
      if (disposed || selectedPort.value !== requested || busy()) return
      if (!response.ok) throw new Error(typeof result?.detail === 'string'
        ? result.detail : result?.detail?.message || result?.detail?.conflict || response.statusText)
      if (result.device !== requested.device || result.uart_kind !== requested.uart_kind
        || result.command_port !== requested.command_port || result.usb_serial !== requested.usb_serial) {
        throw new Error(tr('串口身份已变化，请刷新', 'Port identity changed; refresh ports'))
      }
      ports.value = ports.value.map(port => port === requested ? result : port)
      if (!hasFirmwareBaudrates.value) {
        toast.info(result.uart_baud?.firmware_warning || tr('固件未声明有效档位，保留预设列表', 'Firmware has no valid rate list; keeping preset choices'))
      }
    } catch (caught) {
      if (!disposed) toast.error(caught instanceof Error ? caught.message : String(caught))
    } finally {
      readingBaudrates.value = false
    }
  }
  return { baudrates, baudrateSourceLabel, canReadBaudrates, readingBaudrates, readBaudrates }
}
