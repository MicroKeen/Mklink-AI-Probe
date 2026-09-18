<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { API_BASE } from '../lib/runtimeEndpoint'
import { tr } from '../composables/useLanguage'
const props = defineProps<{ partNumber: string; model: string }>()
interface Word { word: number; current: number; shadow: number; locked: boolean }
interface Plan { word: number; group?: number; expected: number; desired: number; delta: number; script: string }
const rows = ref<Word[]>([]), selected = ref(69), desired = ref('')
const operation = ref('data'), group = ref(19), hardLock = ref<number | null>(null)
const prepared = ref<Plan | null>(null), confirmed = ref(false), busy = ref(false)
const error = ref(''), result = ref('')
const row = computed(() => rows.value.find(item => item.word === selected.value))
const hex = (value: number) => `0x${value.toString(16).toUpperCase().padStart(8, '0')}`
let revision = 0
function invalidate() { prepared.value = null; confirmed.value = false }
watch(() => [props.partNumber, props.model], () => {
  revision++; rows.value = []; hardLock.value = null; desired.value = ''; result.value = ''; invalidate()
})
watch([selected, desired, operation, group], invalidate)
onBeforeUnmount(() => { revision++; invalidate() })
async function request(action: 'read' | 'plan' | 'program') {
  if (busy.value) return
  const requestRevision = revision, plan = prepared.value
  if (action === 'program' && (!plan || !confirmed.value)) return
  busy.value = true; error.value = ''; result.value = ''
  const endpoint = operation.value === 'lock' && action !== 'read' ? `lock-${action}` : action
  const args = action === 'read' ? {} : action === 'program' ? {
    word: plan!.group ?? plan!.word, expected: plan!.expected, desired: plan!.desired, confirm_irreversible: true,
  } : operation.value === 'lock' ? { word: group.value, expected: hardLock.value, desired: 0 }
    : { word: selected.value, expected: row.value?.current ?? 0, desired: desired.value || '0' }
  if (action !== 'program') invalidate()
  if (action === 'read') { rows.value = []; hardLock.value = null }
  try {
    const response = await fetch(`${API_BASE}/api/device/configuration/hpm-user-otp/${endpoint}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ part_number: props.partNumber, model: props.model, ...args }),
    })
    const body = await response.json()
    if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : body.detail?.message || `HTTP ${response.status}`)
    if (requestRevision !== revision) return
    if (action === 'read') { rows.value = body.words; hardLock.value = body.hard_lock ?? null }
    else if (action === 'plan') prepared.value = body
    else {
      result.value = `${tr('写入并校验通过', 'Written and verified')}: word ${body.word} = ${hex(body.after)}`
      rows.value = []; hardLock.value = null; invalidate()
    }
  } catch (e) {
    if (requestRevision === revision) {
      error.value = `${e instanceof Error ? e.message : String(e)}${action === 'program' ? tr('。请重新读取确认结果，不要重试写入。', '. Read the result again; do not retry programming.') : ''}`
      rows.value = []; hardLock.value = null; invalidate()
    }
  } finally { busy.value = false }
}
</script>
<template>
  <section class="user-otp" data-testid="hpm-user-otp" :aria-busy="busy">
    <h4>{{ tr('HPM5301 用户 OTP', 'HPM5301 User OTP') }}</h4>
    <p>{{ tr('仅开放用户 word 69–79。熔丝只能从 0 写为 1，无法擦除；写入会重启目标程序。', 'Only user words 69–79 are available. Fuses only change from 0 to 1 and cannot be erased. Programming restarts the target.') }}</p>
    <button class="btn" :disabled="busy" data-testid="otp-read" @click="request('read')">{{ tr('读取用户 OTP', 'Read User OTP') }}</button>
    <p v-if="error" role="alert" class="error">{{ error }}</p><p v-if="result" role="status">{{ result }}</p>
    <div v-if="rows.length" class="table-wrap"><table>
      <thead><tr><th>Word</th><th>{{ tr('熔丝值', 'Fuse') }}</th><th>{{ tr('影子值', 'Shadow') }}</th><th>{{ tr('锁定', 'Locked') }}</th></tr></thead>
      <tbody><tr v-for="item in rows" :key="item.word"><td>{{ item.word }}</td><td>{{ hex(item.current) }}</td><td>{{ hex(item.shadow) }}</td><td>{{ item.locked ? tr('是', 'Yes') : tr('否', 'No') }}</td></tr></tbody>
    </table></div>
    <div class="inputs">
      <label>{{ tr('操作', 'Operation') }} <select v-model="operation" :disabled="busy" aria-label="OTP operation"><option value="data">{{ tr('用户数据', 'User data') }}</option><option value="lock">{{ tr('永久写保护', 'Permanent write protection') }}</option></select></label>
      <template v-if="operation === 'data'">
        <label>Word <select v-model="selected" :disabled="busy" aria-label="OTP word"><option v-for="word in 11" :key="word" :value="68 + word">{{ 68 + word }}</option></select></label>
        <label>{{ tr('目标值', 'Desired value') }} <input v-model="desired" :disabled="busy" aria-label="OTP desired value" placeholder="0x00000000"></label>
      </template>
      <label v-else>{{ tr('永久锁定范围', 'Permanently lock range') }} <select v-model="group" :disabled="busy" aria-label="OTP lock group"><option :value="18">Word 72–75</option><option :value="19">Word 76–79</option></select></label>
      <button class="btn" :disabled="busy || (operation === 'data' ? !row || row.locked || !desired : hardLock === null)" data-testid="otp-plan" @click="request('plan')">{{ tr('校验并生成脚本', 'Validate and Generate Script') }}</button>
    </div>
    <p v-if="operation === 'lock'">{{ tr('锁定后该组 4 个 word 永远不能再烧写，仍可读取；无法解锁。只保护熔丝，影子寄存器另有锁机制。', 'All four words become permanently unprogrammable but remain readable. This cannot be unlocked. Shadow registers have separate protection.') }}</p>
    <template v-if="prepared">
      <p v-if="prepared.group">{{ tr('将永久锁定', 'Permanently locking') }} Word {{ prepared.group * 4 }}–{{ prepared.group * 4 + 3 }}</p>
      <p>Word {{ prepared.word }}: {{ hex(prepared.expected) }} → {{ hex(prepared.desired) }} · {{ tr('新增位', 'New bits') }} {{ hex(prepared.delta) }}</p>
      <pre>{{ prepared.script }}</pre>
      <label class="confirmation"><input v-model="confirmed" type="checkbox" :disabled="busy" data-testid="otp-confirm">{{ tr('确认永久写入以上新增位，并重启目标程序', 'Confirm permanently burning the new bits above and restarting the target') }}</label>
      <button class="btn" data-testid="otp-program" :disabled="busy || !confirmed" @click="request('program')">{{ busy ? tr('执行中…', 'Working…') : tr('写入并校验', 'Program and Verify') }}</button>
    </template>
  </section>
</template>
<style scoped>
.user-otp{margin-top:12px;padding:12px;border:1px solid var(--border);border-radius:6px;font-size:12px}h4{margin:0 0 8px}p{line-height:1.6;color:var(--muted)}.error{color:var(--danger);overflow-wrap:anywhere}
.table-wrap{overflow:auto;max-height:230px;margin:10px 0}table{width:100%;border-collapse:collapse;font-family:var(--font-mono);font-size:11px}th,td{text-align:left;padding:5px;white-space:nowrap;border-bottom:1px solid var(--border)}
.inputs{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0;align-items:end}.inputs label{display:flex;flex-direction:column;gap:4px}select,input:not([type=checkbox]){padding:6px;background:var(--surface);color:var(--fg);border:1px solid var(--border);border-radius:4px;max-width:160px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;padding:10px;background:var(--bg);border-radius:4px;font-size:11px}.confirmation{display:flex;gap:6px;align-items:start;margin:10px 0}
</style>
