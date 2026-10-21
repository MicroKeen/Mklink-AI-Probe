<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import HpmOtpTable from './HpmOtpTable.vue'
import type { HpmIspOtpChange, HpmIspOtpPlan, HpmIspOtpSnapshot } from '../types/hpmOtp'
import { tr } from '../composables/useLanguage'
const props = defineProps<{ snapshot: HpmIspOtpSnapshot | null; plan: HpmIspOtpPlan | null; result: string; busy: boolean; disabled: boolean; error: string }>()
const emit = defineEmits<{ read: []; prepare: [change: HpmIspOtpChange]; program: [planId: string]; invalidate: [] }>()
const hex = (value: number) => `0x${value.toString(16).toUpperCase().padStart(8, '0')}`
const selected = ref(69), desired = ref(''), confirmed = ref(false)
const row = computed(() => props.snapshot?.words.find(item => item.word === selected.value))
const writablePlan = computed(() => props.plan?.qualified === true && props.plan.write_supported === true && !!props.plan.plan_id)
const planReason = computed(() => {
  const reason = props.plan?.reason
  if (reason === 'expected_mismatch') return tr('当前值与读取快照不一致，请重新读取。', 'The current value differs from the snapshot. Read again.')
  if (reason === 'bit_clear_requested') return tr('目标值不能清除已有的 1。', 'The desired value cannot clear existing 1 bits.')
  if (reason === 'read_semantics_and_locks_unknown') return tr('当前 ROM 尚不能确认熔丝值及写保护状态，暂不支持 UART OTP 写入。', 'Fuse values and write protection cannot yet be confirmed for this ROM. UART OTP programming is unavailable.')
  return reason || tr('下载器未确认可以写入，请重新检查。', 'The probe has not confirmed this change is writable. Check again.')
})
watch([selected, desired], () => { confirmed.value = false; emit('invalidate') }, { flush: 'sync' })
watch(() => props.plan, () => { confirmed.value = false })
watch(() => props.snapshot, () => { confirmed.value = false; desired.value = '' })
function prepare() {
  if (props.busy || props.disabled || !row.value || row.value.locked === true || !desired.value.trim()) return
  emit('prepare', { word: selected.value, expected: row.value.current, desired: desired.value.trim() })
}
function program() {
  if (props.busy || props.disabled || !confirmed.value || !writablePlan.value || !props.plan?.plan_id) return
  confirmed.value = false
  emit('program', props.plan.plan_id)
}
</script>

<template>
  <details class="isp-otp" data-testid="hpm-isp-otp">
    <summary>{{ tr('HPM5301 用户 OTP', 'HPM5301 User OTP') }}</summary>
    <p>{{ tr('目标进入 ROM ISP 后读取，无需连接 JTAG 或添加固件。', 'Read with the target in ROM ISP; no JTAG connection or firmware file is needed.') }}</p>
    <button class="btn" data-testid="isp-otp-read" :disabled="busy || disabled" @click="$emit('read')">{{ busy ? tr('处理中…', 'Working…') : tr('读取 OTP', 'Read OTP') }}</button>
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <p v-if="result" role="status">{{ result }}</p>
    <template v-if="snapshot">
      <p class="identity">CHIP_ID {{ hex(snapshot.chip_id) }} · HARD_LOCK {{ hex(snapshot.hard_lock) }}</p>
      <p>{{ tr('读取快照', 'Snapshot') }} · {{ snapshot.read_at }}</p>
      <HpmOtpTable :rows="snapshot.words" rom-read />
      <p>{{ tr('— / 未知表示本次未取得该项状态，不代表零值或未锁定。换板后请重新读取。', '— / Unknown means the state was not obtained, not zero or unlocked. Read again after changing boards.') }}</p>
      <div class="inputs">
        <label>Word <select v-model="selected" :disabled="busy || disabled" aria-label="UART OTP word"><option v-for="n in 11" :key="n" :value="68+n">{{68+n}}</option></select></label>
        <label>{{ tr('目标值', 'Desired value') }} <input v-model="desired" :disabled="busy || disabled" aria-label="UART OTP desired value" placeholder="0x00000000"></label>
        <button class="btn" data-testid="isp-otp-plan" :disabled="busy || disabled || !row || row.locked === true || !desired.trim()" @click="prepare">{{ tr('检查并预览', 'Check and Preview') }}</button>
      </div>
      <p>{{ tr('仅配置用户 Word 69–79。目标值填写完整结果，已有的 1 不能改回 0。预览不会写入；芯片和锁定状态须通过下载器检查。', 'Only user words 69–79 can be configured. Enter the complete final value; existing 1 bits cannot be cleared. Preview does not program OTP; the probe must check the chip and locks.') }}</p>
    </template>
    <template v-if="plan">
      <p data-testid="isp-otp-diff">Word {{ plan.word }}: {{ hex(plan.expected) }} → {{ hex(plan.desired) }} · {{ tr('新增位', 'New bits') }} {{ hex(plan.delta) }}</p>
      <p v-if="plan.before !== null">{{ tr('预检读取值', 'Preflight read value') }}: {{ hex(plan.before) }}</p>
      <p v-if="!writablePlan" role="status" data-testid="isp-otp-unavailable">{{ planReason }}</p>
      <template v-else>
        <label class="confirmation"><input v-model="confirmed" type="checkbox" data-testid="isp-otp-confirm" :disabled="busy || disabled">{{ tr('确认永久写入以上新增位，无法擦除', 'Confirm permanently burning these new bits; they cannot be erased') }}</label>
        <button class="btn" data-testid="isp-otp-program" :disabled="busy || disabled || !confirmed" @click="program">{{ tr('写入并校验', 'Program and Verify') }}</button>
      </template>
    </template>
  </details>
</template>

<style scoped>
.isp-otp{margin-top:12px;padding:10px;border:1px solid var(--border);border-radius:5px;font-size:12px}summary{cursor:pointer}p{color:var(--muted);line-height:1.6;overflow-wrap:anywhere}.identity{font-family:var(--font-mono)}.error{color:var(--danger)}
.inputs{display:flex;gap:8px;flex-wrap:wrap;align-items:end}.inputs label{display:flex;flex-direction:column;gap:4px}.inputs input,.inputs select{padding:6px;max-width:160px;border:1px solid var(--border);border-radius:4px;background:var(--surface);color:var(--fg)}.confirmation{display:flex;align-items:start;gap:6px;margin:10px 0}
</style>
