<template>
  <component :is="expanded === undefined ? 'span' : 'button'" ref="viewport" class="variable-path" :class="{ overflowing, dragging: drag !== null }"
    :type="expanded === undefined ? undefined : 'button'" :aria-expanded="expanded" @click="activate"
    :title="path" :aria-label="path" :tabindex="expanded === undefined && overflowing ? 0 : undefined"
    @pointerdown="startDrag" @pointermove="moveDrag" @pointerup="endDrag"
    @pointercancel="endDrag" @lostpointercapture="drag = null" @keydown="onKey">{{ path }}</component>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
const props = withDefaults(defineProps<{ path: string; alignment?: { edge: 'left' | 'right'; revision: number }; expanded?: boolean }>(), { expanded: undefined })
const emit = defineEmits<{ actions: [] }>()
let moved = false
function activate(event: MouseEvent) {
  if (props.expanded !== undefined && (!moved || event.detail === 0)) emit('actions')
}
const viewport = ref<HTMLElement | null>(null)
const overflowing = ref(false)
const drag = ref<{ id: number; x: number; left: number } | null>(null)
let observer: ResizeObserver | undefined
function measure() {
  const el = viewport.value
  overflowing.value = !!el && el.scrollWidth > el.clientWidth
  if (el && props.alignment) el.scrollLeft = props.alignment.edge === 'right' ? el.scrollWidth - el.clientWidth : 0
}
function startDrag(event: PointerEvent) {
  moved = false
  const el = viewport.value
  if (!el || event.button !== 0 || el.scrollWidth <= el.clientWidth || event.pointerType === 'touch') return
  drag.value = { id: event.pointerId, x: event.clientX, left: el.scrollLeft }
  el.setPointerCapture(event.pointerId)
  event.preventDefault()
}
function moveDrag(event: PointerEvent) {
  if (viewport.value && drag.value?.id === event.pointerId) {
    if (Math.abs(drag.value.x - event.clientX) > 4) moved = true
    viewport.value.scrollLeft = drag.value.left + drag.value.x - event.clientX
  }
}
function endDrag(event: PointerEvent) {
  if (drag.value?.id !== event.pointerId) return
  if (viewport.value?.hasPointerCapture(event.pointerId)) viewport.value.releasePointerCapture(event.pointerId)
  drag.value = null
}
function onKey(event: KeyboardEvent) {
  const el = viewport.value
  if (!el || !overflowing.value) return
  if (event.key === 'ArrowRight') el.scrollLeft += 40
  else if (event.key === 'ArrowLeft') el.scrollLeft -= 40
  else if (event.key === 'Home') el.scrollLeft = 0
  else if (event.key === 'End') el.scrollLeft = el.scrollWidth
  else return
  event.preventDefault()
}
onMounted(() => {
  measure()
  observer = new ResizeObserver(measure)
  if (viewport.value) observer.observe(viewport.value)
})
watch(() => [props.path, props.alignment], async () => {
  if (viewport.value) viewport.value.scrollLeft = 0
  await nextTick()
  measure()
})
onBeforeUnmount(() => observer?.disconnect())
</script>

<style scoped>
.variable-path { display: block; min-width: 0; overflow-x: auto; white-space: nowrap; scrollbar-width: none; font: 12px/1.5 Consolas, monospace; color: var(--fg); }
.variable-path::-webkit-scrollbar { display: none; }
button.variable-path { border:0; padding:0; background:transparent; text-align:start; cursor:pointer; }
button.variable-path:hover,button.variable-path[aria-expanded=true] { color:var(--accent); }
.variable-path.overflowing { cursor: grab; }
.variable-path.dragging { cursor: grabbing; user-select: none; }
.variable-path:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
</style>
