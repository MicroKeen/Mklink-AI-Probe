<template>
  <aside class="peripheral-panel" data-testid="peripheral-panel">
    <div ref="searchBox" class="chip-search" @focusout="closeSuggestions">
      <label for="peripheral-chip-input">{{ tr('芯片型号 / HPM 系列', 'Chip model / HPM series') }}</label>
      <input id="peripheral-chip-input" v-model="chipQuery" class="form-input" data-testid="peripheral-chip-search" role="combobox" aria-autocomplete="list" aria-controls="peripheral-chip-suggestions" :aria-expanded="suggestionsOpen" :aria-activedescendant="suggestionsOpen && activeSuggestion >= 0 ? `peripheral-chip-option-${activeSuggestion}` : undefined" :placeholder="tr('如 HPM5300 / STM32F103RE', 'e.g. HPM5300 / STM32F103RE')" @input="searchInput" @focus="suggestionsOpen = true; loadTargets()" @keydown="searchKeydown" />
      <div v-if="suggestionsOpen && targets.length" id="peripheral-chip-suggestions" role="listbox" class="chip-suggestions">
        <button v-for="(target, index) in targets" :id="`peripheral-chip-option-${index}`" :key="target.id" type="button" role="option" :aria-selected="index === activeSuggestion" class="chip-suggestion" @mousedown.prevent @click="chooseTarget(target)"><strong>{{ target.target }}</strong><small>{{ target.pack }}</small></button>
      </div>
    </div>
    <select v-model="targetId" class="form-input" data-testid="peripheral-svd" :aria-label="tr('SVD 文件', 'SVD file')" @change="chooseSvd">
      <option value="">{{ searching ? tr('正在匹配 SVD…', 'Finding SVD…') : tr('匹配的 SVD 文件', 'Matching SVD file') }}</option>
      <option v-for="target in matchingSvds" :key="target.id" :value="target.id" :title="target.pack">{{ target.target }} · {{ target.svd.split(/[\\/]/).pop() }} · {{ target.pack }}</option>
    </select>
    <p v-if="chipQuery.trim() && !searching && !matchingSvds.length" data-testid="peripheral-no-match">{{ tr('没有匹配的外设描述。可导入 Pack，或手动加载 SVD / XML 文件。', 'No matching peripheral description. Import a Pack or load an SVD / XML file manually.') }}</p>
    <button class="btn btn-primary" data-testid="peripheral-load" :disabled="!deviceConnected || !targetId || busy" @click="loadChip">{{ tr('加载外设', 'Load peripherals') }}</button>
    <button class="btn" data-testid="peripheral-load-svd" :disabled="!deviceConnected || busy" @click="loadSvd">{{ tr('加载 SVD / XML 文件', 'Load SVD / XML file') }}</button>
    <p v-if="selection" data-testid="peripheral-source">{{ tr('当前已加载：', 'Currently loaded: ') }}{{ selection.target }} · {{ selection.pack }} · {{ selection.svd }} · {{ items.length }} {{ tr('项（只读）', 'items (read only)') }}</p>
    <p v-if="restoreError" role="status" data-testid="peripheral-restore-warning">{{ tr('上次的外设选择已失效，请重新选择实际芯片和 Pack。下载器连接及其他功能可继续使用。', 'The previous peripheral selection is unavailable. Select the actual chip and Pack again. The probe connection and other features remain available.') }} <span>{{ restoreError }}</span></p>
    <p v-if="selection?.series" data-testid="peripheral-series-note">{{ tr('已加载该系列共用外设；扩展外设可手动加载对应型号的 XML。', 'Common peripherals for this series are loaded. Load the model XML for additional peripherals.') }}</p>
    <p>{{ tr('GPIO 输入电平与输出锁存值是不同寄存器，名称以所选描述为准。采样可能漏掉短脉冲，GPIO 时钟须由程序开启。', 'GPIO input levels and output latches are separate registers; names follow the selected description. Short pulses may be missed. Firmware must enable the GPIO clock.') }}</p>
    <select v-model="group" class="form-input" data-testid="peripheral-group"><option value="">{{ tr('所有外设', 'All peripherals') }}</option><option v-for="name in groups" :key="name">{{ name }}</option></select>
    <input v-model="query" class="form-input" data-testid="peripheral-search" :placeholder="tr('搜索，如 GPIOB.12', 'Search, e.g. GPIOB.12')" />
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-else-if="!items.length">{{ tr('选择芯片型号或 HPM 系列，加载外设描述。无需 AXF。', 'Select a chip model or HPM series to load peripherals. No AXF needed.') }}</p>
    <p>{{ tr('已过滤 SVD 标注的只写和读取副作用寄存器；未标注的行为仍以芯片手册为准。', 'Write-only registers and SVD-declared read side effects are excluded; consult the chip manual for undocumented behavior.') }}</p>
    <div class="peripheral-list">
      <label v-for="item in filtered" :key="item.name" :title="`${item.register} @ ${item.address}`">
        <input type="checkbox" :data-testid="`peripheral-${item.name}`" :checked="selected.has(item.name)" :disabled="!deviceConnected || busy" @change="toggle(item.name, $event)" />
        <code>{{ item.name }}</code>
        <output>{{ latestValues[item.name] ?? '—' }}</output>
      </label>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed, nextTick, onActivated, onMounted, onUnmounted, ref, watch } from 'vue'
import { consumerTarget, saveConsumerTarget, TARGET_SELECTION_CHANGED, PACKS_CHANGED } from '../../lib/targetSelection'
import { API_BASE } from '../../lib/runtimeEndpoint'
import { tr } from '../../composables/useLanguage'
import { pickSvdFile } from '../../lib/filePicker'
import { useMklinkApi } from '../../composables/useMklinkApi'
import { domainAction, pathArg, boolArg, requireDomain, type DomainArgs } from '../../lib/domainActions'

const props = defineProps<{ deviceConnected: boolean; latestValues: Record<string, number | boolean> }>()
type Peripheral = { name: string; register: string; address: string }
const items = ref<Peripheral[]>([])
const selected = ref(new Set<string>())
const query = ref('')
const error = ref('')
const restoreError = ref('')
const busy = ref(false)
type Target = { id: string; target: string; pack: string; svd: string; series?: string }
const targets = ref<Target[]>([])
const targetId = ref('')
const chipQuery = ref(consumerTarget('peripheral'))
const chosenModel = ref('')
const searching = ref(false)
const matchingSvds = computed(() => chosenModel.value
  ? targets.value.filter(target => target.target === chosenModel.value)
  : chipQuery.value.trim() ? targets.value : [])
const searchBox = ref<HTMLElement | null>(null)
const suggestionsOpen = ref(false)
const activeSuggestion = ref(-1)
let searchTimer: ReturnType<typeof setTimeout> | undefined
let blurTimer: ReturnType<typeof setTimeout> | undefined
const selection = ref<Target | null>(null)
const group = ref('')
const groups = computed(() => [...new Set(items.value.map(item => item.name.split('.')[0]!))].sort())
let targetRequest = 0
let generation = 0
let timer: ReturnType<typeof setTimeout> | undefined
const filtered = computed(() => items.value.filter(item => (!group.value || item.name.startsWith(group.value + '.')) && item.name.toLowerCase().includes(query.value.trim().toLowerCase())).slice(0, 200))

async function loadTargets(force = false) {
  const epoch = ++targetRequest
  if (force) error.value = ''
  searching.value = true
  try {
    const payload = await request('peripherals/targets?q=' + encodeURIComponent(chipQuery.value.trim()) + (force ? '&refresh=true' : ''))
    if (epoch === targetRequest) {
      targets.value = payload.targets ?? []
      if (targetId.value && !targets.value.some(target => target.id === targetId.value)) targetId.value = ''
      const exact = targets.value.filter(target => target.target.toLowerCase() === chipQuery.value.trim().toLowerCase())
      if (!targetId.value && exact.length === 1) {
        targetId.value = exact[0]!.id
        chosenModel.value = exact[0]!.target
      } else if (!targetId.value && targets.value.length === 1 && targets.value[0]!.series) {
        targetId.value = targets.value[0]!.id
        chosenModel.value = targets.value[0]!.target
      }
      activeSuggestion.value = targets.value.length ? 0 : -1
    }
  } catch (cause) { if (epoch === targetRequest) error.value = String(cause) }
  finally { if (epoch === targetRequest) searching.value = false }
}
function applyCatalog(payload: any) {
  restoreError.value = payload.restore_error ?? ''
  items.value = payload.items ?? []
  selection.value = payload.selection ?? null
}
async function loadSvd() {
  const epoch = generation
  busy.value = true
  error.value = ''
  try {
    const file = await pickSvdFile()
    if (!file || epoch !== generation) return
    const path = typeof file === 'string' ? file : (await useMklinkApi().uploadFileSource('svd', file)).path
    if (epoch !== generation) return
    await selectCatalog({ svd: path }, epoch)
    targetId.value = ''
  } catch (cause) { if (epoch === generation) error.value = String(cause) }
  finally { busy.value = false }
}
async function loadChip() {
  busy.value = true
  error.value = ''
  const epoch = generation
  try {
    await selectCatalog({ target_id: targetId.value }, epoch)
  } catch (cause) { if (epoch === generation) error.value = String(cause) }
  finally { busy.value = false }
}
async function selectCatalog(source: { svd?: string; target_id?: string }, epoch = generation) {
  const payload = await request('peripherals/select', source)
  requireDomain(epoch === generation, 'Peripheral source changed during selection')
  applyCatalog(payload)
  selected.value = new Set()
  group.value = groups.value.includes('GPIOB') ? 'GPIOB' : groups.value[0] ?? ''
}
function chooseTarget(target: Target) {
  clearTimeout(searchTimer)
  targetRequest++
  searching.value = false
  chipQuery.value = target.target
  saveConsumerTarget('peripheral', target.target)
  chosenModel.value = target.target
  targetId.value = target.id
  suggestionsOpen.value = false
}
function chooseSvd() {
  const target = targets.value.find(candidate => candidate.id === targetId.value)
  if (target) chooseTarget(target)
}
function searchInput() {
  saveConsumerTarget('peripheral', chipQuery.value)
  chosenModel.value = ''
  targetId.value = ''
  targetRequest++
  targets.value = []
  activeSuggestion.value = -1
  searching.value = true
  error.value = ''
  suggestionsOpen.value = true
  clearTimeout(searchTimer)
  searchTimer = setTimeout(loadTargets, 150)
}
function closeSuggestions() {
  clearTimeout(blurTimer)
  blurTimer = setTimeout(() => {
    if (!searchBox.value?.contains(document.activeElement)) suggestionsOpen.value = false
  }, 0)
}
function searchKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') { suggestionsOpen.value = false; return }
  if (!targets.value.length) return
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault()
    suggestionsOpen.value = true
    activeSuggestion.value = (activeSuggestion.value + (event.key === 'ArrowDown' ? 1 : -1) + targets.value.length) % targets.value.length
  } else if (event.key === 'Enter' && suggestionsOpen.value && activeSuggestion.value >= 0) {
    event.preventDefault()
    chooseTarget(targets.value[activeSuggestion.value]!)
  }
}
function syncTarget() {
  const part = consumerTarget('peripheral')
  if (part !== chipQuery.value) {
    chipQuery.value = part
    chosenModel.value = ''
    targetId.value = ''
  }
  void loadTargets()
}
function refreshPacks() { void loadTargets() }
onMounted(() => {
  window.addEventListener(TARGET_SELECTION_CHANGED, syncTarget)
  window.addEventListener(PACKS_CHANGED, refreshPacks)
  void loadTargets()
})
onActivated(syncTarget)

async function request(path: string, body?: object) {
  const response = await fetch(`${API_BASE}/api/dash/superwatch/${path}`, body ? {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  } : undefined)
  const payload = await response.json()
  if (!response.ok || payload.error || payload.item?.error) throw new Error(payload.error || payload.item?.error || payload.detail?.message || payload.detail || response.statusText)
  return payload
}

async function refresh(epoch: number) {
  if (!props.deviceConnected) return
  try {
    const watches = await request('items')
    if (epoch !== generation || busy.value) return
    const available = new Set(items.value.map(item => item.name))
    selected.value = new Set((watches.items ?? []).map((item: { name: string }) => item.name).filter((name: string) => available.has(name)))
  } catch (cause) {
    if (epoch === generation) error.value = String(cause)
  } finally {
    if (epoch === generation) timer = setTimeout(() => void refresh(epoch), 2000)
  }
}

async function toggle(name: string, event: Event) {
  ;(event.target as HTMLInputElement).checked = selected.value.has(name)
  busy.value = true
  error.value = ''
  const epoch = generation
  try {
    await setSelected(name, !selected.value.has(name), epoch)
  } catch (cause) {
    if (epoch === generation) error.value = String(cause)
  } finally {
    busy.value = false
    await nextTick()
    ;(event.target as HTMLInputElement).checked = selected.value.has(name)
  }
}
async function setSelected(name: string, enabled: boolean, epoch = generation) {
  await request(enabled ? 'add' : 'remove', { name })
  requireDomain(epoch === generation, 'Peripheral selection changed during the operation')
  const next = new Set(selected.value)
  if (enabled) next.add(name); else next.delete(name)
  selected.value = next
}

function catalog() {
  return [
    domainAction('peripherals.search', 'Filter the loaded peripheral register catalog', { query: { type: 'string', maxLength: 512 }, group: { type: 'string', maxLength: 128 } }, ['query']),
    domainAction('peripherals.inspect', 'Read a page of matching registers and discovered targets', { offset: { type: 'integer', minimum: 0 }, limit: { type: 'integer', minimum: 1, maximum: 200 } }),
    domainAction('peripherals.targets', 'Find installed peripheral target definitions', { query: { type: 'string', maxLength: 512 }, refresh: boolArg }, ['query']),
    domainAction('peripherals.source.select', 'Load a peripheral definition by target ID or backend SVD path', { targetId: pathArg, svd: { type: 'string', maxLength: 4096 } }, [], 'file'),
    domainAction('peripherals.select', 'Add or remove a peripheral register from shared acquisition', { path: pathArg, selected: boolArg }, ['path', 'selected'], 'device'),
  ]
}
function read() { return { view: { query: query.value, group: group.value }, query: query.value, group: group.value, groups: groups.value.slice(0, 32), groupCount: groups.value.length, selection: selection.value, selected: [...selected.value].slice(0, 64), selectedCount: selected.value.size, targets: targets.value.slice(0, 24), targetCount: targets.value.length, items: filtered.value.slice(0, 24), total: items.value.length, busy: busy.value, error: error.value || restoreError.value } }
async function execute(action: string, args: DomainArgs = {}) {
  requireDomain(!busy.value, 'Peripheral controls are busy')
  if (action === 'peripherals.inspect') {
    const start = args.offset || 0, end = start + (args.limit || 100)
    return { targetCount: targets.value.length, targets: targets.value.slice(start, end), selectedCount: selected.value.size, selected: [...selected.value].slice(start, end), items: filtered.value.slice(start, end) }
  }
  if (action === 'peripherals.search') { query.value = args.query; if (args.group !== undefined) { requireDomain(!args.group || groups.value.includes(args.group), 'Unknown peripheral group'); group.value = args.group } }
  else if (action === 'peripherals.targets') {
    chipQuery.value = args.query; error.value = ''; await loadTargets(args.refresh === true); requireDomain(!error.value, error.value)
  } else if (action === 'peripherals.source.select') {
    requireDomain(Boolean(args.targetId) !== Boolean(args.svd), 'Provide exactly one targetId or svd')
    busy.value = true
    try { await selectCatalog(args.svd ? { svd: args.svd } : { target_id: args.targetId }); targetId.value = args.targetId || '' }
    finally { busy.value = false }
  } else if (action === 'peripherals.select') {
    requireDomain(props.deviceConnected && items.value.some(item => item.name === args.path), 'Peripheral is unavailable')
    busy.value = true
    try { await setSelected(args.path, args.selected) } finally { busy.value = false }
  } else throw new Error(`Unknown peripheral action: ${action}`)
  return read()
}
function restore(view: DomainArgs) { if (typeof view.query === 'string') query.value = view.query.slice(0, 512); if (typeof view.group === 'string') group.value = view.group }
defineExpose({ catalog, read, execute, restore, hasSignal: (path: string) => selected.value.has(path) })

watch(() => props.deviceConnected, async connected => {
  const epoch = ++generation
  clearTimeout(timer)
  items.value = []
  selection.value = null
  restoreError.value = ''
  selected.value = new Set()
  error.value = ''
  if (!connected) return
  try {
    const payload = await request('peripherals')
    if (epoch !== generation) return
    applyCatalog(payload)
    await refresh(epoch)
  } catch (cause) {
    if (epoch === generation) error.value = String(cause)
  }
}, { immediate: true })

onUnmounted(() => {
  window.removeEventListener(TARGET_SELECTION_CHANGED, syncTarget)
  window.removeEventListener(PACKS_CHANGED, refreshPacks)
  generation++; targetRequest++; clearTimeout(timer); clearTimeout(searchTimer); clearTimeout(blurTimer)
})
</script>

<style scoped>
.peripheral-panel { flex: 1; min-height: 0; overflow: auto; padding: 8px 10px; }
.chip-search { position: relative; }
.chip-suggestions { position: absolute; z-index: 10; top: 100%; left: 0; right: 0; max-height: 220px; overflow: auto; background: var(--surface); border: 1px solid var(--border); box-shadow: 0 4px 12px #0002; }
.chip-suggestion { display: flex; flex-direction: column; width: 100%; padding: 8px; background: var(--surface); color: var(--fg); border: 0; text-align: left; cursor: pointer; }
.chip-suggestion[aria-selected="true"], .chip-suggestion:hover { background: var(--bg); color: var(--accent); }
.chip-suggestion small { color: var(--muted); font-size: 10px; }
summary { cursor: pointer; font-weight: 600; font-size: 12px; }
summary span { color: var(--accent); }
p { font-size: 11px; color: var(--muted); margin: 7px 0; line-height: 1.5; }
[data-testid="peripheral-source"] { overflow-wrap: anywhere; }
.form-input { width: 100%; box-sizing: border-box; margin-top: 8px; }
.peripheral-list { padding-top: 8px; }
label { display: flex; align-items: center; gap: 6px; padding: 5px 0; font-size: 12px; }
output { margin-left: auto; color: var(--accent); font-family: var(--font-mono); }
</style>
