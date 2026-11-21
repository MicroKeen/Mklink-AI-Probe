<template>
  <WorkbenchNumeric :widget="widget" :value="value">
    <template #default="{ status }">
      <VChart v-if="!status" class="meter-chart" :class="{ 'bar-meter': widget.type === 'bar-meter' }"
        :option="option" :autoresize="{ throttle: 100 }" :init-options="{ renderer: 'svg' }" :update-options="{ notMerge: true }"
        role="img" :aria-label="`${widget.title}，量程 ${min} 至 ${max} ${widget.options?.unit || ''}`" />
      <p v-if="!status && outside" class="meter-warning" role="status">超出量程 · 图形按边界显示，读数保留原值</p>
      <small class="meter-range">量程 {{ min }} ～ {{ max }} {{ widget.options?.unit }}</small>
    </template>
  </WorkbenchNumeric>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { GaugeChart, BarChart } from 'echarts/charts'
import { GridComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'
import { resolvedTheme } from '../../composables/useTheme'
import type { ControlWidget } from '../../lib/workbenchControls'
import type { NumericReading } from '../../lib/numericValue'
import WorkbenchNumeric from './WorkbenchNumeric.vue'
use([GaugeChart, BarChart, GridComponent, SVGRenderer])
const tickFormat = new Intl.NumberFormat('en', { notation: 'compact', maximumSignificantDigits: 3 })
const props = defineProps<{ widget: ControlWidget; value?: NumericReading }>()
const min = computed(() => props.widget.options?.min ?? 0)
const max = computed(() => props.widget.options?.max ?? 100)
const outside = computed(() => typeof props.value?.sample.value === 'number' && (props.value.sample.value < min.value || props.value.sample.value > max.value))
const option = computed(() => {
  const value = Math.max(min.value, Math.min(max.value, props.value?.sample.value ?? min.value))
  const dark = resolvedTheme.value === 'dark'
  const color = outside.value ? (dark ? '#f2bd5b' : '#806114') : (dark ? '#70b9fa' : '#246da8')
  const text = dark ? '#cbd5e1' : '#374151', track = dark ? '#3d4654' : '#cbd5e1'
  return props.widget.type === 'gauge' ? {
    animation: false,
    series: [{ type: 'gauge', min: min.value, max: max.value, startAngle: 200, endAngle: -20, radius: '88%', center: ['50%', '68%'],
      axisLine: { lineStyle: { width: 10, color: [[1, track]] } }, progress: { show: true, width: 10 },
      pointer: { width: 4, length: '55%' }, itemStyle: { color }, splitNumber: 2,
      axisLabel: { color: text, fontSize: 11, distance: -22, formatter: (value: number) => tickFormat.format(value) }, splitLine: { length: 8, lineStyle: { color: text } },
      axisTick: { show: false }, detail: { show: false }, title: { show: false }, data: [{ value }] }],
  } : {
    animation: false, grid: { left: 36, right: 36, top: 10, bottom: 24 },
    xAxis: { type: 'value', min: min.value, max: max.value, splitNumber: 4, axisLabel: { color: text, fontSize: 11, formatter: (value: number) => tickFormat.format(value) }, splitLine: { lineStyle: { color: track } } },
    yAxis: { type: 'category', data: [''], show: false },
    series: [{ type: 'bar', data: [value], barWidth: 18, showBackground: true, backgroundStyle: { color: track }, itemStyle: { color } }],
  }
})
</script>
<style scoped>
.meter-chart { height:160px; width:100%; min-width:0; }
.meter-chart.bar-meter { height:80px; }
.meter-warning { margin:8px 0; color:var(--warn); font-size:14px; }
.meter-range { display:block; margin:4px 0 8px; color:var(--muted); }
</style>
