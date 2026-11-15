<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue';
import { X } from '@lucide/vue';
import { tr } from '../composables/useLanguage';
defineProps<{ title: string }>();
const emit = defineEmits<{ close: [] }>();
const dialog = ref<HTMLDialogElement | null>(null);
let previous: HTMLElement | null = null;
onMounted(() => { previous = document.activeElement as HTMLElement; dialog.value?.showModal(); });
onBeforeUnmount(() => { dialog.value?.close(); if (previous?.isConnected) previous.focus(); });
</script>

<template>
  <Teleport to="body">
    <dialog ref="dialog" class="workbench-settings-dialog" :aria-label="title" @cancel.prevent="emit('close')" @click="event => { if (event.target === dialog) emit('close') }">
      <header><h2>{{ title }}</h2><button type="button" :aria-label="tr('关闭配置', 'Close settings')" @click="emit('close')"><X :size="18" /></button></header>
      <slot />
    </dialog>
  </Teleport>
</template>

<style>
.workbench-settings-dialog { margin:auto; margin:auto; width:min(560px,calc(100vw - 40px)); max-height:calc(100vh - 60px); padding:24px; box-sizing:border-box; border:1px solid var(--border); border-radius:10px; background:var(--surface); color:var(--fg); box-shadow:0 20px 70px #0008; }
.workbench-settings-dialog::backdrop { background:rgb(0 0 0 / 55%); }
.workbench-settings-dialog > header { display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:20px; }
.workbench-settings-dialog h2 { margin:0; font-size:18px; }
.workbench-settings-dialog button { min-height:32px; cursor:pointer; }
.workbench-settings-dialog > header button { display:grid; place-items:center; width:32px; border:1px solid var(--border); border-radius:4px; color:var(--fg); background:var(--input-bg); }
.workbench-settings-dialog :is(input,select) { min-height:34px; padding:6px 8px; background:var(--input-bg); color:var(--fg); border:1px solid var(--border); border-radius:4px; }
.workbench-settings-dialog :focus-visible { outline:2px solid var(--accent); outline-offset:3px; }
</style>
