<template>
  <section class="numeric-readout" :aria-label="widget.title">
    <slot :status="status" />
    <div><output :aria-label="widget.title" :class="{ 'is-unavailable': !!status }">{{ status || value!.sample.value!.toFixed(widget.options?.precision ?? 0) }}</output><span v-if="!status" class="numeric-unit">{{ widget.options?.unit }}</span></div>
    <small v-if="widget.options?.note">{{ widget.options.note }}</small>
  </section>
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import type { ControlWidget } from '../../lib/workbenchControls'
import { numericStatus, type NumericReading } from '../../lib/numericValue'
const props = defineProps<{ widget: ControlWidget; value?: NumericReading }>()
const now = ref(Date.now())
const status = computed(() => numericStatus(props.value, props.widget.options || {}, Math.max(now.value, Date.now())))
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => { timer = setInterval(() => { now.value = Date.now() }, 250) })
onUnmounted(() => clearInterval(timer))
</script>
<style scoped>
.numeric-readout { padding:8px 12px; min-width:0; }
.numeric-readout > div { display:flex; flex-wrap:wrap; gap:12px; align-items:baseline; }
.numeric-readout output { font:700 clamp(24px, 3vw, 48px)/1.2 var(--font-mono); overflow-wrap:anywhere; }
.numeric-readout output.is-unavailable { font:500 20px/1.4 var(--font-body); }
.numeric-unit, small { color:var(--muted); } small { display:block; margin-top:8px; overflow-wrap:anywhere; }
</style>
