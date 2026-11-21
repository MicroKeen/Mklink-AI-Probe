import { defineAsyncComponent } from 'vue'
import { tr } from '../composables/useLanguage'

export const toolTypes = ['connection', 'superwatch', 'rtt', 'serial', 'memory', 'trace', 'hardfault', 'symbols', 'peripherals', 'modbus', 'online-flash', 'offline-flash', 'files', 'firmware', 'runtime', 'remote-service'] as const
export type WorkbenchTool = typeof toolTypes[number]
const names: Record<WorkbenchTool, [string, string]> = {
  connection: ['连接与 SWD/JTAG', 'Connection and SWD/JTAG'], superwatch: ['SuperWatch 工作区', 'SuperWatch workspace'],
  rtt: ['RTT View 完整视图', 'RTT View workspace'], serial: ['串口助手', 'Serial assistant'], memory: ['内存视图', 'Memory'],
  trace: ['RTOS Trace', 'RTOS Trace'], hardfault: ['HardFault', 'HardFault'], symbols: ['符号表', 'Symbols'],
  peripherals: ['外设寄存器', 'Peripheral registers'], modbus: ['Modbus', 'Modbus'],
  'online-flash': ['在线烧录', 'Online flash'], 'offline-flash': ['脱机烧录与 OTP', 'Offline flash and OTP'],
  files: ['文件与符号来源', 'File sources'], firmware: ['探针固件', 'Probe firmware'], runtime: ['后台与诊断', 'Runtime and diagnostics'],
  'remote-service': ['远程服务', 'Remote service'],
}
export function toolLabel(type: WorkbenchTool) { return tr(...names[type]) }
export const remoteTools: readonly WorkbenchTool[] = ['superwatch', 'rtt', 'memory', 'trace', 'hardfault', 'symbols', 'peripherals']
const config = defineAsyncComponent(() => import('../views/ConfigView.vue'))
export const toolComponents = {
  connection: config, files: config, firmware: config, runtime: config,
  superwatch: defineAsyncComponent(() => import('../components/dash/SuperWatchTab.vue')),
  rtt: defineAsyncComponent(() => import('../components/dash/RttViewTab.vue')),
  serial: defineAsyncComponent(() => import('../components/dash/SerialMonitorTab.vue')),
  memory: defineAsyncComponent(() => import('../components/dash/MemoryTab.vue')),
  trace: defineAsyncComponent(() => import('../components/dash/SystemViewTab.vue')),
  hardfault: defineAsyncComponent(() => import('../components/dash/HardFaultTab.vue')),
  symbols: defineAsyncComponent(() => import('../components/dash/SymbolsTab.vue')),
  peripherals: defineAsyncComponent(() => import('../components/dash/PeripheralWatchPanel.vue')),
  modbus: defineAsyncComponent(() => import('../components/dash/ModbusTab.vue')),
  'online-flash': defineAsyncComponent(() => import('../views/OnlineFlashView.vue')),
  'offline-flash': defineAsyncComponent(() => import('../views/OfflineFlashView.vue')),
  'remote-service': defineAsyncComponent(() => import('../views/SiteAgentView.vue')),
}
