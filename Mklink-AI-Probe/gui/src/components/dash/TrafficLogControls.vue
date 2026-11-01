<template>
  <div class="traffic-log-controls">
    <details>
      <summary>{{ tr('日志', 'Logs') }}{{ recording ? tr(' · 记录中', ' · Recording') : '' }}</summary>
      <div class="log-actions">
        <SuperWatchRecording :name="kind === 'rtt' ? 'RTT' : 'Serial'" :endpoint="`/api/dash/${kind}/traffic-recording`" :channel="channel" :disabled="!!log" @state="recording = ['recording','stopping'].includes($event)" />
        <button data-testid="traffic-open" :disabled="recording || loading" @click="picker?.click()">{{ tr('日志回放', 'Log replay') }}</button>
        <input ref="picker" type="file" accept=".jsonl" hidden @change="openFile" />
      </div>
    </details>
    <div v-if="log" class="replay-controls" data-testid="traffic-replay">
      <span :title="filename">{{ filename }}</span>
      <select v-model="source" :aria-label="tr('日志通道', 'Log channel')" @change="seek(0)"><option v-for="name in log.sources" :key="name">{{ name }}</option></select>
      <button data-testid="traffic-play" @click="togglePlay">{{ playing ? tr('暂停', 'Pause') : tr('播放', 'Play') }}</button>
      <select v-model.number="speed" :aria-label="tr('回放速度', 'Replay speed')"><option v-for="n in [0.25,0.5,1,2,4,10]" :key="n" :value="n">{{ n }}×</option></select>
      <input data-testid="traffic-seek" type="range" min="0" :max="frames.length" :value="cursor" :aria-label="tr('回放位置', 'Replay position')" @input="seek(Number(($event.target as HTMLInputElement).value))" />
      <small>{{ cursor }} / {{ frames.length }}</small>
      <button data-testid="traffic-close" @click="close">{{ tr('退出回放', 'Exit replay') }}</button>
    </div>
    <span v-if="log?.warning" role="status" class="warning">{{ tr('日志不完整或采集存在丢失；仅回放已保存数据。', 'Incomplete log or acquisition loss; replaying saved data only.') }}</span>
    <span v-if="error" role="alert">{{ error }}</span>
  </div>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref, shallowRef } from 'vue'
import SuperWatchRecording from './SuperWatchRecording.vue'
import { tr } from '../../composables/useLanguage'
import { parseTrafficLog, TRAFFIC_FILE_LIMIT, type TrafficFrame, type TrafficLog } from '../../lib/trafficReplay'
const props = withDefaults(defineProps<{ kind: 'rtt' | 'serial'; channel?: number }>(), { channel: 0 })
const emit = defineEmits<{ state: [active: boolean]; reset: []; batch: [frames: TrafficFrame[]] }>()
const picker = ref<HTMLInputElement>(), log = shallowRef<TrafficLog | null>(null), filename = ref(''), source = ref('')
const frames = computed(() => log.value?.frames.filter(frame => frame.source === source.value) || [])
const recording = ref(false), loading = ref(false), error = ref(''), playing = ref(false), speed = ref(1), cursor = ref(0)
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
    if (file.size > TRAFFIC_FILE_LIMIT) throw new Error(tr('请加载不超过 16 MiB 的日志分段。', 'Open a log part of at most 16 MiB.'))
    const parsed = parseTrafficLog(await file.text(), props.kind)
    if (disposed || current !== generation) return
    playing.value = false; log.value = parsed; filename.value = file.name; source.value = parsed.sources[0]!
    emit('state', true); seek(0)
  } catch (caught) { if (!disposed && current === generation) error.value = String(caught) }
  finally { if (!disposed && current === generation) loading.value = false }
}
function seek(index: number) {
  playing.value = false; cursor.value = Math.max(0, Math.min(index, frames.value.length))
  position = times.value[Math.max(0, cursor.value - 1)] || 0
  redraw()
}
function redraw() { emit('reset'); emit('batch', frames.value.slice(0, cursor.value)) }
function togglePlay() {
  if (!playing.value && cursor.value >= frames.value.length) seek(0)
  playing.value = !playing.value; lastTick = performance.now()
}
const timer = setInterval(() => {
  if (!playing.value) return
  const now = performance.now(); position += (now - lastTick) * speed.value; lastTick = now
  const start = cursor.value
  while (cursor.value < frames.value.length && times.value[cursor.value]! <= position) cursor.value++
  if (cursor.value > start) emit('batch', frames.value.slice(start, cursor.value))
  if (cursor.value === frames.value.length) playing.value = false
}, 25)
function close() { generation++; loading.value = false; playing.value = false; log.value = null; emit('reset'); emit('state', false) }
defineExpose({ redraw })
onUnmounted(() => { disposed = true; generation++; clearInterval(timer) })
</script>
<style scoped>
.traffic-log-controls { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; font-size: 12px; margin: 4px 0; }
details { position: relative; } summary { cursor: pointer; color: var(--accent); padding: 4px 8px; }
.log-actions { position: absolute; top: 100%; left: 0; z-index: 30; min-width: 250px; max-width: 70vw; padding: 12px; display: flex; flex-wrap: wrap; gap: 8px; border: 1px solid var(--border); background: var(--surface); border-radius: 6px; box-shadow: 0 4px 16px #0005; }
.replay-controls { display: flex; flex: 1; align-items: center; flex-wrap: wrap; gap: 6px; min-width: 0; }
.replay-controls span { max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.replay-controls input { flex: 1; min-width: 80px; }
button, select { color: inherit; background: var(--surface); border: 1px solid var(--border); border-radius: 4px; padding: 4px 7px; font: inherit; }
[role=alert], .warning { color: #efa45d; }
</style>
