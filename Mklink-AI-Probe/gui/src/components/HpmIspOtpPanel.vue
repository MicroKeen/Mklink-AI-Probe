<script setup lang="ts">
import HpmOtpTable from './HpmOtpTable.vue'
import type { HpmIspOtpSnapshot } from '../types/hpmOtp'
import { tr } from '../composables/useLanguage'
defineProps<{ snapshot: HpmIspOtpSnapshot | null; busy: boolean; disabled: boolean; error: string }>()
defineEmits<{ read: [] }>()
const hex = (value: number) => `0x${value.toString(16).toUpperCase().padStart(8, '0')}`
</script>

<template>
  <details class="isp-otp" data-testid="hpm-isp-otp">
    <summary>{{ tr('HPM5301 用户 OTP（只读）', 'HPM5301 User OTP (read only)') }}</summary>
    <p>{{ tr('目标进入 ROM ISP 后读取，无需连接 JTAG 或添加固件。', 'Read with the target in ROM ISP; no JTAG connection or firmware file is needed.') }}</p>
    <button class="btn" data-testid="isp-otp-read" :disabled="busy || disabled" @click="$emit('read')">{{ busy ? tr('读取中…', 'Reading…') : tr('读取 OTP', 'Read OTP') }}</button>
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <template v-if="snapshot">
      <p class="identity">CHIP_ID {{ hex(snapshot.chip_id) }} · HARD_LOCK {{ hex(snapshot.hard_lock) }}</p>
      <p>{{ tr('读取快照', 'Snapshot') }} · {{ snapshot.read_at }}</p>
      <HpmOtpTable :rows="snapshot.words" rom-read />
      <p>{{ tr('— / 未知表示本次未取得该项状态，不代表零值或未锁定。换板后请重新读取。', '— / Unknown means the state was not obtained, not zero or unlocked. Read again after changing boards.') }}</p>
    </template>
  </details>
</template>

<style scoped>
.isp-otp{margin-top:12px;padding:10px;border:1px solid var(--border);border-radius:5px;font-size:12px}summary{cursor:pointer}p{color:var(--muted);line-height:1.6;overflow-wrap:anywhere}.identity{font-family:var(--font-mono)}.error{color:var(--danger)}
</style>
