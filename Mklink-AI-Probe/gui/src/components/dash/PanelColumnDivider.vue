<script setup lang="ts">
import { ref } from 'vue'
import { tr } from '../../composables/useLanguage'
const props = defineProps<{ width: number; span: number; minimum: number; maximum: number }>()
const emit = defineEmits<{ resize: [width: number] }>()
const preview = ref<number>()
let drag: { pointer: number; x: number; width: number; step: number } | undefined
function start(e: PointerEvent) {
  const el = e.currentTarget as HTMLElement
  const grid = el.closest('.workbench-grid')
  if (e.button !== 0 || drag || !grid?.clientWidth) return
  drag = { pointer: e.pointerId, x: e.clientX, width: props.width, step: grid.clientWidth / 12 }
  el.setPointerCapture(e.pointerId)
}
function bounded(n: number) { return Math.max(props.minimum, Math.min(props.maximum, n)) }
function move(e: PointerEvent) {
  if (drag && e.pointerId === drag.pointer) {
    const width = bounded(drag.width + Math.round((e.clientX - drag.x) / drag.step))
    if (preview.value !== width) { preview.value = width; emit('resize', width) }
  }
}
function end(e: PointerEvent, cancel = false) {
  if (!drag || e.pointerId !== drag.pointer) return
  if (cancel) emit('resize', drag.width)
  else move(e)
  drag = undefined; preview.value = undefined
}
</script>
<template>
  <div class="panel-column-divider" role="separator" tabindex="0" aria-orientation="vertical"
    :aria-label="tr('调整左右分栏比例', 'Resize adjacent columns')" :aria-valuemin="minimum" :aria-valuemax="maximum" :aria-valuenow="width"
    :aria-valuetext="width + ' / ' + (span - width)" :title="tr('拖动调整分栏，双击均分', 'Drag to resize columns; double-click to balance')"
    @pointerdown="start" @pointermove="move" @pointerup="end($event)" @pointercancel="end($event, true)" @lostpointercapture="end($event, true)"
    @keydown.left.prevent="emit('resize', bounded(width - 1))" @keydown.right.prevent="emit('resize', bounded(width + 1))"
    @keydown.home.prevent="emit('resize', minimum)" @keydown.end.prevent="emit('resize', maximum)" @dblclick="emit('resize', bounded(Math.round(span / 2)))">
    <span v-if="preview !== undefined">{{ width }} / {{ span - width }}</span>
  </div>
</template>
<style scoped>
.panel-column-divider { position:absolute; z-index:12; top:6%; bottom:6%; right:-3px; width:12px; cursor:col-resize; touch-action:none; }
.panel-column-divider::after { content:''; position:absolute; background:var(--muted); border-radius:2px; width:3px; height:32px; left:4px; top:calc(50% - 16px); }
.panel-column-divider:hover::after,.panel-column-divider:focus-visible::after { background:var(--accent); }
.panel-column-divider span { position:absolute; right:12px; top:50%; white-space:nowrap; background:var(--surface); color:var(--fg); padding:2px 6px; border:1px solid var(--border); border-radius:4px; }
@media(max-width:700px){.panel-column-divider { display:none; }}
</style>
