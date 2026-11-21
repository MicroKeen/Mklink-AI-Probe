<template>
  <section class="workbench-log">
    <div class="log-toolbar"><label>{{ tr('筛选', 'Filter') }}<select class="form-select" v-model="filter"><option value="all">{{ tr('全部记录', 'All entries') }}</option><option value="operation">{{ tr('操作历史', 'Operations') }}</option><option value="conversation">{{ tr('问答', 'Questions and answers') }}</option><option value="error">{{ tr('错误', 'Errors') }}</option></select></label>
      <input class="form-input" v-model="query" :aria-label="tr('搜索日志', 'Search logs')" :placeholder="tr('搜索记录…', 'Search entries…')" />
      <button class="btn btn-secondary" type="button" @click="exportLog">{{ tr('导出文本', 'Export text') }}</button><button class="btn btn-secondary" type="button" @click="confirmClear = true">{{ tr('清空本窗口记录', 'Clear window history') }}</button>
    </div>
    <p v-if="confirmClear" role="alert">{{ tr('清空本窗口的历史记录？设备原始记录文件不受影响。', 'Clear this window history? Device recording files remain intact.') }} <button class="btn btn-secondary" @click="clear">{{ tr('清空', 'Clear') }}</button><button class="btn btn-secondary" @click="confirmClear = false">{{ tr('取消', 'Cancel') }}</button></p>
    <p v-if="activity.state.storageError" role="alert">{{ activity.state.storageError }}</p>
    <small>{{ tr('本窗口按运行会话保存最近 200 条记录', 'Last 200 entries for this window and runtime session') }}<template v-if="activity.state.dropped"> · {{ activity.state.dropped }} {{ tr('条较早记录已移出', 'older entries expired') }}</template></small>
    <ol role="log" aria-live="polite" aria-relevant="additions"><li v-for="entry in visibleEntries" :key="entry.id" :data-kind="entry.kind"><header><time>{{ new Date(entry.time).toLocaleTimeString() }}</time><strong>{{ entry.title }}</strong><span>{{ entry.source }}</span><small>{{ statusLabel(entry.status) }}</small></header><p v-if="entry.text">{{ entry.text }}</p></li></ol>
    <p v-if="!visibleEntries.length">{{ tr('尚无匹配记录。面板操作和 Agent 问答将显示在这里。', 'No matching entries. Panel operations and Agent conversations appear here.') }}</p>
  </section>
</template>
<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import { createWorkbenchActivity, workbenchActivityKey } from '../../lib/workbenchActivity'
import { objectSchema, interaction, type JsonObject } from '../../lib/frontendControl'
import { saveTextFile } from '../../lib/downloadTextFile'
import { tr } from '../../composables/useLanguage'
import { display } from '../../lib/capabilityPresentation'
const activity = inject(workbenchActivityKey, createWorkbenchActivity())
const filter = ref('all'), query = ref(''), confirmClear = ref(false)
const visibleEntries = computed(() => [...activity.state.entries].reverse().filter(entry =>
  (filter.value === 'all' || filter.value === 'conversation' && ['question', 'answer'].includes(entry.kind) || entry.kind === filter.value) &&
  `${entry.title} ${entry.text} ${entry.source}`.toLowerCase().includes(query.value.toLowerCase())))
function statusLabel(status: string) { return ({ info: tr('信息', 'Info'), warn: tr('注意', 'Warning'), dispatched: tr('已提交，结果见原面板', 'Dispatched; inspect original panel'), waiting: tr('等待答复', 'Awaiting reply'), replied: tr('已答复', 'Answered') } as Record<string, string>)[status] || display(status) }
function clear() { activity.clear(); confirmClear.value = false }
async function exportLog() { return saveTextFile('mklink-operations.txt', visibleEntries.value.map(entry => `${entry.time} ${entry.source} ${entry.title} ${statusLabel(entry.status)}\n${entry.text}`).join('\n\n')) }
function catalog() { return [
  { name: 'log.read', description: 'Read operation and conversation history, newest first', args: objectSchema({ offset: { type: 'integer', minimum: 0, maximum: 200 } }, []), effect: 'view' },
  { name: 'log.filter', description: 'Filter visible history', args: objectSchema({ kind: { type: 'string', enum: ['all', 'operation', 'conversation', 'error'] }, query: { type: 'string', maxLength: 200 } }), effect: 'view' },
  { name: 'log.append', description: 'Display an Agent note or answer; does not execute business actions', args: objectSchema({ title: { type: 'string', maxLength: 200 }, text: { type: 'string', maxLength: 4000 }, kind: { type: 'string', enum: ['note', 'answer'] } }), effect: 'view' },
  { name: 'log.export', description: 'Export displayed history as readable text', args: objectSchema(), effect: 'file' },
] }
function read() { return { view: { filter: filter.value, query: query.value }, total: activity.state.entries.length, dropped: activity.state.dropped, entries: visibleEntries.value.slice(0, 8).map(entry => ({ ...entry, text: entry.text.slice(0, 500), truncated: entry.text.length > 500 })), storage_error: activity.state.storageError } }
async function execute(action: string, args: JsonObject) {
  const descriptor = catalog().find(item => item.name === action); if (!descriptor) throw new Error('Unknown log action')
  interaction.validateArgs(args, descriptor.args)
  if (action === 'log.filter') { filter.value = args.kind; query.value = args.query }
  if (action === 'log.append') activity.append({ source: 'Agent', title: args.title, text: args.text, kind: args.kind, status: args.kind === 'answer' ? 'replied' : 'completed' })
  if (action === 'log.read') { const offset = args.offset || 0; return { entries: visibleEntries.value.slice(offset, offset + 3), total: visibleEntries.value.length, next_offset: offset + 3 < visibleEntries.value.length ? offset + 3 : null } }
  if (action === 'log.export') return { saved: await exportLog() }
  return read()
}
function restore(view: JsonObject) { if (['all', 'operation', 'conversation', 'error'].includes(view.filter)) filter.value = view.filter; if (typeof view.query === 'string') query.value = view.query.slice(0, 200) }
defineExpose({ catalog, read, execute, restore })
</script>
<style scoped>
.workbench-log { padding:12px; display:flex; flex-direction:column; gap:12px; min-width:0; } .log-toolbar { display:flex; flex-wrap:wrap; gap:8px; align-items:end; } label { display:flex; flex-direction:column; gap:4px; } input { flex:1; min-width:140px; } ol { list-style:none; padding:0; margin:0; } li { border-top:1px solid var(--border); padding:12px 0; } header { display:flex; flex-wrap:wrap; gap:8px; align-items:baseline; } time,small,header span { color:var(--muted); font-size:12px; } p { margin:4px 0 0; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.6; font-size:14px; } [data-kind=error] strong { color:var(--danger); }
</style>
