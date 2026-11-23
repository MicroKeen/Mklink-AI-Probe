<template>
  <section class="workbench-information">
    <div class="information-toolbar"><span>{{ following ? tr('跟随最新 Agent 答复', 'Following latest Agent reply') : tr('当前面板内容', 'Panel content') }}</span><button class="btn btn-secondary" @click="edit">{{ tr('编辑内容', 'Edit content') }}</button><button class="btn btn-secondary" v-if="!following" @click="activity.follow(panelId)">{{ tr('跟随答复', 'Follow replies') }}</button></div>
    <h3 v-if="content.title">{{ content.title }}</h3>
    <p v-if="content.text" class="information-text">{{ content.text }}</p>
    <div v-if="content.kind === 'table' && content.columns.length" class="information-table"><table><thead><tr><th v-for="(column, i) in content.columns" :key="i">{{ column }}</th></tr></thead><tbody><tr v-for="(row, r) in content.rows" :key="r"><td v-for="(cell, c) in row" :key="c">{{ cell }}</td></tr></tbody></table></div>
    <template v-if="['bar', 'line', 'pie'].includes(content.kind) && content.points.length">
      <WorkbenchAnalysisChart :content="content" />
      <ul v-if="content.kind === 'pie'" class="chart-legend"><li v-for="(point, index) in content.points" :key="index"><i :style="{ background: colors[index % colors.length] }" />{{ point.label }} · {{ point.value }}{{ content.unit }}</li></ul>
      <details><summary>{{ tr('查看图表数据', 'View chart data') }}</summary><table><thead><tr><th>{{ tr('项目', 'Item') }}</th><th>{{ tr('数值', 'Value') }} {{ content.unit }}</th></tr></thead><tbody><tr v-for="(point, index) in content.points" :key="index"><td>{{ point.label }}</td><td>{{ point.value }}</td></tr></tbody></table></details>
    </template>
    <p v-if="!content.title && !content.text && !content.rows.length && !content.points.length" class="information-empty">{{ tr('Agent 答复、说明、表格或分析图表将显示在这里。也可以手动编辑内容。', 'Agent replies, notes, tables and analysis charts appear here. You can also edit content.') }}</p>
    <p v-if="activity.state.storageError" role="alert">{{ activity.state.storageError }}</p>
    <WorkbenchSettingsDialog v-if="editing" :title="tr('编辑展示内容', 'Edit display content')" @close="editing = false">
      <form class="content-editor" @submit.prevent="applyDraft">
        <p v-if="error" role="alert">{{ error }}</p>
        <label>{{ tr('标题', 'Title') }}<input class="form-input" v-model="draft.title" maxlength="200" /></label>
        <label>{{ tr('展示方式', 'Display') }}<select class="form-select" v-model="draft.kind"><option v-for="kind in contentKinds" :key="kind" :value="kind">{{ kindLabels[kind] }}</option></select></label>
        <label>{{ tr('说明或答复', 'Notes or reply') }}<textarea v-model="draft.text" maxlength="16000" rows="5" /></label>
        <template v-if="['bar', 'line', 'pie'].includes(draft.kind)">
          <label>{{ tr('单位', 'Unit') }}<input class="form-input" v-model="draft.unit" maxlength="40" /></label>
          <div v-for="(point, index) in draft.points" :key="index" class="point-editor"><input class="form-input" v-model="point.label" :aria-label="tr('项目名称', 'Item label')" maxlength="120" /><input class="form-input" v-model.number="point.value" type="number" step="any" :aria-label="tr('数值', 'Value')" /><button class="btn btn-secondary" type="button" @click="draft.points.splice(index, 1)">{{ tr('移除', 'Remove') }}</button></div>
          <button class="btn btn-secondary" type="button" :disabled="draft.points.length >= 100" @click="draft.points.push({ label: '', value: 0 })">＋ {{ tr('添加数据', 'Add data') }}</button>
        </template>
        <template v-if="draft.kind === 'table'">
          <div v-for="(_, index) in draft.columns" :key="index" class="point-editor"><input class="form-input" v-model="draft.columns[index]" :aria-label="tr('列标题', 'Column title')" maxlength="100" /><button class="btn btn-secondary" type="button" @click="draft.columns.splice(index, 1); draft.rows.forEach(row => row.splice(index, 1))">{{ tr('移除列', 'Remove column') }}</button></div>
          <button class="btn btn-secondary" type="button" :disabled="draft.columns.length >= 8" @click="draft.columns.push(''); draft.rows.forEach(row => row.push(''))">＋ {{ tr('添加列', 'Add column') }}</button>
          <div v-for="(row, r) in draft.rows" :key="r" class="point-editor"><input class="form-input" v-for="(_, c) in row" :key="c" v-model="row[c]" :aria-label="`${r + 1} / ${draft.columns[c]}`" maxlength="500" /><button class="btn btn-secondary" type="button" @click="draft.rows.splice(r, 1)">{{ tr('移除行', 'Remove row') }}</button></div>
          <button class="btn btn-secondary" type="button" :disabled="!draft.columns.length || draft.rows.length >= 100" @click="draft.rows.push(draft.columns.map(() => ''))">＋ {{ tr('添加行', 'Add row') }}</button>
        </template>
        <div class="editor-actions"><button class="btn btn-primary" type="submit">{{ tr('应用', 'Apply') }}</button><button class="btn btn-secondary" type="button" @click="editing = false">{{ tr('取消', 'Cancel') }}</button></div>
      </form>
    </WorkbenchSettingsDialog>
  </section>
</template>
<script setup lang="ts">
import { computed, inject, ref, defineAsyncComponent } from 'vue'
import { tr } from '../../composables/useLanguage'
import { createWorkbenchActivity, workbenchActivityKey, emptyContent, contentKinds, contentSchema, type PanelContent } from '../../lib/workbenchActivity'
import { interaction, objectSchema, type JsonObject } from '../../lib/frontendControl'
import WorkbenchSettingsDialog from '../WorkbenchSettingsDialog.vue'
const WorkbenchAnalysisChart = defineAsyncComponent(() => import('./WorkbenchAnalysisChart.vue'))
const props = defineProps<{ panelId: string; chart?: boolean }>()
const activity = inject(workbenchActivityKey, createWorkbenchActivity())
const following = computed(() => !activity.state.documents[props.panelId])
const content = computed(() => activity.state.documents[props.panelId] || { ...emptyContent(), kind: props.chart ? 'bar' : 'text', title: activity.latestAnswer()?.title || '', text: activity.latestAnswer()?.text || '' })
const editing = ref(false), error = ref(''), draft = ref<PanelContent>(emptyContent())
const kindLabels = computed<Record<string, string>>(() => ({ text: tr('文字说明', 'Text'), table: tr('信息表格', 'Table'), bar: tr('柱状图', 'Bar chart'), line: tr('折线图', 'Line chart'), pie: tr('饼图', 'Pie chart') }))
const colors = ['#5ca9e6', '#ef9872', '#9d8ae3', '#6abda1', '#d7bc62', '#d984b8', '#84b3b8', '#aab17a']
function edit() { draft.value = JSON.parse(JSON.stringify(content.value)); editing.value = true; error.value = '' }
function applyDraft() { try { activity.setContent(props.panelId, draft.value); editing.value = false; error.value = '' } catch (cause) { error.value = String(cause) } }
function catalog() { return [
  { name: 'content.set', description: 'Display text, a table, bar/line/pie chart using bounded data; no HTML or script execution', args: contentSchema, effect: 'view' },
  { name: 'content.follow', description: 'Show the latest Agent answer in this information panel', args: objectSchema(), effect: 'view' },
] }
function read() { return { following: following.value, content: content.value, storage_error: activity.state.storageError } }
function execute(action: string, args: JsonObject) {
  const descriptor = catalog().find(item => item.name === action); if (!descriptor) throw new Error('Unknown information action')
  interaction.validateArgs(args, descriptor.args)
  if (action === 'content.set') activity.setContent(props.panelId, args as PanelContent)
  else activity.follow(props.panelId)
  return read()
}
defineExpose({ catalog, read, execute })
</script>
<style scoped>
.workbench-information { padding:12px; display:flex; flex-direction:column; gap:12px; min-width:0; } .information-toolbar { display:flex; align-items:center; flex-wrap:wrap; gap:8px; } .information-toolbar span { flex:1; color:var(--muted); font-size:12px; } h3,p { margin:0; } .information-text { white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.7; font-size:14px; } .information-empty { color:var(--muted); line-height:1.6; } table { width:100%; border-collapse:collapse; font-size:13px; } th,td { padding:8px; border-bottom:1px solid var(--border); text-align:left; white-space:pre-wrap; overflow-wrap:anywhere; } .information-table { overflow:auto; } .chart-legend { list-style:none; display:flex; gap:12px; flex-wrap:wrap; margin:0; padding:0; font-size:13px; } .chart-legend li { min-width:0; overflow-wrap:anywhere; } .chart-legend i { display:inline-block; width:10px; height:10px; margin-right:6px; border-radius:2px; } .content-editor { display:flex; flex-direction:column; gap:16px; } label { display:flex; flex-direction:column; gap:8px; } textarea { width:100%; box-sizing:border-box; resize:vertical; color:var(--fg); background:var(--input-bg); border:1px solid var(--border); font:inherit; padding:8px; } .point-editor { display:flex; flex-wrap:wrap; gap:8px; } .point-editor input { flex:1 1 120px; min-width:0; } .point-editor button { flex-shrink:0; } .editor-actions { display:flex; gap:8px; } [role=alert] { color:var(--danger); }
</style>
