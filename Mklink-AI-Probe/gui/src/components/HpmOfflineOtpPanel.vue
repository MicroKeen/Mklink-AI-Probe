<script setup lang="ts">
import { ref, watch } from 'vue'
import { tr } from '../composables/useLanguage'
import type { HpmOfflineOtp } from '../types/offlineFlash'
const emit = defineEmits<{ change: [value: HpmOfflineOtp | undefined] }>()
const enabled = ref(false), confirmed = ref(false)
const words = ref([{ word: 69, expected: '0x0', desired: '' }])
const locks = ref<number[]>([]), hard = ref('')
watch([enabled, words, locks, hard], () => { confirmed.value = false }, { deep: true, flush: 'sync' })
watch([enabled, words, locks, hard, confirmed], () => emit('change', enabled.value ? {
  words: words.value.filter(row => row.desired.trim()).map(row => ({ ...row })),
  locks: [...locks.value], expected_hard_lock: hard.value,
  confirm_irreversible: confirmed.value,
} : undefined), { deep: true })
</script>
<template>
  <section class="offline-otp" data-testid="offline-otp">
    <label><input v-model="enabled" type="checkbox" data-testid="offline-otp-enable"> {{ tr('固件下载并校验成功后配置用户 OTP（脱机执行）', 'Configure user OTP after successful programming and verification (offline)') }}</label>
    <template v-if="enabled">
      <p>{{ tr('执行顺序：检查固件能力、芯片及旧值 → 下载并逐字节校验全部固件 → 写入用户数据并回读 → 永久锁定。任一步失败即停止，不自动重试；旧下载器固件须先升级。', 'Order: check probe capability, chip and current values → program and byte-verify every image → write and read back user data → permanently lock. Stop on any failure; never retry automatically. Older probe firmware requires an upgrade.') }}</p>
      <p>{{ tr('每个 Word 为4字节。预期旧值必须符合待烧芯片；空白用户字可填0。目标值填完整结果，例如0x5增加bit1填0x7，不能清除已有的1。此处只生成脱机配方，不立即烧写。', 'Each word is 4 bytes. Expected values must match the chip; blank user words are 0. Enter the complete desired value: adding bit 1 to 0x5 gives 0x7. Set bits cannot be cleared. Editing this recipe does not program the chip.') }}</p>
      <div v-for="(row, index) in words" :key="index" class="row">
        <label>Word <select v-model="row.word" :aria-label="`Offline OTP word ${index}`"><option v-for="n in 11" :value="68+n" :key="n">{{68+n}}</option></select></label>
        <label>{{ tr('预期旧值', 'Expected value') }}<input v-model="row.expected" :aria-label="`Offline OTP expected ${index}`"></label>
        <label>{{ tr('目标值', 'Desired value') }}<input v-model="row.desired" :aria-label="`Offline OTP desired ${index}`" :placeholder="tr('留空不配置', 'Leave blank to skip')"></label>
        <button class="btn" @click="words.splice(index,1)">{{ tr('移除', 'Remove') }}</button>
      </div>
      <button class="btn" :disabled="words.length >= 11" @click="words.push({word:69,expected:'0x0',desired:''})">{{ tr('添加用户字', 'Add user word') }}</button>
      <p>{{ tr('永久锁最后执行，整个组不能再烧写。仅在组内数据全部确定后选择：', 'Permanent locks run last and prevent any further programming of the entire group. Select only after all data in that group is final:') }}</p>
      <label v-for="g in [18,19]" :key="g"><input v-model="locks" type="checkbox" :value="g"> Word {{g*4}}–{{g*4+3}} </label>
      <label v-if="locks.length" class="hard">{{ tr('预期 HARD_LOCK（从待烧芯片读取，不要猜测）', 'Expected HARD_LOCK (read from the chip; do not guess)') }}<input v-model="hard" aria-label="Offline OTP hard lock" placeholder="0x…"></label>
      <p>{{ tr('该配方会应用于每一轮烧录的芯片；中途失败后必须先回读。已部分写入或已锁的芯片可能不再符合旧值条件。', 'The recipe applies to every chip in the run. Read back after any failure: partially programmed or locked chips may no longer match the expected values.') }}</p>
      <label><input v-model="confirmed" type="checkbox" data-testid="offline-otp-confirm"> {{ tr('确认部署并触发脚本后将永久写入以上配置', 'I confirm these settings will be permanently programmed when the deployed script runs') }}</label>
    </template>
  </section>
</template>
<style scoped>
.offline-otp{margin-top:12px;padding:12px;border:1px solid var(--border);border-radius:6px;font-size:12px}p{line-height:1.6;color:var(--muted)}.row{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0;align-items:end}.row label,.hard{display:flex;flex-direction:column;gap:4px}.row input{width:100px}input:not([type=checkbox]),select{background:var(--surface);color:var(--fg);padding:5px;border:1px solid var(--border);border-radius:4px}.hard{margin-top:8px}
</style>
