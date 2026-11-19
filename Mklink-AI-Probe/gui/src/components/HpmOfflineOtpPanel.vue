<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { tr } from '../composables/useLanguage'
import { useMklinkApi } from '../composables/useMklinkApi'
import { API_BASE } from '../lib/runtimeEndpoint'
import { customOtpEntries, otpCsv, otpHex as hex, parseOtpCsv, type OtpEntry } from '../lib/otpConfiguration'
import { saveTextFile } from '../lib/downloadTextFile'
import HpmOtpGrid from './HpmOtpGrid.vue'
import HpmUserOtpPanel from './HpmUserOtpPanel.vue'
import { hpmJtagOtpProfile, otpFieldValue } from '../lib/hpmOtpProfiles'
import DeviceConfigurationPanel from './DeviceConfigurationPanel.vue'
import type { HpmOfflineOtp } from '../types/offlineFlash'

const props = withDefaults(defineProps<{ partNumber?: string; probeId?: string; active?: boolean; disabled?: boolean }>(), { partNumber: 'HPM5301' })
const emit = defineEmits<{ change: [value: HpmOfflineOtp | undefined, pending: boolean] }>()
const { deviceStatus } = useMklinkApi()
interface Word { word: number; current: number | null; shadow: number | null; locked: boolean | null }
interface Draft extends OtpEntry { expected: string }
const view = ref<'read' | 'write'>('read'), columns = ref(4), selected = ref(69)
const rows = ref<Word[]>([]), hardLock = ref<number | null>(null), readAt = ref('')
const pending = ref<Draft[]>([]), locks = ref<number[]>([]), expectedHardLock = ref(''), confirmed = ref(false)
const editing = ref(false), start = ref(69), count = ref(1), values = ref('0x00000000')
const busy = ref(false), importing = ref(false), saving = ref(false), error = ref(''), fileInput = ref<HTMLInputElement>()
let revision = 0, disposed = false
const unavailable = computed(() => props.disabled || busy.value || importing.value)
const readAllowed = computed(() => deviceStatus.value.connected && (!props.probeId || props.probeId === deviceStatus.value.probe_id))
const profile = computed(() => hpmJtagOtpProfile(props.partNumber))
const legacyWrite = computed(() => ['HPM5301', 'HPM5301XEGX'].includes(props.partNumber.toUpperCase()))
const genericWrite = ref(false)
const canWrite = computed(() => legacyWrite.value || genericWrite.value)
const readEntries = computed(() => rows.value.map(row => ({ ...row, value: row.current })))
const selectedEntry = computed(() => rows.value.find(item => item.word === selected.value))
const selectedFields = computed(() => profile.value?.words[selected.value]?.fields || [])
function expectedHex(word: number) {
  const current = rows.value[word]?.current
  return current == null ? '' : hex(current)
}
function u32(text: string): number | null {
  if (!/^(?:0x[\da-f]{1,8}|\d+)$/i.test(text.trim())) return null
  const value = Number(text.trim())
  return Number.isSafeInteger(value) && value >= 0 && value <= 0xffffffff ? value : null
}
const hasDraft = computed(() => pending.value.length > 0 || locks.value.length > 0 || editing.value)
const valid = computed(() => canWrite.value && !editing.value && (pending.value.length > 0 || locks.value.length > 0)
  && pending.value.every(item => {
    const expected = u32(item.expected), current = rows.value.find(row => row.word === item.word)
    return expected !== null && (!genericWrite.value || expected !== item.value) && ((expected & item.value) >>> 0) === expected
      && (!current || (current.current === expected && current.locked === false))
  }) && (!locks.value.length || (u32(expectedHardLock.value) !== null
    && (!rows.value.length || u32(expectedHardLock.value) === hardLock.value))))
watch([pending, locks, expectedHardLock, editing, rows, hardLock], () => { confirmed.value = false }, { deep: true, flush: 'sync' })
watch([pending, locks, expectedHardLock, confirmed, valid, hasDraft], () => emit('change', valid.value && confirmed.value ? {
  words: pending.value.map(item => ({ word: item.word, expected: hex(u32(item.expected)!), desired: hex(item.value) })),
  locks: [...locks.value], expected_hard_lock: locks.value.length ? hex(u32(expectedHardLock.value)!) : '', confirm_irreversible: true,
} : undefined, hasDraft.value), { deep: true })
function clearSnapshot() { rows.value = []; hardLock.value = null; readAt.value = ''; confirmed.value = false; genericWrite.value = false }
watch([() => props.partNumber, () => props.probeId, () => deviceStatus.value.probe_id, () => deviceStatus.value.device_generation, () => deviceStatus.value.connected], () => {
  revision++; clearSnapshot(); pending.value = []; locks.value = []; expectedHardLock.value = ''; editing.value = false; error.value = ''; view.value = 'read'
})
onBeforeUnmount(() => { disposed = true; revision++ })
async function refresh() {
  if (unavailable.value || !readAllowed.value) return
  const current = ++revision
  clearSnapshot(); busy.value = true; error.value = ''
  try {
    const probe = props.probeId || deviceStatus.value.probe_id
    const response = await fetch(`${API_BASE}/api/device/configuration/read`, {
      method: 'POST', headers: { 'Content-Type': 'application/json',
        ...(probe ? { 'X-MKLink-Probe': probe } : {}),
        ...(deviceStatus.value.device_generation !== undefined ? { 'X-MKLink-Device-Generation': String(deviceStatus.value.device_generation) } : {}) },
      body: JSON.stringify({ part_number: props.partNumber, model: 'V4', otp_words: true }),
    })
    const body = await response.json()
    if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : body.detail?.message || `HTTP ${response.status}`)
    if (disposed || revision !== current) return
    if (body.source !== 'jtag_otp' || !Array.isArray(body.words) || body.words.length !== 128 ||
        !body.words.every((row: Word, i: number) => row.word === i)) {
      throw new Error(tr('共享后台未返回完整 JTAG OTP 快照，请检查上位机版本。', 'Incomplete JTAG OTP snapshot. Check the host version.'))
    }
    rows.value = body.words; hardLock.value = body.hard_lock; readAt.value = body.read_at
    genericWrite.value = body.jtag_otp_write_api === 'rom_v1'
    pending.value = pending.value.map(item => ({ ...item, expected: expectedHex(item.word) }))
    expectedHardLock.value = body.hard_lock == null ? '' : hex(body.hard_lock)
  } catch (cause) { if (!disposed && revision === current) error.value = cause instanceof Error ? cause.message : String(cause) }
  finally { busy.value = false }
}
function merge(entries: OtpEntry[]) {
  pending.value = [...pending.value.filter(item => !entries.some(entry => entry.word === item.word)), ...entries.map(item => ({
    ...item, expected: pending.value.find(row => row.word === item.word)?.expected
      ?? expectedHex(item.word),
  }))].sort((a, b) => a.word - b.word)
}
function addDialog(word = 69) {
  if (unavailable.value) return
  start.value = word; count.value = 1
  values.value = hex(pending.value.find(item => item.word === word)?.value ?? rows.value.find(item => item.word === word)?.current ?? 0)
  editing.value = true; error.value = ''
}
function addEntries() {
  if (unavailable.value) return
  try { merge(customOtpEntries(start.value, count.value, values.value)); selected.value = start.value; editing.value = false; error.value = '' }
  catch (cause) { error.value = tr('请检查 Word 69–79 范围、数量和 8 位十六进制值：', 'Check words 69–79, the count and 8-digit hexadecimal values: ') + String(cause) }
}
async function importFile(event: Event) {
  const input = event.target as HTMLInputElement, file = input.files?.[0]; input.value = ''
  if (!file || unavailable.value) return
  const current = revision; importing.value = true; error.value = ''; confirmed.value = false
  try {
    if (file.size > 65536) throw new Error(tr('文件超过 64 KB', 'File exceeds 64 KB'))
    const text = await file.text()
    if (disposed || current !== revision) return
    const entries = parseOtpCsv(text)
    pending.value = []; merge(entries); editing.value = false
  } catch (cause) { if (!disposed && current === revision) error.value = tr('导入失败：', 'Import failed: ') + String(cause) }
  finally { importing.value = false }
}
async function exportFile() {
  if (saving.value) return
  saving.value = true; error.value = ''
  try { await saveTextFile(`${props.partNumber}-JTAG-OTP-${view.value}.csv`, otpCsv(view.value === 'read' ? rows.value.flatMap(row => row.current === null ? [] : [{ word: row.word, value: row.current }]) : pending.value)) }
  catch (cause) { error.value = String(cause) }
  finally { saving.value = false }
}
</script>

<template>
  <section class="otp-workspace" data-testid="offline-otp" :aria-busy="busy">
    <header><h2>{{ canWrite ? tr('OTP 读写', 'OTP Read / Write') : tr('OTP 读取', 'Read OTP') }}</h2><small>{{ tr('所选型号', 'Selected target') }} {{ partNumber }} · JTAG · Word 0–127</small></header>
    <div class="toolbar">
      <div class="actions" role="group" :aria-label="tr('OTP 视图', 'OTP view')">
        <button class="btn" :aria-pressed="view === 'read'" data-testid="offline-otp-read-view" @click="view = 'read'">{{ tr('读视图', 'Read view') }}</button>
        <button v-if="canWrite" class="btn" :aria-pressed="view === 'write'" data-testid="offline-otp-write-view" @click="view = 'write'">{{ tr('写视图', 'Write view') }} <span v-if="pending.length">{{ pending.length }}</span></button>
      </div>
      <div class="actions"><button v-if="view === 'write'" class="btn" :disabled="unavailable" @click="fileInput?.click()">{{ tr('导入', 'Import') }}</button><button class="btn" :disabled="saving || !(view === 'read' ? rows.length : pending.length)" @click="exportFile">{{ tr('导出', 'Export') }}</button><button class="btn" :disabled="unavailable || !readAllowed" data-testid="offline-otp-read" @click="refresh">{{ busy ? tr('读取中…', 'Reading…') : tr('刷新', 'Refresh') }}</button></div>
    </div>
    <div class="workspace">
      <div class="table-heading"><h3>OTP {{ view === 'read' ? 'Readable' : 'Writable' }} Words {{ tr('表', 'Table') }}</h3><label>{{ tr('列数', 'Columns') }} <select v-model.number="columns" aria-label="JTAG OTP columns"><option :value="4">4</option><option :value="8">8</option></select></label></div>
      <template v-if="view === 'read'">
        <p v-if="!readAllowed" class="hint">{{ tr('请先在配置页连接所选下载器，再刷新 OTP。', 'Connect the selected probe in Configuration before refreshing OTP.') }}</p>
        <p v-else-if="!rows.length && !error" class="hint">{{ busy ? tr('正在读取 OTP…', 'Reading OTP…') : tr('点击刷新以读取所选芯片的 OTP。', 'Refresh to read OTP from the selected target.') }}</p>
        <HpmOtpGrid v-if="rows.length" :entries="readEntries" :columns="columns" :selected="selected" :definitions="profile?.words" @select="selected = $event" />
        <div v-if="selectedEntry" class="word-detail">Word {{ selected }} · {{ selectedEntry.current === null ? '—' : hex(selectedEntry.current) }}
          <template v-if="selectedEntry.current !== null"> · {{ selectedEntry.current.toString(2).padStart(32, '0') }}
            <div v-for="field in selectedFields" :key="field.name">{{ field.name }}: 0x{{ otpFieldValue(selectedEntry.current, field) }}</div>
          </template>
          <div>{{ tr('影子值', 'Shadow') }} {{ selectedEntry.shadow === null ? '—' : hex(selectedEntry.shadow) }} · {{ tr('写保护', 'Write protection') }} {{ selectedEntry.locked === null ? tr('未知', 'Unknown') : selectedEntry.locked ? tr('是', 'Yes') : tr('否', 'No') }}</div>
        </div>
        <details v-if="legacyWrite && active !== false && readAllowed" class="system-fields"><summary>{{ tr('系统字段（只读）', 'System fields (read-only)') }}</summary><DeviceConfigurationPanel expanded hide-user-otp :part-number="partNumber" model="V4" :unlock-before-download="false" :lock-after-download="false" /></details>
      </template>
      <template v-else>
        <details v-if="genericWrite && readAllowed && active !== false" class="system-fields"><summary>{{ tr('直接写入当前芯片', 'Program connected target') }}</summary><HpmUserOtpPanel :part-number="partNumber" model="V4" generic :probe-id="probeId || deviceStatus.probe_id" :generation="deviceStatus.device_generation" /></details>
        <p v-if="genericWrite" class="hint">{{ tr('写入需要下载器支持 JTAG OTP ROM v1，目标为稳定的 3.3 V 供电。', 'Programming requires probe JTAG OTP ROM v1 and a stable 3.3 V target supply.') }}</p>
        <div class="actions edit-actions"><button class="btn" :disabled="unavailable" data-testid="offline-otp-add" @click="addDialog()">{{ tr('添加 Words', 'Add Words') }}</button><button class="btn" :disabled="unavailable || !hasDraft" data-testid="offline-otp-clear" @click="pending = []; locks = []; editing = false">{{ tr('移除所有', 'Remove all') }}</button><span>{{ tr('点击字可编辑', 'Click a word to edit') }}</span></div>
        <HpmOtpGrid v-if="pending.length" :entries="pending" :columns="columns" :selected="selected" :disabled="unavailable" @select="selected = $event; addDialog($event)" />
        <p v-else-if="!editing" class="empty">{{ tr('添加 Words 或导入 CSV / TXT 配置。', 'Add Words or import a CSV / TXT configuration.') }}</p>
        <form v-if="editing" class="editor" @submit.prevent="addEntries">
          <h4>{{ tr('添加 OTP 字 · 自定义', 'Add OTP Words · Custom') }}</h4>
          <div class="editor-fields"><label>{{ tr('起始地址（Word）', 'Start address (Word)') }}<input v-model.number="start" type="number" min="69" max="79" :disabled="unavailable" aria-label="OTP start word"></label><label>{{ tr('Word 个数', 'Word count') }}<input v-model.number="count" type="number" min="1" max="11" :disabled="unavailable" aria-label="OTP word count"></label></div>
          <label>{{ tr('Word 列表（8 位十六进制数，用逗号分隔）', 'Word list (8-digit hexadecimal values, comma-separated)') }}<textarea v-model="values" rows="3" :disabled="unavailable" aria-label="OTP word values" /></label>
          <div class="actions"><button class="btn" type="button" :disabled="unavailable" @click="editing = false">{{ tr('取消', 'Cancel') }}</button><button class="btn" type="submit" :disabled="unavailable" data-testid="offline-otp-add-confirm">{{ tr('确定', 'OK') }}</button></div>
        </form>
        <p class="hint">{{ tr('仅开放用户 Word 69–79。填写写入后的完整值，已有的 1 不能改回 0。此处只配置脱机配方，不立即写入芯片。', 'Only user words 69–79 are available. Enter complete final values; existing 1 bits cannot be cleared. This configures an offline recipe without programming the chip immediately.') }}</p>
        <section class="preview">
          <h4>{{ tr('随镜像部署的 OTP 配置', 'OTP configuration deployed with images') }}</h4>
          <table v-if="pending.length"><thead><tr><th>Word</th><th>{{ tr('预期旧值', 'Expected value') }}</th><th>{{ tr('目标值', 'Desired value') }}</th><th /></tr></thead><tbody><tr v-for="item in pending" :key="item.word"><td>{{ item.word }}</td><td><input v-model="item.expected" :disabled="unavailable" :aria-label="`OTP expected ${item.word}`" :placeholder="tr('读取或手动填写', 'Read or enter explicitly')"></td><td>{{ hex(item.value) }}</td><td><button class="btn" :disabled="unavailable" :aria-label="`Remove Word ${item.word}`" @click="pending = pending.filter(row => row.word !== item.word)">{{ tr('移除', 'Remove') }}</button></td></tr></tbody></table>
          <details v-if="legacyWrite"><summary>{{ tr('永久写保护', 'Permanent write protection') }}</summary><p>{{ tr('锁定最后执行，之后整个组无法再次写入。请先确定组内所有数据。', 'Locks run last and prevent further programming of the entire group. Finalize all data in the group first.') }}</p><label v-for="group in [18, 19]" :key="group" class="confirmation"><input v-model="locks" type="checkbox" :value="group" :disabled="unavailable">Word {{ group * 4 }}–{{ group * 4 + 3 }}</label><label v-if="locks.length">{{ tr('预期 HARD_LOCK（从待烧芯片读取，不要猜测）', 'Expected HARD_LOCK (read from the chip; do not guess)') }}<input v-model="expectedHardLock" :disabled="unavailable" aria-label="Offline OTP hard lock"></label></details>
          <p>{{ tr('先检查芯片和旧值，再下载并逐字节校验全部固件，最后写入用户数据、回读并永久锁定。失败即停止；旧下载器固件须先升级。', 'Check the chip and expected values, then program and byte-verify every image, write and read back user data, and apply permanent locks last. Stop on failure. Older probe firmware requires an upgrade.') }}</p>
          <p v-if="hasDraft && !valid" role="status">{{ tr('请完成编辑，检查预期旧值、目标值和保护锁。', 'Finish editing and check expected values, desired values and locks.') }}</p>
          <label class="confirmation"><input v-model="confirmed" type="checkbox" :disabled="unavailable || !valid" data-testid="offline-otp-confirm">{{ tr('确认部署并触发后永久写入以上配置', 'Confirm permanent programming of this configuration when deployed and triggered') }}</label>
        </section>
      </template>
    </div>
    <footer><p v-if="error" role="alert" class="error">{{ error }}</p><p v-if="readAt" class="identity">HARD_LOCK {{ hardLock === null ? '—' : hex(hardLock) }} · {{ readAt }}</p><small>{{ tr('— 表示尚未读取或该字禁止访问。', '— indicates an unread or access-disabled word.') }}
      <template v-if="view === 'write'">{{ tr('配方应用于每一轮芯片；失败或换板后请回读确认。', 'The recipe applies to every chip in the run. Read back after failure or changing boards.') }}</template></small></footer>
    <input ref="fileInput" type="file" accept=".csv,.txt" class="file-input" aria-label="OTP CSV file" @change="importFile">
  </section>
</template>

<style scoped>
.otp-workspace{border:1px solid var(--border);border-radius:6px;background:var(--surface);overflow:hidden;color:var(--fg);font-size:12px}header{padding:20px 22px 14px}h2{font-size:18px;margin:0 0 6px}h3{font-size:14px;margin:0}h4{margin:0 0 12px}small,.hint,.empty{color:var(--muted)}.toolbar{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:12px 22px;border-block:1px solid var(--border);background:var(--bg)}.actions,.table-heading{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.actions .btn[aria-pressed=true]{border-color:var(--accent);color:var(--accent)}.workspace{padding:20px 22px;min-height:340px}.table-heading{justify-content:space-between;margin-bottom:18px}.empty{padding:36px;text-align:center}.word-detail{padding:12px;background:var(--bg);font-family:var(--font-mono);line-height:1.8}.edit-actions{margin-bottom:16px}.editor,.preview{padding:16px;margin-top:16px;border:1px solid var(--border);border-radius:5px}.editor{border-color:var(--accent);background:var(--bg)}.editor-fields{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:12px}.editor-fields label{display:grid;gap:4px}.editor-fields input{width:150px}.editor .actions{justify-content:flex-end;margin-top:12px}input:not([type=checkbox]),textarea,select{box-sizing:border-box;background:var(--bg);color:var(--fg);border:1px solid var(--border);border-radius:4px;padding:8px}textarea{width:100%;display:block;font-family:var(--font-mono)}table{width:100%;border-collapse:collapse;font-family:var(--font-mono)}th,td{text-align:left;padding:8px;border-bottom:1px solid var(--border)}td input{width:150px}.preview{overflow:auto}.confirmation{display:flex;gap:8px;align-items:center;margin:14px 0}p{line-height:1.65}summary{cursor:pointer;padding:12px 0}.system-fields{margin-top:16px}footer{padding:12px 22px;border-top:1px solid var(--border);background:var(--bg)}.identity{font-family:var(--font-mono);color:var(--muted)}.error{color:var(--danger)}.file-input{display:none}@media(max-width:600px){header,.toolbar,.workspace,footer{padding:12px}.table-heading h3{width:100%}.word-detail{overflow-wrap:anywhere}}
</style>
