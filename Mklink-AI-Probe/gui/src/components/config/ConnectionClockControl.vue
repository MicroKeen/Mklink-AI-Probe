<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { API_BASE } from '../../lib/runtimeEndpoint'
import { tr } from '../../composables/useLanguage'

interface ClockStatus {
  connected: boolean
  device_generation?: number
  interface: string
  active_interface?: string
  selected_interface?: string
  interfaces?: Record<string, { clocks_hz: number[]; clock_source: string; requested_hz: number | null }>
  clocks_hz: number[]
  clock_source: string
  requested_hz: number | null
  configured_hz: number | null
  applied_hz: number | null
  apply_state: 'unknown' | 'acknowledged' | 'configured' | 'applied'
  migration?: { from_hz: number; to_hz: number; pending: boolean } | null
  warning?: string | null
}
const props = defineProps<{ deviceConnected: boolean; deviceGeneration?: number; disabled?: boolean }>()
const emit = defineEmits<{ busy: [value: boolean]; firmwareUpdate: [] }>()
const status = ref<ClockStatus | null>(null)
const selected = ref('10000000')
const selectedInterface = ref('SWD')
const dirty = ref(false)
const busy = ref(false)
const message = ref('')
const readError = ref('')
let disposed = false
let revision = 0
let timer: ReturnType<typeof setTimeout> | undefined

function frequency(hz: number): string {
  return hz >= 1_000_000 ? `${hz / 1_000_000} MHz` : `${hz / 1000} kHz`
}
const activeInterface = computed(() => status.value?.active_interface ?? status.value?.interface ?? 'unknown')
const matchingInterface = computed(() => props.deviceConnected && activeInterface.value === selectedInterface.value)
const interfaceConfig = computed(() => status.value?.interfaces?.[selectedInterface.value] ?? status.value)
const firmwareUpdateNeeded = computed(() => matchingInterface.value
  && ['legacy', 'hpm-profiles'].includes(interfaceConfig.value?.clock_source ?? ''))
const clocks = computed(() => interfaceConfig.value?.clocks_hz || [])
const migration = computed(() => ['v3-advertised', 'swd-advertised'].includes(interfaceConfig.value?.clock_source ?? '')
  && (interfaceConfig.value?.requested_hz === 4_000_000 || (matchingInterface.value && status.value?.configured_hz === 4_000_000))
  ? { from_hz: 4_000_000, to_hz: 2_000_000, pending: true } : null)
const legacyChoice = computed(() => selected.value && !clocks.value.includes(Number(selected.value)))
const canApply = computed(() => status.value?.connected === props.deviceConnected && !busy.value && !props.disabled
  && clocks.value.includes(Number(selected.value)))
const effectiveLabel = computed(() => {
  const s = status.value
  if (!props.deviceConnected || !s?.connected) return tr('连接时使用：', 'On connection: ') + frequency(interfaceConfig.value?.requested_hz ?? 10_000_000)
  if (!matchingInterface.value) return tr('已保存：', 'Saved: ') + frequency(interfaceConfig.value?.requested_hz ?? 10_000_000)
  if (s.apply_state === 'applied' && s.applied_hz) return tr('已应用：', 'Applied: ') + frequency(s.applied_hz)
  if (s.apply_state === 'configured' && s.configured_hz) return tr('已保存，待应用：', 'Saved, pending application: ') + frequency(s.configured_hz)
  if (s.configured_hz) return tr('下载器已确认设置：', 'Probe acknowledged setting: ') + frequency(s.configured_hz)
  return tr('下载器设置未确认', 'Probe setting unconfirmed')
})

async function refresh() {
  const current = revision
  try {
    const response = await fetch(`${API_BASE}/api/device/debug-speed`)
    if (!response.ok) throw new Error(tr('读取连接时钟失败', 'Failed to read connection clock'))
    const payload: ClockStatus = await response.json()
    if (disposed || current !== revision) return
    if (!Array.isArray(payload.clocks_hz)) throw new Error(tr('后台尚不支持连接时钟配置', 'The backend does not support connection clock settings'))
    status.value = payload
    readError.value = ''
    if (!dirty.value && !busy.value) {
      selectedInterface.value = payload.selected_interface || payload.interface
      const value = (matchingInterface.value ? payload.configured_hz : null) ?? interfaceConfig.value?.requested_hz ?? 10_000_000
      selected.value = String(value)
    }
  } catch (error) {
    if (!disposed && current === revision) {
      status.value = null
      readError.value = error instanceof Error ? error.message : String(error)
    }
  }
}

async function poll() {
  if (!busy.value) await refresh()
  if (!disposed) timer = setTimeout(poll, 1000)
}

async function apply() {
  if (!canApply.value) return
  const current = ++revision // Discard a GET that started before this mutation.
  busy.value = true
  message.value = ''
  const requested = Number(selected.value)
  const previousMigration = migration.value
  const mode = selectedInterface.value
  try {
    const applyToProbe = matchingInterface.value
    const response = await fetch(`${API_BASE}${applyToProbe ? '/api/device/debug-speed' : '/api/config'}`, {
      method: applyToProbe ? 'POST' : 'PUT',
      headers: { 'Content-Type': 'application/json',
        ...(status.value?.device_generation !== undefined
          ? { 'X-MKLink-Device-Generation': String(status.value.device_generation) } : {}) },
      body: JSON.stringify(applyToProbe ? { interface: mode, clock_hz: requested, save: true } : { clock_interface: mode, clock_hz: requested }),
    })
    const payload = await response.json()
    if (!response.ok) {
      const detail = payload.detail
      if (Array.isArray(detail?.busy) && detail.busy.length) throw new Error(tr(
        '此固件暂不支持采集中改频率。请先停止采集，再应用时钟；原任务保持运行。',
        'This firmware cannot change the clock during acquisition. Stop acquisition, then apply; existing captures remain running.',
      ))
      throw new Error(typeof detail === 'string' ? detail : detail?.message || response.statusText)
    }
    if (disposed || current !== revision) return
    if (applyToProbe
      ? payload.interface !== mode || payload.configured_hz !== requested || !['configured', 'applied', 'acknowledged'].includes(payload.apply_state)
      : payload.clock_interface !== mode || Number(payload[`${mode.toLowerCase()}_clock`]) !== requested) {
      throw new Error(tr('下载器未确认所选时钟，请核对当前状态。', 'The probe did not confirm the selected clock; check its current status.'))
    }
    dirty.value = false
    if (previousMigration?.from_hz === 4_000_000 && requested === previousMigration.to_hz) {
      message.value = tr('旧 4 MHz 配置已迁移到 2 MHz。', 'The old 4 MHz configuration was migrated to 2 MHz.')
    }
  } catch (error) {
    if (!disposed && current === revision) message.value = error instanceof Error ? error.message : String(error)
  } finally {
    if (!disposed && current === revision) {
      busy.value = false
      await refresh() // Read cached truth even after an unknown or rejected result. Never replay the POST.
    }
  }
}

async function selectClock() {
  dirty.value = true
  await apply()
}

async function selectInterface() {
  if (busy.value || props.disabled || !status.value) return
  const current = ++revision
  busy.value = true
  dirty.value = false
  message.value = ''
  selected.value = String(interfaceConfig.value?.requested_hz ?? 10_000_000)
  try {
    const response = await fetch(`${API_BASE}/api/config`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json',
        ...(status.value?.device_generation !== undefined
          ? { 'X-MKLink-Device-Generation': String(status.value.device_generation) } : {}) },
      body: JSON.stringify({ clock_interface: selectedInterface.value }),
    })
    const payload = await response.json()
    if (!response.ok || payload.clock_interface !== selectedInterface.value) {
      throw new Error(typeof payload.detail === 'string' ? payload.detail : tr('保存接口配置失败', 'Failed to save interface preference'))
    }
  } catch (error) {
    if (!disposed && current === revision) message.value = error instanceof Error ? error.message : String(error)
  } finally {
    if (!disposed && current === revision) { busy.value = false; await refresh() }
  }
}

watch(busy, value => emit('busy', value), { flush: 'sync' })
watch(() => [props.deviceConnected, props.deviceGeneration], () => {
  revision++
  status.value = null
  selected.value = '10000000'
  dirty.value = false
  busy.value = false
  message.value = ''
  readError.value = ''
  void refresh()
})
onMounted(poll)
onUnmounted(() => { disposed = true; revision++; clearTimeout(timer); emit('busy', false) })
</script>

<template>
  <div class="connection-clock" data-testid="connection-clock">
    <div class="form-row clock-row">
      <label class="form-label" for="connection-clock-interface">{{ tr('接口 / 时钟', 'Interface / Clock') }}</label>
      <select id="connection-clock-interface" v-model="selectedInterface" class="form-select interface-select" :aria-label="tr('时钟接口', 'Clock interface')" :disabled="busy || disabled || !status" @change="selectInterface">
        <option value="SWD">SWD</option><option value="JTAG">JTAG</option>
      </select>
      <select id="connection-clock-hz" v-model="selected" class="form-select" data-testid="swd-clock" :aria-label="tr('时钟频率', 'Clock frequency')" :disabled="busy || disabled || !status" @change="selectClock">
        <option v-if="legacyChoice" :value="selected" disabled>{{ frequency(Number(selected)) }} · {{ tr('旧配置，请重新选择', 'Previous setting; select a supported clock') }}</option>
        <option v-for="hz in clocks" :key="hz" :value="String(hz)">{{ frequency(hz) }}</option>
      </select>
      <button v-if="dirty || (matchingInterface && status?.apply_state === 'configured')" class="btn btn-sm" data-testid="apply-connection-clock" :disabled="!canApply" @click="apply">{{ busy ? tr('保存中…', 'Saving…') : tr('重新应用', 'Apply again') }}</button>
      <span class="clock-state" data-testid="connection-clock-state">{{ effectiveLabel }}</span>
      <span v-if="deviceConnected" class="clock-state">{{ tr('当前接口：', 'Active interface: ') }}{{ activeInterface === 'unknown' ? tr('未确认', 'Unconfirmed') : activeInterface }}</span>
    </div>
    <p class="clock-help">{{ tr('SWD/JTAG 分别保存，默认 10 MHz；连接后按下载器支持的档位应用，采集与内存访问共用。', 'SWD/JTAG settings are saved separately, defaulting to 10 MHz. Supported settings apply on connection and are shared by acquisition and memory access.') }}</p>
    <p v-if="firmwareUpdateNeeded" class="clock-message" role="status" data-testid="clock-firmware-update">
      {{ tr('当前固件不支持完整时钟档位，请更新下载器固件。', 'This firmware does not support the full clock range. Please update the probe firmware.') }}
      <button type="button" class="btn btn-sm" @click="emit('firmwareUpdate')">{{ tr('前往固件升级', 'Open Firmware Update') }}</button>
    </p>
    <p v-if="deviceConnected && !matchingInterface" class="clock-help">{{ tr('此处选择要配置的接口；连接匹配的目标后才会应用，不会切换下载器接口。', 'This selects the interface to configure. Settings apply when a matching target connects; the probe interface is not switched.') }}</p>
    <p v-if="migration?.pending" role="status" data-testid="clock-migration">{{ tr('旧 4 MHz 配置需要迁移：请选择 2 MHz 并应用。确认前保留原设置，不会自动切换。', 'The old 4 MHz configuration needs migration: select 2 MHz and apply. The previous setting is retained until confirmed; it will not change automatically.') }}</p>
    <p v-if="matchingInterface && status?.apply_state === 'configured'" role="status">{{ tr('下载器已保存采集设置，尚未确认应用。退出 Keil 调试并停止采集后，可显式重新应用；不会自动停止或重试。', 'The probe saved the acquisition setting but has not confirmed application. After exiting Keil debugging and stopping captures, explicitly apply it again; nothing is automatically stopped or retried.') }}</p>
    <p v-if="interfaceConfig?.clock_source?.endsWith('-advertised')" class="clock-help">{{ tr('档位是请求值，并非逻辑分析仪实测频率。', 'These are requested clock settings, not logic-analyzer measurements.') }}</p>
    <p v-if="interfaceConfig?.clock_source?.endsWith('-advertised') && Number(selected) > 0 && Number(selected) < 1000000" class="clock-help">{{ tr('低频采集会延长总线占用，可能明显增加并行 Keil 调试的等待时间。', 'Low-frequency acquisition holds the bus longer and can significantly increase waiting time during concurrent Keil debugging.') }}</p>
    <p v-if="readError || message || status?.warning" class="clock-message" role="status">{{ readError || message || status?.warning }}</p>
  </div>
</template>

<style scoped>
.connection-clock { margin: 12px 0; }
.clock-row { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.clock-row label span, .clock-help, .clock-state { color: var(--muted); font-size: 12px; }
.clock-row select { width: auto; min-width: 130px; max-width: 100%; }
.clock-row .interface-select { flex: 0 0 90px; width: 90px; min-width: 90px; }
.connection-clock p { margin: 6px 0 0 110px; font-size: 12px; }
.clock-message { color: var(--warning, #e2aa55); }
@media (max-width: 640px) { .connection-clock p { margin-left: 0; } }
</style>
