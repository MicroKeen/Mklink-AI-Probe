<script setup lang="ts">
import { computed, onActivated, onBeforeUnmount, onDeactivated, ref, watch } from 'vue'
import { API_BASE } from '../lib/runtimeEndpoint'
import { tr } from '../composables/useLanguage'

interface ConfigurationField {
  id: string
  label: string
  description: string
  bit_width?: number
  current: number | string | null
  shadow: number | null
}
interface Configuration {
  kind: string
  read_supported: boolean
  reason: string
  fields: ConfigurationField[]
  read_at?: string
}
const props = defineProps<{
  partNumber: string
  model: string
  unlockBeforeDownload: boolean
  lockAfterDownload: boolean
}>()
const configuration = ref<Configuration | null>(null)
const busy = ref(false)
const error = ref('')
let revision = 0
let controller: AbortController | null = null
const plan = computed(() => [
  ...(props.unlockBeforeDownload ? [tr('解锁并擦除', 'Unlock and erase')] : []),
  tr('烧录固件', 'Program firmware'),
  ...(props.lockAfterDownload ? [tr('加锁', 'Lock')] : []),
].join(' → '))

function cancel() {
  revision++
  controller?.abort()
  controller = null
  busy.value = false
}
async function load(read = false) {
  cancel()
  const requestRevision = revision
  error.value = ''
  // Drop previous readings immediately, including when a refresh fails.
  if (read && configuration.value) {
    configuration.value = { ...configuration.value, read_at: undefined,
      fields: configuration.value.fields.map(field => ({ ...field, current: null, shadow: null })) }
  } else configuration.value = null
  if (!props.partNumber || !props.model) return
  busy.value = true
  controller = new AbortController()
  try {
    const query = new URLSearchParams({ part_number: props.partNumber, model: props.model })
    const response = await fetch(`${API_BASE}/api/device/configuration${read ? '/read' : `?${query}`}`, {
      method: read ? 'POST' : 'GET', signal: controller.signal,
      ...(read ? { headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ part_number: props.partNumber, model: props.model }) } : {}),
    })
    const body = await response.json()
    if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : body.detail?.message || `HTTP ${response.status}`)
    if (revision === requestRevision) configuration.value = body
  } catch (e) {
    if (revision === requestRevision) error.value = e instanceof Error ? e.message : String(e)
  } finally {
    if (revision === requestRevision) busy.value = false
  }
}
function display(value: number | string | null, width = 32): string {
  if (value === null) return '—'
  if (typeof value === 'number') return `0x${value.toString(16).toUpperCase().padStart(Math.ceil(width / 4), '0')}`
  if (value === 'unprotected') return tr('未保护', 'Unprotected')
  if (value === 'protected') return tr('已保护', 'Protected')
  if (value === 'permanent') return tr('永久保护', 'Permanent protection')
  return value
}
watch(() => [props.partNumber, props.model], () => void load(), { immediate: true })
onDeactivated(() => { cancel(); configuration.value = null })
onActivated(() => { if (!configuration.value && !busy.value) void load() })
onBeforeUnmount(cancel)
</script>

<template>
  <div class="configuration-panel" data-testid="device-configuration">
    <div class="configuration-heading">
      <strong>{{ tr('选项字节 / OTP 配置', 'Option Bytes / OTP') }}</strong>
      <button class="btn" data-testid="configuration-read" :disabled="busy || !configuration?.read_supported" @click="load(true)">
        {{ busy ? tr('加载中…', 'Loading…') : tr('读取配置', 'Read Configuration') }}
      </button>
    </div>
    <p v-if="!partNumber || !model">{{ tr('选择芯片和下载器型号后加载配置。', 'Select a chip and probe model to load configuration.') }}</p>
    <p v-if="error" class="configuration-error" role="alert">{{ error }}</p>
    <template v-if="configuration">
      <p>{{ configuration.reason }}</p>
      <p v-if="configuration.read_at" data-testid="configuration-timestamp">{{ tr('读取快照', 'Snapshot') }} · {{ configuration.read_at }}</p>
      <div v-if="configuration.fields.length" class="configuration-table">
        <table>
          <thead><tr><th>{{ tr('字段', 'Field') }}</th><th>{{ configuration.kind === 'otp' ? tr('熔丝值', 'Fuse') : tr('读取值', 'Read Value') }}</th><th v-if="configuration.kind === 'otp'">{{ tr('影子值', 'Shadow') }}</th><th>{{ tr('配置目标', 'Target') }}</th></tr></thead>
          <tbody><tr v-for="field in configuration.fields" :key="field.id" :data-testid="`configuration-field-${field.id}`">
            <td :title="field.description"><b>{{ field.id }}</b><small>{{ field.label }}</small><small>{{ field.description }}</small></td>
            <td>{{ display(field.current, field.bit_width) }}</td>
            <td v-if="configuration.kind === 'otp'">{{ display(field.shadow, field.bit_width) }}</td>
            <td>{{ configuration.kind === 'otp' ? tr('只读', 'Read only') : lockAfterDownload ? tr('加锁', 'Lock') : unlockBeforeDownload ? tr('解锁', 'Unlock') : tr('保持', 'Preserve') }}</td>
          </tr></tbody>
        </table>
      </div>
      <p v-if="configuration.kind === 'option_bytes' && configuration.read_supported" data-testid="configuration-plan">{{ tr('生成脚本的动作顺序：', 'Generated script sequence: ') }}{{ plan }}</p>
    </template>
    <slot />
  </div>
</template>

<style scoped>
.configuration-panel{margin-top:14px;padding-top:12px;border-top:1px solid var(--border)}
.configuration-heading{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:12px}
p{font-size:11px;line-height:1.5;color:var(--muted);margin:8px 0}
.configuration-error{color:var(--danger)}
.configuration-table{overflow-x:auto;max-height:360px;border:1px solid var(--border);border-radius:5px}
table{width:100%;border-collapse:collapse;font-size:11px;text-align:left}
th,td{padding:7px;border-bottom:1px solid var(--border-subtle);vertical-align:top}
th{background:var(--bg);position:sticky;top:0;white-space:nowrap}
td:not(:first-child){font-family:var(--font-mono);white-space:nowrap}
td b{font:11px var(--font-mono)}
td small{display:block;min-width:90px;margin-top:3px;color:var(--muted);line-height:1.4}
</style>
