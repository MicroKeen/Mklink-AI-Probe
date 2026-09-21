<template>
  <div class="toast-container">
    <TransitionGroup name="toast">
      <div
        v-for="t in toasts" :key="t.id"
        :class="['toast', `toast-${t.type}`]"
        @click="dismiss(t.id)"
      >
        <span class="toast-icon">{{ icons[t.type] }}</span>
        <span class="toast-msg">{{ t.message }}</span>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup lang="ts">
import { useToast } from '../composables/useToast'

const { toasts, dismiss } = useToast()

const icons: Record<string, string> = {
  success: '✓',
  error: '✗',
  warn: '⚠',
  info: 'ℹ',
}
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 56px;
  right: 16px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 400px;
}
.toast {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: var(--radius);
  font-size: 13px;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0,0,0,0.12);
  transition: opacity 0.2s, transform 0.2s;
}
.toast-success { background: var(--success-bg); color: var(--success); }
.toast-error   { background: var(--danger-bg); color: var(--danger); }
.toast-warn    { background: var(--warn-bg); color: var(--warn); }
.toast-info    { background: var(--info-bg); color: var(--info); }
.toast-icon { font-weight: 700; flex-shrink: 0; }
.toast-msg { flex: 1; line-height: 1.4; word-break: break-word; }

.toast-enter-active { transition: all 0.2s ease-out; }
.toast-leave-active { transition: all 0.15s ease-in; }
.toast-enter-from { opacity: 0; transform: translateX(40px); }
.toast-leave-to { opacity: 0; transform: translateX(40px); }
</style>
