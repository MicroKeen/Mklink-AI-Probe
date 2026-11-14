<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { FirmwareUpdateNotice } from '../types/mklink'
import { tr } from '../composables/useLanguage'
import ConfirmationDialog from './ConfirmationDialog.vue'

const props = defineProps<{ notice?: FirmwareUpdateNotice | null; onFirmwarePage?: boolean; deferred?: boolean }>()
const emit = defineEmits<{ openFirmware: [] }>()
const dismissed = new Set<string>()
const visible = ref(false)
const key = computed(() => {
  const n = props.notice
  const actionable = n?.status === 'unrecognized'
    || (n?.status === 'available' && n.current_version && n.latest_version)
  return actionable && n?.probe_id
    ? JSON.stringify([n.probe_id, n.status, n.family, n.model, n.current_version, n.latest_version]) : ''
})
function remember(value: string) {
  dismissed.add(value)
  try { sessionStorage.setItem('mklink.firmware-notice.' + value, '1') } catch { /* Private storage may be unavailable. */ }
}
watch([key, () => props.onFirmwarePage, () => props.deferred], ([value, onPage, deferred]) => {
  visible.value = false
  if (!value || deferred) return
  if (onPage) { remember(value); return }
  let seen = dismissed.has(value)
  try { seen ||= sessionStorage.getItem('mklink.firmware-notice.' + value) === '1' } catch { /* Use in-memory deduplication. */ }
  visible.value = !seen
}, { immediate: true })
function answer(accepted: boolean) {
  if (!key.value) return
  remember(key.value)
  visible.value = false
  if (accepted) emit('openFirmware')
}
const message = computed(() => {
  const n = props.notice
  if (n?.status === 'unrecognized') return tr(
    '当前下载器固件信息无法识别，建议升级固件。\n\n是否前往固件升级页面？请按下载器型号选择固件。进入页面不会停止采集；开始升级前请先停止采集。',
    'The installed probe firmware could not be identified. A firmware upgrade is recommended.\n\nOpen Firmware Update? Choose firmware matching your probe model. Opening the page keeps acquisition running. Stop acquisition before starting the update.',
  )
  const model = `${n?.family === 'hpmlink' ? 'HPMLink' : 'MicroLink'} ${n?.model || ''}`
  return tr(
    `${model} 有可用的新固件。\n当前版本：${n?.current_version}\n云端版本：${n?.latest_version}\n\n是否前往固件升级页面？进入页面不会停止采集；开始升级前请先停止采集。`,
    `New firmware is available for ${model}.\nInstalled: ${n?.current_version}\nCloud: ${n?.latest_version}\n\nOpen Firmware Update? Opening the page keeps acquisition running. Stop acquisition before starting the update.`,
  )
})
</script>

<template>
  <ConfirmationDialog v-if="visible" :message="message" :danger="false"
    :title="notice?.status === 'unrecognized' ? tr('建议升级固件', 'Probe Firmware Upgrade Recommended') : tr('发现新固件', 'New Probe Firmware')"
    :accept-label="tr('前往升级', 'Open Firmware Update')" :cancel-label="tr('稍后', 'Later')"
    @answer="answer" />
</template>
