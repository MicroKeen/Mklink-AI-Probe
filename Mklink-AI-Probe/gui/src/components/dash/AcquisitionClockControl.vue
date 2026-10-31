<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { API_BASE } from '../../lib/runtimeEndpoint'
import { tr } from '../../composables/useLanguage'

interface ClockStatus {
  connected: boolean
  device_generation?: number
  interface: string
  clocks_hz: number[]
  clock_source: string
  requested_hz: number | null
  configured_hz: number | null
  applied_hz: number | null
  apply_state: 'unknown' | 'acknowledged' | 'configured' | 'applied'
  migration?: { from_hz: number; to_hz: number; pending: boolean } | null
  warning?: string | null
}
const props = defineProps<{ deviceConnected: boolean; deviceGeneration?: number }>()
const status = ref<ClockStatus | null>(null)
const selected = ref('')
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
const clocks = computed(() => status.value?.clocks_hz || [])
const legacyChoice = computed(() => selected.value && !clocks.value.includes(Number(selected.value)))
const canApply = computed(() => props.deviceConnected && status.value?.connected && !busy.value
  && clocks.value.includes(Number(selected.value)))
const effectiveLabel = computed(() => {
  const s = status.value
  if (!props.deviceConnected || !s?.connected) return tr('未连接', 'Disconnected')
  if (s.apply_state === 'applied' && s.applied_hz) return tr('已应用：', 'Applied: ') + frequency(s.applied_hz)
  if (s.apply_state === 'configured' && s.configured_hz) return tr('已保存，待应用：', 'Saved, pending application: ') + frequency(s.configured_hz)
  if (s.configured_hz) return tr('下载器已确认设置：', 'Probe acknowledged setting: ') + frequency(s.configured_hz)
  return tr('下载器设置未确认', 'Probe setting unconfirmed')
})

async function refresh() {
  const current = revision
  try {
    const response = await fetch(`${API_BASE}/api/device/debug-speed`)
    if (!response.ok) throw new Error(tr('读取采集时钟失败', 'Failed to read acquisition clock'))
    const payload: ClockStatus = await response.json()
    if (disposed || current !== revision) return
    if (!Array.isArray(payload.clocks_hz)) throw new Error(tr('后台尚不支持统一采集时钟', 'The backend does not support the shared clock control'))
    status.value = payload
    readError.value = ''
    if (!dirty.value && !busy.value) {
      const value = payload.configured_hz ?? payload.requested_hz
      selected.value = value ? String(value) : ''
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
  const migration = status.value?.migration
  try {
    const response = await fetch(`${API_BASE}/api/device/debug-speed`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json',
        ...(status.value?.device_generation !== undefined
          ? { 'X-MKLink-Device-Generation': String(status.value.device_generation) } : {}) },
      body: JSON.stringify({ clock_hz: requested, save: true }),
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
    if (payload.configured_hz !== requested || !['configured', 'applied', 'acknowledged'].includes(payload.apply_state)) {
      throw new Error(tr('下载器未确认所选时钟，请核对当前状态。', 'The probe did not confirm the selected clock; check its current status.'))
    }
    dirty.value = false
    if (migration?.from_hz === 4_000_000 && requested === migration.to_hz) {
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

watch(() => [props.deviceConnected, props.deviceGeneration], () => {
  revision++
  status.value = null
  selected.value = ''
  dirty.value = false
  busy.value = false
  message.value = ''
  readError.value = ''
  void refresh()
})
onMounted(poll)
onUnmounted(() => { disposed = true; revision++; clearTimeout(timer) })
</script>

<template>
  <div class="acquisition-clock" data-testid="acquisition-clock">
    <div class="clock-row">
      <label for="acquisition-clock-hz">{{ tr('采集时钟', 'Acquisition clock') }} <span>{{ status?.interface || '' }}</span></label>
      <select id="acquisition-clock-hz" v-model="selected" class="form-select" :disabled="busy || !deviceConnected || !status" @change="dirty = true">
        <option value="" disabled>{{ tr('选择时钟', 'Select clock') }}</option>
        <option v-if="legacyChoice" :value="selected" disabled>{{ frequency(Number(selected)) }} · {{ tr('旧配置，请重新选择', 'Previous setting; select a supported clock') }}</option>
        <option v-for="hz in clocks" :key="hz" :value="String(hz)">{{ frequency(hz) }}</option>
      </select>
      <button class="btn btn-sm" data-testid="apply-acquisition-clock" :disabled="!canApply" @click="apply">{{ busy ? tr('应用中…', 'Applying…') : tr('应用并保存', 'Apply and save') }}</button>
      <span class="clock-state" data-testid="acquisition-clock-state">{{ effectiveLabel }}</span>
    </div>
    <p class="clock-help">{{ tr('RTT、RTOS Trace、SuperWatch 和普通内存访问共用此时钟；Keil 调试时钟独立。', 'RTT, RTOS Trace, SuperWatch and ordinary memory access share this clock. Keil keeps its own debug clock.') }}</p>
    <p v-if="status?.migration?.pending" role="status" data-testid="clock-migration">{{ tr('旧 4 MHz 配置需要迁移：请选择 2 MHz 并应用。确认前保留原设置，不会自动切换。', 'The old 4 MHz configuration needs migration: select 2 MHz and apply. The previous setting is retained until confirmed; it will not change automatically.') }}</p>
    <p v-if="status?.apply_state === 'configured'" role="status">{{ tr('下载器已保存采集设置，尚未确认应用。退出 Keil 调试并停止采集后，可显式重新应用；不会自动停止或重试。', 'The probe saved the acquisition setting but has not confirmed application. After exiting Keil debugging and stopping captures, explicitly apply it again; nothing is automatically stopped or retried.') }}</p>
    <p v-if="status?.clock_source === 'v3-advertised'" class="clock-help">{{ tr('档位是请求值，并非逻辑分析仪实测频率。', 'These are requested clock settings, not logic-analyzer measurements.') }}</p>
    <p v-if="status?.clock_source === 'v3-advertised' && Number(selected) > 0 && Number(selected) < 1000000" class="clock-help">{{ tr('低频采集会延长总线占用，可能明显增加并行 Keil 调试的等待时间。', 'Low-frequency acquisition holds the bus longer and can significantly increase waiting time during concurrent Keil debugging.') }}</p>
    <p v-if="readError || message || status?.warning" class="clock-message" role="status">{{ readError || message || status?.warning }}</p>
  </div>
</template>

<style scoped>
.acquisition-clock { padding: 10px 16px; border-bottom: 1px solid var(--border); }
.clock-row { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.clock-row label { font-weight: 600; }
.clock-row label span, .clock-help, .clock-state { color: var(--muted); font-size: 12px; }
.clock-row select { width: auto; min-width: 130px; max-width: 100%; }
.acquisition-clock p { margin: 6px 0 0; font-size: 12px; }
.clock-message { color: var(--warning, #e2aa55); }
</style>
