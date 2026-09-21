<template>
  <div class="chart-container" ref="container">
    <canvas ref="canvas" @mousemove="onMouseMove" @mouseleave="onMouseLeave"
            @wheel.prevent="onWheel"></canvas>
    <div v-if="tooltip" class="chart-tooltip" :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }">
      <div v-for="(item, i) in tooltip.items" :key="i" class="tooltip-item">
        <span class="tooltip-dot" :style="{ background: item.color }"></span>
        {{ item.name }}: {{ item.value }}
      </div>
      <div class="tooltip-time">{{ tooltip.time }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { RingBuffer } from '../../utils/RingBuffer'

const COLORS = [
  '#c96442', '#3898ec', '#b58a1b', '#2d6a4f', '#c084fc',
  '#fb923c', '#2dd4bf', '#f472b6', '#a78bfa', '#60a5fa',
]

const props = withDefaults(defineProps<{
  maxPoints?: number
  height?: string
}>(), {
  maxPoints: 500,
  height: '260px',
})

const container = ref<HTMLDivElement | null>(null)
const canvas = ref<HTMLCanvasElement | null>(null)

const channels = ref<Map<string, { ring: RingBuffer; color: string; visible: boolean }>>(new Map())
let colorIdx = 0
let animFrame = 0
let timeOffset = 0
let timeZoom = 1

interface TooltipData { x: number; y: number; time: string; items: { name: string; value: string; color: string }[] }
const tooltip = ref<TooltipData | null>(null)

function getOrCreateChannel(name: string) {
  let ch = channels.value.get(name)
  if (!ch) {
    ch = { ring: new RingBuffer(props.maxPoints), color: COLORS[colorIdx % COLORS.length], visible: true }
    colorIdx++
    channels.value.set(name, ch)
  }
  return ch
}

function pushPoint(name: string, t: number, v: number) {
  getOrCreateChannel(name).ring.push(t, v)
}

function pushDataPoint(dp: Record<string, unknown>) {
  const t = (dp._t as number) || Date.now() / 1000
  if (!timeOffset) timeOffset = t - 10
  for (const [k, v] of Object.entries(dp)) {
    if (k.startsWith('_') || typeof v !== 'number' || !Number.isFinite(v)) continue
    pushPoint(k, t, v)
  }
  if (!animFrame) {
    animFrame = requestAnimationFrame(draw)
  }
}

function pushRawLine(_line: string) {
  // Raw lines are handled by RawLogPanel, not chart
}

function clear() {
  channels.value.clear()
  colorIdx = 0
  timeOffset = 0
  timeZoom = 1
}

function resize() {
  const cvs = canvas.value
  const el = container.value
  if (!cvs || !el) return false
  const dpr = window.devicePixelRatio || 1
  const w = el.clientWidth
  const h = el.clientHeight
  if (w <= 0 || h <= 0) return false
  cvs.width = w * dpr
  cvs.height = h * dpr
  cvs.style.width = w + 'px'
  cvs.style.height = h + 'px'
  const ctx = cvs.getContext('2d')
  if (ctx) ctx.scale(dpr, dpr)
  return true
}

function draw() {
  animFrame = 0
  if (!resize()) return
  const cvs = canvas.value!
  const ctx = cvs.getContext('2d')!
  const W = cvs.clientWidth
  const H = cvs.clientHeight
  ctx.clearRect(0, 0, W, H)

  const ml = 16, mr = 16, mt = 8, mb = 28
  const pw = W - ml - mr
  const ph = H - mt - mb
  if (pw <= 0 || ph <= 0) return

  // Determine visible time range
  let tMax = 0
  for (const ch of channels.value.values()) {
    const latest = ch.ring.latest()
    if (latest && latest.t > tMax) tMax = latest.t
  }
  if (tMax === 0) return
  const tRange = 10 / timeZoom
  const tMin = tMax - tRange

  // Global Y range
  let yMin = Infinity, yMax = -Infinity
  for (const [_name, ch] of channels.value) {
    if (!ch.visible || ch.ring.count < 2) continue
    if (Number.isFinite(ch.ring.min)) yMin = Math.min(yMin, ch.ring.min)
    if (Number.isFinite(ch.ring.max)) yMax = Math.max(yMax, ch.ring.max)
  }
  if (!Number.isFinite(yMin) || !Number.isFinite(yMax)) return
  const pad = (yMax - yMin) * 0.1 || 1
  yMin -= pad; yMax += pad

  function tx(v: number) { return ml + (v - tMin) / (tMax - tMin || 1) * pw }
  function ty(v: number) { return mt + ph - (v - yMin) / (yMax - yMin || 1) * ph }

  // Grid
  ctx.strokeStyle = '#d0cec4'
  ctx.lineWidth = 0.5
  for (let i = 0; i <= 5; i++) {
    const yp = Math.round(mt + ph * i / 5) + 0.5
    ctx.beginPath(); ctx.moveTo(ml, yp); ctx.lineTo(ml + pw, yp); ctx.stroke()
  }
  for (let i = 0; i <= 5; i++) {
    const xv = tMin + (tMax - tMin) * i / 5
    const xp = Math.round(tx(xv)) + 0.5
    ctx.beginPath(); ctx.moveTo(xp, mt); ctx.lineTo(xp, mt + ph); ctx.stroke()
    ctx.fillStyle = '#888'
    ctx.font = '10px Consolas, monospace'
    ctx.textAlign = 'center'
    ctx.fillText(xv.toFixed(1) + 's', xp, mt + ph + 14)
  }

  // Clip to plot area
  ctx.save()
  ctx.beginPath()
  ctx.rect(ml, mt, pw, ph)
  ctx.clip()

  // Draw each visible channel
  for (const [_name, ch] of channels.value) {
    if (!ch.visible || ch.ring.count < 2) continue
    ctx.strokeStyle = ch.color
    ctx.lineWidth = 1.5
    ctx.beginPath()
    let started = false
    const pts = ch.ring.toArray()
    for (const p of pts) {
      const sx = tx(p.t), sy = ty(p.y)
      if (sx < ml - 10 || sx > ml + pw + 10) continue
      if (!started) { ctx.moveTo(sx, sy); started = true }
      else ctx.lineTo(sx, sy)
    }
    ctx.stroke()
  }
  ctx.restore()
}

// Mouse interaction
function onMouseMove(e: MouseEvent) {
  const cvs = canvas.value
  if (!cvs) return
  const rect = cvs.getBoundingClientRect()
  const mx = e.clientX - rect.left
  const my = e.clientY - rect.top
  const ml = 16, mr = 16, mt = 8, mb = 28
  const W = cvs.clientWidth, H = cvs.clientHeight
  const pw = W - ml - mr, ph = H - mt - mb
  if (mx < ml || mx > ml + pw || my < mt || my > mt + ph) {
    tooltip.value = null
    return
  }
  const tFrac = (mx - ml) / pw
  let tMax = 0
  for (const ch of channels.value.values()) {
    const latest = ch.ring.latest()
    if (latest && latest.t > tMax) tMax = latest.t
  }
  const tRange = 10 / timeZoom
  const tMin = tMax - tRange
  const probeTime = tMin + tFrac * tRange

  const items: TooltipData['items'] = []
  for (const [name, ch] of channels.value) {
    if (!ch.visible) continue
    const pts = ch.ring.toArray()
    let closest = pts[0]
    let minDist = Infinity
    for (const p of pts) {
      const d = Math.abs(p.t - probeTime)
      if (d < minDist) { minDist = d; closest = p }
    }
    if (closest && minDist < tRange * 0.1) {
      items.push({ name, value: closest.y.toFixed(3), color: ch.color })
    }
  }
  tooltip.value = { x: mx + 12, y: my - 8, time: probeTime.toFixed(3) + 's', items }
}

function onMouseLeave() {
  tooltip.value = null
}

function onWheel(e: WheelEvent) {
  if (e.deltaY < 0) timeZoom = Math.min(timeZoom * 1.2, 20)
  else timeZoom = Math.max(timeZoom / 1.2, 0.2)
  draw()
}

// Resize observer
let ro: ResizeObserver | null = null
onMounted(() => {
  nextTick(() => {
    if (container.value) {
      ro = new ResizeObserver(() => draw())
      ro.observe(container.value)
    }
  })
})

onUnmounted(() => {
  if (animFrame) cancelAnimationFrame(animFrame)
  if (ro) ro.disconnect()
})

defineExpose({ pushDataPoint, pushRawLine, clear, draw })
</script>

<style scoped>
.chart-container {
  position: relative;
  width: 100%;
  height: v-bind(height);
  background: var(--input-bg, #fff);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}
canvas {
  display: block;
  width: 100%;
  height: 100%;
}
.chart-tooltip {
  position: absolute;
  pointer-events: none;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 6px 8px;
  font-size: 11px;
  font-family: Consolas, monospace;
  z-index: 10;
  white-space: nowrap;
  box-shadow: 0 2px 6px rgba(0,0,0,0.08);
}
.tooltip-item {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--fg);
}
.tooltip-dot {
  width: 6px; height: 6px; border-radius: 50%; display: inline-block;
}
.tooltip-time {
  color: var(--dim);
  margin-top: 2px;
  font-size: 10px;
}
</style>
