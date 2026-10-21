<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import HpmOtpGrid from './HpmOtpGrid.vue'
import type { HpmIspOtpBatchPlan, HpmIspOtpChange, HpmIspOtpSnapshot } from '../types/hpmOtp'
import { customOtpEntries, otpCsv, otpHex as hex, parseOtpCsv, type OtpEntry } from '../lib/otpConfiguration'
import { saveTextFile } from '../lib/downloadTextFile'
import { tr } from '../composables/useLanguage'
const props = defineProps<{ snapshot: HpmIspOtpSnapshot | null; plan: HpmIspOtpBatchPlan | null; result: string; busy: boolean; disabled: boolean; error: string }>()
const emit = defineEmits<{ read: []; prepare: [changes: HpmIspOtpChange[]]; program: [planId: string]; invalidate: [] }>()
const view = ref<'read' | 'write'>('read')
const columns = ref(4), selected = ref(69), confirmed = ref(false), pending = ref<OtpEntry[]>([])
const editing = ref(false), start = ref(69), count = ref(1), values = ref('0x00000000')
const localError = ref(''), importing = ref(false), saving = ref(false), fileInput = ref<HTMLInputElement>()
let revision = 0
const unavailable = computed(() => props.busy || props.disabled || importing.value)
const readEntries = computed(() => props.snapshot?.words.map(item => ({ ...item, value: item.current })) || [])
const selectedEntry = computed(() => readEntries.value.find(item => item.word === selected.value))
const writablePlan = computed(() => props.plan?.qualified === true && props.plan.write_supported === true && !!props.plan.plan_id)
const changes = computed(() => pending.value.flatMap(item => {
  const row = props.snapshot?.words.find(row => row.word === item.word)
  return row && row.current !== item.value ? [{ word: item.word, expected: row.current, desired: hex(item.value) }] : []
}))
const canPrepare = computed(() => !!props.snapshot && pending.value.length > 0 && changes.value.length > 0
  && pending.value.every(item => {
    const row = props.snapshot?.words.find(row => row.word === item.word)
    return row && (row.current === item.value || (row.locked !== true && ((row.current & item.value) >>> 0) === row.current))
  }))
function invalidate() { revision++; confirmed.value = false; emit('invalidate') }
watch(pending, invalidate, { deep: true, flush: 'sync' })
watch(() => props.plan, () => { confirmed.value = false })
watch(() => props.snapshot, () => { confirmed.value = false })
onBeforeUnmount(() => { revision++; emit('invalidate') })
onMounted(() => { if (!props.snapshot && !unavailable.value) emit('read') })
function refresh() {
  if (unavailable.value) return
  invalidate(); localError.value = ''; emit('read')
}
function addDialog(word?: number) {
  if (unavailable.value) return
  start.value = word ?? 69; count.value = 1
  values.value = hex(pending.value.find(item => item.word === start.value)?.value ?? selectedEntry.value?.current ?? 0)
  localError.value = ''; editing.value = true; invalidate()
}
function addEntries() {
  if (unavailable.value) return
  try {
    const entries = customOtpEntries(start.value, count.value, values.value)
    pending.value = [...pending.value.filter(item => !entries.some(entry => entry.word === item.word)), ...entries].sort((a, b) => a.word - b.word)
    editing.value = false; localError.value = ''; selected.value = start.value
  } catch (error) { localError.value = tr('请检查地址、数量和 8 位十六进制值：', 'Check the address, count and 8-digit hexadecimal values: ') + String(error) }
}
async function importFile(event: Event) {
  const input = event.target as HTMLInputElement, file = input.files?.[0]
  input.value = ''
  if (!file || unavailable.value) return
  invalidate(); const current = revision; importing.value = true; localError.value = ''
  try {
    if (file.size > 65536) throw new Error(tr('文件超过 64 KB', 'File exceeds 64 KB'))
    const text = await file.text()
    if (revision !== current) return
    pending.value = parseOtpCsv(text); editing.value = false
  } catch (error) { if (revision === current) localError.value = tr('导入失败：', 'Import failed: ') + String(error) }
  finally { importing.value = false }
}
async function exportFile() {
  if (saving.value) return
  saving.value = true; localError.value = ''
  try { await saveTextFile(`HPM5301-OTP-${view.value}.csv`, otpCsv(view.value === 'read' ? readEntries.value : pending.value)) }
  catch (error) { localError.value = tr('导出失败：', 'Export failed: ') + String(error) }
  finally { saving.value = false }
}
function prepare() { if (!unavailable.value && canPrepare.value) { localError.value = ''; emit('prepare', changes.value) } }
function program() {
  if (unavailable.value || !confirmed.value || !writablePlan.value || !props.plan?.plan_id) return
  const token = props.plan.plan_id
  confirmed.value = false
  // Consume the draft when dispatching; uncertain outcomes cannot replay it.
  emit('program', token); pending.value = []
}
function reason(value: string | null) {
  const messages: Record<string, string> = {
    expected_mismatch: tr('当前值已改变，请刷新', 'Current value changed; refresh'),
    bit_clear_requested: tr('不能清除已有的 1', 'Existing 1 bits cannot be cleared'),
    read_semantics_and_locks_unknown: tr('当前固件暂不支持写入，请更新', 'Update firmware to enable programming'),
    hard_locked: tr('已永久锁定', 'Permanently locked'),
    unsupported_rom: tr('ROM 版本不支持', 'Unsupported ROM version'),
    no_change: tr('无需写入', 'No change'),
  }
  return value && value !== 'ok' ? messages[value] || value : tr('通过', 'Ready')
}
</script>

<template>
  <section class="otp-workspace" data-testid="hpm-isp-otp" :aria-busy="busy">
        <header><div><h2>{{ tr('OTP 读写', 'OTP Read / Write') }}</h2><small>HPM5301 · USART ISP · {{ tr('用户区 Word 69–79', 'User area Word 69–79') }}</small></div></header>
        <div class="toolbar">
          <div class="view-switch" role="group" :aria-label="tr('OTP 视图', 'OTP view')"><button class="btn" :class="{ active: view === 'read' }" :aria-pressed="view === 'read'" data-testid="isp-otp-read-view" @click="view = 'read'">{{ tr('读视图', 'Read view') }}</button><button class="btn" :class="{ active: view === 'write' }" :aria-pressed="view === 'write'" data-testid="isp-otp-write-view" @click="view = 'write'">{{ tr('写视图', 'Write view') }}<span v-if="pending.length" class="badge">{{ pending.length }}</span></button></div>
          <div class="actions"><button v-if="view === 'write'" class="btn" :disabled="unavailable" data-testid="isp-otp-import" @click="fileInput?.click()">{{ tr('导入', 'Import') }}</button><button class="btn" :disabled="saving || !(view === 'read' ? readEntries.length : pending.length)" @click="exportFile">{{ tr('导出', 'Export') }}</button><button class="btn" data-testid="isp-otp-read" :disabled="unavailable" @click="refresh">{{ busy ? tr('处理中…', 'Working…') : tr('刷新', 'Refresh') }}</button></div>
        </div>
        <div class="workspace">
          <div class="table-heading"><h3>OTP {{ view === 'read' ? 'Readable' : 'Writable' }} Words {{ tr('表', 'Table') }}</h3><span class="legend">● {{ tr('通用 / 用户区', 'General / User') }}</span><label>{{ tr('列数', 'Columns') }} <select v-model.number="columns" aria-label="OTP columns"><option :value="4">4</option><option :value="8">8</option></select></label></div>
          <template v-if="view === 'read'">
            <HpmOtpGrid v-if="readEntries.length" :entries="readEntries" :columns="columns" :selected="selected" @select="selected = $event" />
            <div v-else class="empty">{{ busy ? tr('正在读取 OTP…', 'Reading OTP…') : tr('目标进入 ROM ISP 后，点击“刷新”读取。', 'Enter ROM ISP on the target, then click Refresh.') }}</div>
            <div v-if="selectedEntry" class="word-detail"><b>Word {{ selectedEntry.word }}</b><span>Hex {{ hex(selectedEntry.current) }}</span><span>Binary {{ selectedEntry.current.toString(2).padStart(32, '0') }}</span><span>{{ tr('影子值', 'Shadow') }} {{ selectedEntry.shadow === null ? '—' : hex(selectedEntry.shadow) }} · {{ tr('锁定', 'Locked') }} {{ selectedEntry.locked === null ? tr('未知', 'Unknown') : selectedEntry.locked ? tr('是', 'Yes') : tr('否', 'No') }}</span></div>
          </template>
          <template v-else>
            <div class="edit-actions"><button class="btn" :disabled="unavailable" data-testid="isp-otp-add" @click="addDialog()">{{ tr('添加 Words', 'Add Words') }}</button><button class="btn" :disabled="unavailable || !pending.length" data-testid="isp-otp-remove-all" @click="pending = []; editing = false">{{ tr('移除所有', 'Remove all') }}</button><span>{{ tr('点击字可编辑', 'Click a word to edit') }}</span></div>
            <HpmOtpGrid v-if="pending.length" :entries="pending" :columns="columns" :selected="selected" :disabled="unavailable" @select="selected = $event; addDialog($event)" />
            <div v-else-if="!editing" class="empty">{{ tr('添加 Words 或导入 CSV / TXT 配置。', 'Add Words or import a CSV / TXT configuration.') }}</div>
            <form v-if="editing" class="editor" @submit.prevent="addEntries">
              <h4>{{ tr('添加 OTP 字 · 自定义', 'Add OTP Words · Custom') }}</h4><div class="editor-fields"><label>{{ tr('起始地址（Word）', 'Start address (Word)') }}<input v-model.number="start" type="number" min="69" max="79" :disabled="unavailable" aria-label="OTP start word"></label><label>{{ tr('Word 个数', 'Word count') }}<input v-model.number="count" type="number" min="1" max="11" :disabled="unavailable" aria-label="OTP word count"></label></div>
              <label>{{ tr('Word 列表（8 位十六进制数，用逗号分隔）', 'Word list (8-digit hexadecimal values, comma-separated)') }}<textarea v-model="values" :disabled="unavailable" rows="3" aria-label="OTP word values" placeholder="0x00000001, 0x00000002" /></label>
              <div class="actions"><button class="btn" type="button" :disabled="unavailable" @click="editing = false">{{ tr('取消', 'Cancel') }}</button><button class="btn" type="submit" :disabled="unavailable" data-testid="isp-otp-add-confirm">{{ tr('确定', 'OK') }}</button></div>
            </form>
            <p class="hint">{{ tr('填写写入后的完整值，已有的 1 不能改回 0。写入前逐字预检；失败即停止，已完成的写入无法撤销。', 'Enter complete final values; existing 1 bits cannot be cleared. Every word is checked before programming. Stops on failure; completed writes cannot be undone.') }}</p>
            <div class="actions"><span v-if="pending.length && !snapshot">{{ tr('请先刷新当前芯片的 OTP', 'Refresh OTP on the current chip first') }}</span><span v-else-if="pending.length && !canPrepare">{{ tr('检查锁定状态和目标值；与当前相同的字无需写入。', 'Check locks and desired values; unchanged words need no programming.') }}</span><button class="btn btn-primary" :disabled="unavailable || editing || !canPrepare" data-testid="isp-otp-plan" @click="prepare">{{ tr('检查并预览', 'Check and Preview') }}</button></div>
            <section v-if="plan" class="preview">
              <h4>{{ tr('写入预览', 'Programming preview') }}</h4><table><thead><tr><th>Word</th><th>{{ tr('当前值', 'Current') }}</th><th>{{ tr('目标值', 'Desired') }}</th><th>{{ tr('新增位', 'New bits') }}</th><th>{{ tr('预检', 'Preflight') }}</th></tr></thead><tbody><tr v-for="change in plan.changes" :key="change.word" data-testid="isp-otp-diff"><td>{{ change.word }}</td><td>{{ hex(change.expected) }}</td><td>{{ hex(change.desired) }}</td><td>{{ hex(change.delta) }}</td><td>{{ reason(change.reason) }}</td></tr></tbody></table>
              <p v-if="!writablePlan" data-testid="isp-otp-unavailable">{{ tr('配置未全部通过预检，请修正后重新检查。', 'Some changes failed preflight. Correct them and check again.') }}</p>
              <template v-else><label class="confirmation"><input v-model="confirmed" type="checkbox" data-testid="isp-otp-confirm" :disabled="unavailable">{{ tr('确认永久写入以上新增位，无法擦除', 'Confirm permanently burning these new bits; they cannot be erased') }}</label><button class="btn program" data-testid="isp-otp-program" :disabled="unavailable || !confirmed" @click="program">{{ tr('写入并回读', 'Program and Read Back') }}</button></template>
            </section>
          </template>
        </div>
        <footer><p v-if="localError || error" role="alert" class="error">{{ localError || error }}</p><p v-if="result" role="status" class="result">{{ result }}</p><p v-if="snapshot" class="identity">CHIP_ID {{ hex(snapshot.chip_id) }} · HARD_LOCK {{ hex(snapshot.hard_lock) }} · {{ snapshot.read_at }}</p><small>{{ tr('ROM 读取值；— / 未知表示未取得该项状态。换板后请刷新。', 'ROM values; — / Unknown means the state was not obtained. Refresh after changing boards.') }}</small></footer>
        <input ref="fileInput" type="file" accept=".csv,.txt" class="file-input" aria-label="OTP CSV file" @change="importFile">
  </section>
</template>

<style scoped>
.otp-workspace{background:var(--surface);color:var(--fg);border:1px solid var(--border);border-radius:6px;font-size:13px;overflow:hidden}header{display:flex;align-items:center;justify-content:space-between;padding:18px 22px;border-bottom:1px solid var(--border)}h2{font-size:18px;margin:0 0 5px}small,.hint{color:var(--muted);line-height:1.6}.toolbar,.table-heading,.edit-actions,.actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.toolbar{padding:14px 22px;justify-content:space-between;border-bottom:1px solid var(--border)}.view-switch{display:flex;gap:4px}.active{color:var(--accent);border-color:var(--accent);background:color-mix(in srgb,var(--accent) 12%,var(--surface))}.badge{margin-left:8px}.workspace{padding:18px 22px;min-height:270px}.table-heading{margin-bottom:12px}.table-heading h3{font-size:13px;margin:0}.table-heading label{margin-left:auto}.legend{color:var(--success);font-size:12px}.empty{padding:58px 12px;text-align:center;color:var(--muted);border:1px dashed var(--border);border-radius:5px}.word-detail{display:flex;gap:14px;flex-wrap:wrap;padding:15px 10px;margin-top:12px;background:var(--bg);font:12px var(--font-mono);line-height:1.8}.word-detail b{color:var(--success)}.edit-actions{margin-bottom:14px}.edit-actions span{color:var(--muted);margin-left:auto}select,input:not([type=checkbox]),textarea{box-sizing:border-box;background:var(--bg);color:var(--fg);border:1px solid var(--border);border-radius:4px;padding:8px}select{padding:5px}label{line-height:1.7}.editor{padding:16px;margin:12px 0;border:1px solid var(--accent);border-radius:5px;background:var(--bg)}h4{margin:0 0 12px}.editor-fields{display:flex;gap:20px;margin-bottom:12px}.editor-fields label{display:grid;gap:4px}.editor-fields input{width:170px}textarea{display:block;width:100%;resize:vertical;font-family:var(--font-mono)}.editor .actions{justify-content:flex-end;margin-top:12px}.preview{margin-top:16px;padding:16px;border:1px solid var(--border);border-radius:5px;overflow:auto}.preview table{width:100%;border-collapse:collapse;font:12px var(--font-mono)}.preview th,.preview td{text-align:left;padding:8px;border-bottom:1px solid var(--border);white-space:nowrap}.confirmation{display:flex;gap:8px;align-items:center;margin:14px 0}.program{background:var(--danger);color:white;border-color:var(--danger)}footer{padding:12px 22px;border-top:1px solid var(--border);background:var(--bg)}footer p{margin:4px 0 8px;line-height:1.6;overflow-wrap:anywhere}.identity{font:11px var(--font-mono);color:var(--muted)}.error{color:var(--danger)}.result{color:var(--fg)}.file-input{display:none}@media(max-width:600px){header,.toolbar,.workspace,footer{padding:12px}.editor-fields{flex-wrap:wrap}.table-heading h3{width:100%}.word-detail{overflow-wrap:anywhere}}
</style>
