<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, inject } from 'vue';
import { guiPanelScopeKey } from '../lib/guiAutomation';
const scope = inject(guiPanelScopeKey, null);
import { X } from '@lucide/vue';
import { tr } from '../composables/useLanguage';
defineProps<{ title: string; closeLabel?: string }>();
const emit = defineEmits<{ close: [] }>();
const dialog = ref<HTMLDialogElement | null>(null);
let previous: HTMLElement | null = null;
function backdropClick(event: MouseEvent) {
  if (event.target !== dialog.value || !dialog.value) return;
  const box = dialog.value.getBoundingClientRect();
  if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) emit('close');
}
onMounted(() => { previous = dialog.value?.ownerDocument.activeElement as HTMLElement; dialog.value?.showModal(); });
onBeforeUnmount(() => { dialog.value?.close(); if (previous?.isConnected) previous.focus(); });
</script>

<template>
  <Teleport :to="scope?.ownerDocument?.().body || 'body'">
    <dialog ref="dialog" class="workbench-settings-dialog" :data-gui-panel-owner="scope?.id" :aria-label="title" @cancel.prevent="emit('close')" @click="backdropClick">
      <header><h2>{{ title }}</h2><button type="button" :aria-label="closeLabel || tr('关闭配置', 'Close settings')" @click="emit('close')"><X :size="18" /></button></header>
      <slot />
    </dialog>
  </Teleport>
</template>

<style>
.workbench-settings-dialog { margin:auto; width:min(560px,calc(100vw - 40px)); max-height:calc(100vh - 60px); padding:24px; box-sizing:border-box; border:1px solid var(--border); border-radius:10px; background:var(--surface); color:var(--fg); box-shadow:0 20px 70px #0008; }
.workbench-settings-dialog::backdrop { background:rgb(0 0 0 / 55%); }
.workbench-settings-dialog > header { display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:20px; }
.workbench-settings-dialog h2 { margin:0; min-width:0; overflow-wrap:anywhere; font-size:18px; }
.workbench-settings-dialog button { min-height:32px; cursor:pointer; }
.workbench-settings-dialog > header button { display:grid; place-items:center; align-self:flex-start; flex-shrink:0; width:32px; border:1px solid var(--border); border-radius:4px; color:var(--fg); background:var(--input-bg); }
.workbench-settings-dialog :is(input,select) { background:var(--input-bg); color:var(--fg); border:1px solid var(--border); border-radius:4px; }
.workbench-settings-dialog :focus-visible { outline:2px solid var(--accent); outline-offset:3px; }
</style>
