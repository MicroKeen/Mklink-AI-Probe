<script setup lang="ts">
import { CircleArrowUp, Download, RefreshCw, TriangleAlert } from '@lucide/vue'
import type { AppUpdateState } from '../composables/useAppUpdater'
import { tr } from '../composables/useLanguage'

defineProps<{
  state: AppUpdateState
  version: string
  progress: number | null
  error: string
  blocked?: string
  firmwareBusy?: boolean
  firmwarePending?: boolean
}>()

defineEmits<{
  install: []
  retry: []
  dismiss: []
}>()
</script>

<template>
  <div
    v-if="['downloading', 'ready', 'installing', 'restart-required', 'unavailable', 'error'].includes(state)"
    class="update-banner"
    :class="{ 'update-error': state === 'error' }"
    data-testid="update-banner"
    :role="state === 'error' ? 'alert' : 'status'"
  >
    <TriangleAlert v-if="state === 'error'" :size="15" aria-hidden="true" />
    <Download v-else-if="state === 'downloading'" :size="15" aria-hidden="true" />
    <RefreshCw v-else-if="state === 'installing'" :size="15" class="spin" aria-hidden="true" />
    <CircleArrowUp v-else :size="15" aria-hidden="true" />

    <span v-if="state === 'downloading'">{{ tr('正在下载', 'Downloading') }} v{{ version }}</span>
    <span v-else-if="state === 'ready'">{{ tr(`v${version} 已下载完成`, `v${version} is ready`) }}</span>
    <span v-else-if="state === 'installing'">{{ tr('正在安装更新并重新启动', 'Installing update and restarting') }}</span>
    <span v-else-if="state === 'restart-required'">{{ error }}</span>
    <span v-else-if="state === 'unavailable'">{{ tr('当前平台暂无可用更新，可继续使用现有版本。', 'No update is available for this platform. You can continue using this version.') }}</span>
    <span v-else>{{ tr('更新失败：', 'Update failed: ') }}{{ error }}</span>
    <span v-if="firmwareBusy">{{ tr('固件升级处理中，请完成后再安装上位机更新。', 'Firmware update in progress. Finish it before installing the app update.') }}</span>
    <span v-else-if="blocked" role="alert" data-testid="update-blocked">{{ blocked }}</span>
    <span v-else-if="firmwarePending && ['downloading', 'ready'].includes(state)">{{ tr('建议先更新上位机，重启后再升级固件。', 'Update the app first, then restart and update the firmware.') }}</span>

    <progress
      v-if="state === 'downloading'"
      :value="progress ?? undefined"
      max="1"
      :aria-label="tr('软件更新下载进度', 'Software update download progress')"
    />
    <div v-if="state === 'ready' || state === 'restart-required'" class="update-actions">
      <button
        class="btn btn-sm btn-primary"
        data-testid="install-update"
        type="button"
        :disabled="firmwareBusy"
        @click="$emit('install')"
      >
        <CircleArrowUp :size="13" aria-hidden="true" />
        {{ state === 'restart-required' ? tr('重新启动', 'Restart App') : tr('立即安装', 'Install Now') }}
      </button>
      <button
        v-if="state === 'ready'"
        class="btn btn-sm"
        data-testid="later-update"
        type="button"
        @click="$emit('dismiss')"
      >{{ tr('稍后', 'Later') }}</button>
    </div>
    <button
      v-else-if="state === 'error' || state === 'unavailable'"
      class="btn btn-sm"
      data-testid="retry-update"
      type="button"
      @click="$emit('retry')"
    >
      <RefreshCw :size="13" aria-hidden="true" />
      {{ state === 'unavailable' ? tr('重新检查', 'Check Again') : tr('重试', 'Retry') }}
    </button>
  </div>
</template>

<style scoped>
.update-banner {
  flex: 0 0 34px;
  min-height: 34px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 20px;
  border-bottom: 1px solid var(--border);
  background: var(--info-bg);
  color: var(--info);
  font-size: 12px;
}
.update-error {
  border-bottom-color: var(--border);
  background: var(--danger-bg);
  color: var(--danger);
}
.update-banner span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.update-banner progress {
  width: min(220px, 28vw);
  height: 6px;
  margin-left: auto;
  accent-color: var(--info);
}
.update-actions,
.update-banner > button {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.update-actions { gap: 6px; }
.update-actions button { display: inline-flex; align-items: center; gap: 5px; }
.spin { animation: update-spin 1s linear infinite; }
@keyframes update-spin { to { transform: rotate(360deg); } }
@media (max-width: 640px) {
  .update-banner { padding: 0 12px; }
  .update-banner progress { width: 100px; }
}
</style>
