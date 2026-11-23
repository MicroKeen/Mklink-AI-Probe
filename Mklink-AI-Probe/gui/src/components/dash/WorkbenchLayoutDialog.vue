<script setup lang="ts">
import { onMounted, ref } from 'vue';
import WorkbenchSettingsDialog from '../WorkbenchSettingsDialog.vue';
import { tr } from '../../composables/useLanguage';

export interface SavedLayout { name: string; revision: number; updated_at: number; panel_count: number; builtin?: boolean }
type Scope = 'project' | 'global';
const props = defineProps<{
  mode: 'save' | 'load';
  search: (query: string, scope: Scope) => Promise<{ layouts: SavedLayout[]; location: string }>;
  save: (name: string, revision: number, scope: Scope) => Promise<unknown>;
  load: (name: string, scope: Scope) => Promise<unknown>;
}>();
const emit = defineEmits<{ close: []; restore: [] }>();
const query = ref(''), name = ref(''), revision = ref(0), entries = ref<SavedLayout[]>([]), busy = ref(false), error = ref('');
const scope = ref<Scope>('project'), location = ref('');
async function search() {
  busy.value = true; error.value = '';
  entries.value = [];
  if (props.mode === 'load' || revision.value > 0) name.value = '';
  revision.value = 0;
  try { const result = await props.search(query.value, scope.value); entries.value = result.layouts; location.value = result.location; }
  catch (cause) { error.value = String(cause); }
  finally { busy.value = false; }
}
function select(entry: SavedLayout) { name.value = entry.name; revision.value = entry.revision; }
function changeScope() { name.value = ''; revision.value = 0; entries.value = []; location.value = ''; void search(); }
async function submit() {
  busy.value = true; error.value = '';
  try {
    if (props.mode === 'save') await props.save(name.value.trim(), revision.value, scope.value);
    else await props.load(name.value, scope.value);
    emit('close');
  } catch (cause) { error.value = String(cause); }
  finally { busy.value = false; }
}
onMounted(search);
</script>

<template>
  <WorkbenchSettingsDialog :title="mode === 'save' ? tr('另存布局', 'Save named layout') : tr('加载布局', 'Load layout')" @close="!busy && emit('close')">
    <div class="layout-library" :aria-busy="busy">
      <label>{{ tr('保存位置', 'Storage location') }}<select v-model="scope" :disabled="busy" @change="changeScope"><option value="project">{{ tr('当前工程（默认）', 'Current project (default)') }}</option><option value="global">{{ tr('全局模板', 'Global templates') }}</option></select></label>
      <p class="layout-location">{{ location }}</p>
      <p v-if="scope === 'global'">{{ tr('全局模板可跨工程使用。变量名和操作绑定会保留，加载到其他工程后请核对。预置模板只读，可用新名称另存。', 'Templates are shared across projects. Verify retained signal names and bindings in the destination project. Built-in templates are read-only; save a copy with a new name.') }}</p>
      <form class="layout-search" @submit.prevent="search">
        <label>{{ tr('搜索布局', 'Search layouts') }}<input v-model="query" type="search" maxlength="80" :disabled="busy" /></label>
        <button class="btn btn-secondary" :disabled="busy">{{ tr('搜索', 'Search') }}</button>
      </form>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="!entries.length && !busy">{{ tr('没有匹配的布局。', 'No matching layouts.') }}</p>
      <ul class="layout-results" :aria-label="tr('已保存布局', 'Saved layouts')">
        <li v-for="entry in entries" :key="entry.name">
          <button type="button" :disabled="busy || (mode === 'save' && entry.builtin)" :aria-pressed="name === entry.name && revision === entry.revision" @click="select(entry)">
            <strong>{{ entry.name }}</strong><small>{{ entry.panel_count }} {{ tr('个面板', 'panels') }} · {{ entry.builtin ? tr('预置模板', 'Built-in template') : new Date(entry.updated_at * 1000).toLocaleString() }}</small>
          </button>
        </li>
      </ul>
      <form class="layout-submit" @submit.prevent="submit">
        <label v-if="mode === 'save'">{{ tr('布局名称', 'Layout name') }}<input v-model="name" maxlength="80" required :disabled="busy" @input="revision = 0" /></label>
        <p v-if="mode === 'save'">{{ revision ? tr('将覆盖选中的已保存布局；其他窗口的新修改会阻止覆盖。', 'Replaces the selected layout; concurrent changes prevent overwriting.') : tr('输入新名称保存；如需覆盖，请先选择上方已有布局。', 'Enter a new name, or select a saved layout above to replace it.') }}</p>
        <p v-else>{{ tr('加载会替换当前未保存的面板配置，不会连接设备或启动采集。', 'Loading replaces unsaved panel settings without connecting devices or starting acquisition.') }}</p>
        <div class="layout-buttons">
          <button class="btn btn-primary" :disabled="busy || !name.trim()">{{ mode === 'load' ? tr('加载选中布局', 'Load selected layout') : revision ? tr('更新选中布局', 'Update selected layout') : tr('保存新布局', 'Save new layout') }}</button>
          <button v-if="mode === 'load'" type="button" class="btn btn-secondary" :disabled="busy" @click="emit('restore')">{{ tr('恢复最近保存的当前布局', 'Restore last current layout') }}</button>
          <button type="button" class="btn btn-secondary" :disabled="busy" @click="emit('close')">{{ tr('取消', 'Cancel') }}</button>
        </div>
      </form>
    </div>
  </WorkbenchSettingsDialog>
</template>

<style scoped>
.layout-library { display:flex; flex-direction:column; gap:16px; }
.layout-library p { margin:0; color:var(--muted); font-size:13px; overflow-wrap:anywhere; }
.layout-library [role=alert] { color:var(--danger); }
.layout-library label { display:flex; flex-direction:column; gap:8px; min-width:0; }
.layout-library input { height:var(--control-height,32px); min-width:0; width:100%; padding:4px 8px; box-sizing:border-box; }
.layout-search { display:flex; align-items:flex-end; gap:8px; }.layout-search label { flex:1; }
.layout-library .btn { min-height:var(--control-height,32px); margin:0; }
.layout-results { list-style:none; margin:0; padding:0; max-height:240px; overflow:auto; display:flex; flex-direction:column; gap:8px; }
.layout-results button { width:100%; height:auto; min-height:56px; text-align:start; border:1px solid var(--border); border-radius:6px; background:var(--input-bg); color:var(--fg); padding:10px 12px; overflow-wrap:anywhere; }
.layout-results small { display:block; color:var(--muted); margin-top:4px; }.layout-results [aria-pressed=true] { border-color:var(--accent); }
.layout-submit { display:flex; flex-direction:column; gap:12px; }.layout-buttons { display:flex; flex-wrap:wrap; gap:8px; }
</style>
