<template>
  <div class="analysis-chart">
    <p v-if="factor !== 1 && content.kind !== 'pie'" class="chart-scale">{{ tr('纵轴缩放', 'Y-axis scale') }} × {{ factor.toExponential() }} · {{ tr('完整数值见提示和数据表', 'Full values in tooltip and data table') }}</p>
    <VChart class="chart" :option="option" :autoresize="{ throttle: 100 }" :init-options="{ renderer: 'svg' }"
      :update-options="{ notMerge: true }" role="img" :aria-label="description" />
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, DataZoomComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'
import type { PanelContent } from '../../lib/workbenchActivity'
import { resolvedTheme } from '../../composables/useTheme'
import { tr } from '../../composables/useLanguage'
use([BarChart, LineChart, PieChart, GridComponent, TooltipComponent, DataZoomComponent, SVGRenderer])
const props = defineProps<{ content: PanelContent }>()
const colors = ['#5ca9e6', '#ef9872', '#9d8ae3', '#6abda1', '#d7bc62', '#d984b8', '#84b3b8', '#aab17a']
const magnitude = computed(() => Math.max(0, ...props.content.points.map(point => Math.abs(point.value))))
// Keep finite input extremes from overflowing chart sums/axis arithmetic; preserve raw values in the table and tooltip.
const factor = computed(() => magnitude.value && (props.content.kind === 'pie' || magnitude.value > 1e100 || magnitude.value < 1e-100) ? magnitude.value : 1)
const description = computed(() => `${props.content.title}: ${props.content.points.map(point => `${point.label}: ${point.value} ${props.content.unit}`).join('; ')}`)
const option = computed(() => {
  const { content } = props, dark = resolvedTheme.value === 'dark', pie = content.kind === 'pie'
  const text = dark ? '#cbd5e1' : '#374151', grid = dark ? '#3d4654' : '#cbd5e1'
  const data = content.points.map(point => ({ name: point.label, value: point.value / factor.value }))
  return {
    animation: false, color: colors,
    tooltip: { trigger: pie ? 'item' : 'axis', renderMode: 'richText', confine: true,
      valueFormatter: (_value: unknown, index: number) => `${content.points[index]?.value ?? ''} ${content.unit}` },
    ...(pie ? {} : {
      grid: { left: 12, right: 20, top: 24, bottom: content.points.length > 12 ? 64 : 16, containLabel: true },
      xAxis: { type: 'category', data: content.points.map(point => point.label), axisLabel: { color: text, hideOverlap: true, width: 90, overflow: 'truncate' }, axisLine: { lineStyle: { color: grid } } },
      yAxis: { type: 'value', axisLabel: { color: text }, splitLine: { lineStyle: { color: grid } } },
      dataZoom: content.points.length > 12 ? [{ type: 'slider', start: 0, end: 100, bottom: 4, height: 22, textStyle: { color: text }, borderColor: grid }] : [],
    }),
    series: [{ type: content.kind, data,
      ...(pie ? { radius: ['35%', '65%'], avoidLabelOverlap: true, label: { show: content.points.length <= 12, color: text, width: 100, overflow: 'truncate' }, labelLayout: { hideOverlap: true } }
        : { barMaxWidth: 64, showSymbol: content.points.length <= 30, lineStyle: { width: 2 }, itemStyle: { color: colors[0] } }),
    }],
  }
})
</script>
<style scoped>
.analysis-chart { min-width:0; }
.chart { width:100%; height:280px; min-width:0; }
.chart-scale { margin:0 0 8px; font-size:13px; color:var(--muted); overflow-wrap:anywhere; }
</style>
