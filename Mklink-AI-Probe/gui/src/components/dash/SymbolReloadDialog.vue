<script setup lang="ts">
import { tr } from '../../composables/useLanguage'
defineProps<{ busy: boolean; rtt?: boolean }>()
defineEmits<{ later: []; confirm: [] }>()
</script>

<template>
  <div class="overlay" @click.self="$emit('later')" @keydown.esc="$emit('later')">
    <section role="dialog" aria-modal="true" :aria-label="tr('固件文件已更新', 'Firmware file updated')" data-testid="reload-symbols-dialog">
      <h3>{{ tr('固件文件已更新', 'Firmware file updated') }}</h3>
      <p>{{ rtt ? tr('是否重新解析 RTT 符号？请先确认新固件已下载到目标板。', 'Reparse RTT symbols? Make sure the new firmware is on the target first.') : tr('是否重新加载变量列表？请先确认新固件已下载到目标板。', 'Reload the variable list? Make sure the new firmware is on the target first.') }}</p>
      <footer>
        <button type="button" class="btn btn-secondary" data-testid="reload-symbols-later" @click="$emit('later')">{{ tr('稍后', 'Later') }}</button>
        <button type="button" class="btn btn-primary" data-testid="reload-symbols-confirm" :disabled="busy" @click="$emit('confirm')">{{ rtt ? tr('重新解析', 'Reparse') : tr('重新加载变量', 'Reload variables') }}</button>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.overlay { position: fixed; z-index: 1000; inset: 0; display: grid; place-items: center; padding: 20px; background: rgb(0 0 0 / 45%); }
section { width: min(620px, 100%); padding: 16px; border: 1px solid var(--border); background: var(--surface); box-shadow: 0 16px 50px rgb(0 0 0 / 25%); }
footer { display: flex; justify-content: flex-end; gap: 8px; }
</style>
