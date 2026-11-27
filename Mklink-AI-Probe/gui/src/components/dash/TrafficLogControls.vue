<template>
  <div class="traffic-log-controls" :class="{ compact }">
    <details ref="menuDetails">
      <summary>{{ tr('日志', 'Logs') }}{{ recording ? tr(' · 记录中', ' · Recording') : '' }}</summary>
      <div class="log-actions">
        <SuperWatchRecording :name="kind === 'rtt' ? 'RTT' : 'Serial'" :endpoint="`/api/dash/${kind}/traffic-recording`" :channel="channel" :disabled="!!log" @state="recording = ['recording','stopping'].includes($event)" />
        <button data-testid="traffic-open" :disabled="recording || loading" @click="picker?.click()">{{ tr('日志回放', 'Log replay') }}</button>
        <input ref="picker" type="file" accept=".mklog,.jsonl" hidden @change="openFile" />
      </div>
    </details>
    <div v-if="log" class="replay-controls" data-testid="traffic-replay">
      <span :title="filename">{{ filename }}</span>
      <select v-model="source" :aria-label="tr('日志通道', 'Log channel')" @change="seek(0)"><option v-for="name in log.sources" :key="name">{{ name }}</option></select>
      <button data-testid="traffic-play" @click="togglePlay">{{ playing ? tr('暂停', 'Pause') : tr('播放', 'Play') }}</button>
      <select v-model.number="speed" :aria-label="tr('回放速度', 'Replay speed')"><option v-for="n in [0.25,0.5,1,2,4,10]" :key="n" :value="n">{{ n }}×</option></select>
      <input data-testid="traffic-seek" type="range" min="0" :max="indexed ? duration : total" :step="indexed ? 0.001 : 1" :value="indexed ? elapsed : cursor" :aria-label="tr('回放位置', 'Replay position')" @input="seekSlider(Number(($event.target as HTMLInputElement).value))" />
      <small v-if="indexed">{{ elapsed.toFixed(3) }} / {{ duration.toFixed(3) }} s</small><small>{{ cursor }} / {{ total }}</small>
      <button data-testid="traffic-close" @click="close">{{ tr('退出回放', 'Exit replay') }}</button>
    </div>
    <span v-if="log?.warning" role="status" class="warning">{{ tr('日志不完整或采集存在丢失；仅回放已保存数据。', 'Incomplete log or acquisition loss; replaying saved data only.') }}</span>
    <span v-if="error" role="alert">{{ error }}</span>
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, shallowRef } from 'vue'
import { mountDetailsMenu } from '../../lib/detailsMenu'
import SuperWatchRecording from './SuperWatchRecording.vue'
import { tr } from '../../composables/useLanguage'
import { indexedTraffic, parseTrafficLog, TRAFFIC_FILE_LIMIT, type TrafficFrame, type TrafficLog } from '../../lib/trafficReplay'
import { useGuiPanel } from '../../lib/guiAutomation'
const props = withDefaults(defineProps<{ kind: 'rtt' | 'serial'; channel?: number; compact?: boolean }>(), { channel: 0 })
const menuDetails = ref<HTMLDetailsElement>()
let disposeMenu: (() => void) | undefined
onMounted(() => { if (menuDetails.value) disposeMenu = mountDetailsMenu(menuDetails.value, menuDetails.value.querySelector('.log-actions')!) })
onUnmounted(() => disposeMenu?.())
const emit = defineEmits<{ state: [active: boolean]; reset: []; batch: [frames: TrafficFrame[]] }>()
const picker = ref<HTMLInputElement>(), log = shallowRef<TrafficLog | null>(null), filename = ref(''), source = ref('')
const indexed = shallowRef<Awaited<ReturnType<typeof indexedTraffic>> | null>(null)
let epoch = 0, reading = false
let activePage: Awaited<ReturnType<NonNullable<typeof indexed.value>['page']>> | null = null
const elapsed = ref(0)
const duration = computed(() => (indexed.value?.duration(source.value) ?? 0) / 1000)
const total = computed(() => indexed.value?.count(source.value) ?? frames.value.length)
const frames = computed(() => log.value?.frames.filter(frame => frame.source === source.value) || [])
const recording = ref(false), loading = ref(false), error = ref(''), playing = ref(false), speed = ref(1), cursor = ref(0)
useGuiPanel(`${props.kind}.replay.${props.channel}`, {
  snapshot: () => ({ active: !!log.value, loading: loading.value, file: filename.value, source: source.value,
    sources: log.value?.sources, playing: playing.value, speed: speed.value, cursor: cursor.value,
    frames: total.value, error: error.value, warning: log.value?.warning }),
  actions: {},
})
let disposed = false, generation = 0, position = 0, lastTick = 0
const times = computed(() => {
  let previous = 0
  const origin = frames.value[0]?.time || 0
  return frames.value.map(frame => previous = Math.max(previous, (frame.time - origin) * 1000))
})
async function openFile(event: Event) {
  const input = event.target as HTMLInputElement, file = input.files?.[0]
  input.value = ''
  if (!file || recording.value) return
  const current = ++generation
  loading.value = true; error.value = ''
  try {
    const long = file.name.toLowerCase().endsWith('.mklog') ? await indexedTraffic(file, props.kind) : null
    if (!long && file.size > TRAFFIC_FILE_LIMIT) throw new Error(tr('请加载不超过 16 MiB 的日志分段。', 'Open a log part of at most 16 MiB.'))
    const parsed = long ? { frames: [], sources: long.sources, warning: long.warning } : parseTrafficLog(await file.text(), props.kind)
    if (disposed || current !== generation) return
    epoch++; activePage = null; reading = false; elapsed.value = 0
    indexed.value = long; playing.value = false; log.value = parsed; filename.value = file.name; source.value = parsed.sources[0]!
    emit('state', true); seek(0)
  } catch (caught) { if (!disposed && current === generation) error.value = String(caught) }
  finally { if (!disposed && current === generation) loading.value = false }
}
async function seekSlider(value: number) {
  if (!indexed.value) { seek(value); return }
  playing.value = false
  const current = ++epoch
  try {
    const time = Math.max(0, Math.min(duration.value, value)) * 1000
    const index = await indexed.value.cursorAt(source.value, time)
    if (current === epoch) await indexedSeek(index, time)
  } catch (caught) { if (current === epoch) { reading = false; error.value = String(caught) } }
}
async function indexedSeek(index: number, time?: number) {
  const current = ++epoch, recording = indexed.value!, channel = source.value
  activePage = null; reading = true
  try {
    // Reconstruct a bounded terminal window at the requested location.
    let start = Math.max(0, index - 1000)
    const history: TrafficFrame[] = []
    let targetTime = 0
    while (start < index) {
      const page = await recording.page(channel, start)
      if (current !== epoch) return
      const next = Math.min(index, page.first + page.frames.length)
      history.push(...page.frames.slice(start - page.first, next - page.first))
      activePage = page; targetTime = page.times[next - page.first - 1]!
      start = next
    }
    position = time ?? Math.max(0, targetTime); elapsed.value = position / 1000; cursor.value = index
    emit('reset'); emit('batch', history)
  } catch (caught) { if (current === epoch) error.value = String(caught) }
  finally { if (current === epoch) reading = false }
}
function seek(index: number) {
  playing.value = false
  if (indexed.value) { void indexedSeek(Math.max(0, Math.min(index, total.value))); return }
  cursor.value = Math.max(0, Math.min(index, total.value))
  position = times.value[Math.max(0, cursor.value - 1)] || 0
  redraw()
}
function redraw() {
  if (indexed.value) { void indexedSeek(cursor.value, position); return }
  emit('reset'); emit('batch', frames.value.slice(0, cursor.value))
}
function togglePlay() {
  if (!playing.value && cursor.value >= total.value) seek(0)
  playing.value = !playing.value; lastTick = performance.now()
}
async function playIndexed() {
  if (reading || !indexed.value) return
  reading = true
  const current = epoch
  try {
    if (!activePage || cursor.value < activePage.first || cursor.value >= activePage.first + activePage.frames.length) {
      const page = await indexed.value.page(source.value, cursor.value)
      if (current !== epoch || !playing.value) return
      activePage = page
    }
    const page = activePage, from = cursor.value - page.first
    let to = from
    while (to < page.frames.length && page.times[to]! <= position) to++
    if (to > from) { emit('batch', page.frames.slice(from, to)); cursor.value = page.first + to }
    if (cursor.value >= total.value) playing.value = false
  } catch (caught) { if (current === epoch) { playing.value = false; error.value = String(caught) } }
  finally { if (current === epoch) reading = false }
}
const timer = setInterval(() => {
  if (!playing.value) return
  const now = performance.now(); position += (now - lastTick) * speed.value; lastTick = now
  if (indexed.value) { elapsed.value = Math.min(duration.value, position / 1000); void playIndexed(); return }
  const start = cursor.value
  while (cursor.value < frames.value.length && times.value[cursor.value]! <= position) cursor.value++
  if (cursor.value > start) emit('batch', frames.value.slice(start, cursor.value))
  if (cursor.value === frames.value.length) playing.value = false
}, 25)
function close() { generation++; epoch++; indexed.value = null; activePage = null; reading = false; loading.value = false; playing.value = false; log.value = null; emit('reset'); emit('state', false) }
defineExpose({ redraw })
onUnmounted(() => { disposed = true; generation++; epoch++; clearInterval(timer) })
</script>
<style scoped>
.traffic-log-controls { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; font-size: 12px; margin: 4px 0; }
.traffic-log-controls.compact { display: contents; }
.compact > details { flex: 0 0 auto; position: static; }
.compact summary { white-space: nowrap; }
/* The RTT toolbar wraps. Anchor the menu to that toolbar, even when Logs starts a new row. */
.compact .log-actions { left: 0; right: 0; min-width: 0; max-width: none; }
.compact .replay-controls { flex: 1 0 100%; order: 1; }
.compact > .warning, .compact > [role=alert] { flex-basis: 100%; order: 2; }
details { position: relative; } summary { cursor: pointer; color: var(--accent); padding: 4px 8px; }
.log-actions { position: absolute; top: 100%; left: 0; z-index: 30; min-width: 250px; max-width: 70vw; padding: 12px; display: flex; flex-wrap: wrap; gap: 8px; border: 1px solid var(--border); background: var(--surface); border-radius: 6px; box-shadow: 0 4px 16px #0005; }
.replay-controls { display: flex; flex: 1; align-items: center; flex-wrap: wrap; gap: 6px; min-width: 0; }
.replay-controls span { max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.replay-controls input { flex: 1; min-width: 80px; }
button, select { color: inherit; background: var(--surface); border: 1px solid var(--border); border-radius: 4px; padding: 4px 7px; font: inherit; }
.log-actions { color: var(--fg); }
.log-actions :deep(button) { height: var(--control-height, 30px); padding: 0 8px; white-space: nowrap; }
[role=alert], .warning { color: #efa45d; }
</style>
