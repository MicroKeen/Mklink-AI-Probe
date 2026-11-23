<script setup lang="ts">
import { ref } from 'vue'
import { gridRowHeight } from '../../composables/useWorkbenchGrid'
import { tr } from '../../composables/useLanguage'
import { geometrySchema } from '../../lib/workbenchLayout'

const props = defineProps<{ height: number; minimum: number }>()
const emit = defineEmits<{ resize: [height: number] }>()
const maximum = geometrySchema.h.maximum
const preview = ref<number>()
let drag: { pointer: number; startY: number; startHeight: number; card: HTMLElement } | undefined
const clamp = (rows: number) => Math.min(maximum, Math.max(props.minimum, rows))

function start(event: PointerEvent) {
  if (event.button !== 0 || drag) return
  const handle = event.currentTarget as HTMLElement
  const card = handle.closest<HTMLElement>('article[data-panel-id]')
  if (!card) return
  drag = { pointer: event.pointerId, startY: event.clientY, startHeight: props.height, card }
  handle.setPointerCapture(event.pointerId)
}
function move(event: PointerEvent) {
  if (!drag || drag.pointer !== event.pointerId) return
  const pixels = Math.min(maximum * gridRowHeight, Math.max(props.minimum * gridRowHeight, drag.startHeight * gridRowHeight + event.clientY - drag.startY))
  drag.card.style.setProperty('--drag-height', pixels + 'px')
  preview.value = Math.round(pixels / gridRowHeight)
}
function finish(event: PointerEvent, apply: boolean) {
  if (!drag || drag.pointer !== event.pointerId) return
  if (apply) move(event)
  const rows = preview.value
  drag.card.style.removeProperty('--drag-height')
  drag = undefined
  preview.value = undefined
  if (apply && rows !== undefined && rows !== props.height) emit('resize', rows)
}
</script>

<template>
  <div class="narrow-panel-resize" role="separator" tabindex="0" aria-orientation="horizontal"
    :aria-label="tr('调整面板高度', 'Resize panel height')" :title="tr('拖动或按上下键调整高度', 'Drag or use the arrow keys to resize')"
    :aria-valuemin="minimum" :aria-valuemax="maximum" :aria-valuenow="preview ?? height"
    @pointerdown="start" @pointermove="move" @pointerup="finish($event, true)" @lostpointercapture="finish($event, false)"
    @pointercancel="finish($event, false)" @keydown.up.prevent="emit('resize', clamp(height - 1))" @keydown.down.prevent="emit('resize', clamp(height + 1))" />
</template>

<style scoped>
.narrow-panel-resize { display:none; }
@media (max-width:700px) {
  .narrow-panel-resize { display:grid; place-items:center; flex:0 0 24px; cursor:ns-resize; touch-action:none; user-select:none; }
  .narrow-panel-resize::after { content:''; width:32px; height:3px; background:var(--muted); border-radius:2px; }
  .narrow-panel-resize:focus-visible { outline:2px solid var(--accent); outline-offset:-2px; }
}
</style>
