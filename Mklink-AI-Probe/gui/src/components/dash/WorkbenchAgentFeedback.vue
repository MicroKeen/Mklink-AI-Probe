<template>
  <div v-if="rejection" :key="rejection.id" class="agent-rejection" role="alert" data-testid="agent-rejection">
    <CircleAlert :size="15" aria-hidden="true" />
    <div><strong>{{ rejection.title }}</strong>
      <span>{{ rejection.detail }}{{ focused && rejection.declinedExit ? tr('，仍在专注查看。', '. Focused view is still open.') : tr('，本次操作未执行。', '. The action was not performed.') }}</span>
    </div>
  </div>
  <template v-else-if="update" :key="update.id">
    <span class="agent-header-wash" aria-hidden="true" />
    <span class="agent-update" role="status" data-testid="agent-update" :aria-label="update.title">
      <span class="update-label">{{ tr('Agent 已更新', 'Agent updated') }}</span>
      <span class="compact-update-label">{{ tr('已更新', 'Updated') }}</span>
    </span>
  </template>
</template>

<script setup lang="ts">
import { CircleAlert } from '@lucide/vue'
import { tr } from '../../composables/useLanguage'
import type { WorkbenchFeedback } from '../../composables/useFrontendWorkbench'

defineProps<{ update?: WorkbenchFeedback; rejection?: WorkbenchFeedback; focused?: boolean }>()
</script>

<style scoped>
.agent-update {
  flex: none;
  color: var(--info);
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  pointer-events: none;
}
.compact-update-label { display: none; }
@media (max-width: 700px) {
  .update-label { display: none; }
  .compact-update-label { display: inline; }
}
.agent-header-wash {
  pointer-events: none;
  position: absolute;
  inset: 0;
  z-index: -1;
  background: var(--info-bg);
}
@media (prefers-reduced-motion: no-preference) {
  .agent-update, .agent-header-wash { animation: update-once 1500ms ease-out both; }
  @keyframes update-once {
    0%, 100% { opacity: 0; }
    12%, 65% { opacity: 1; }
  }
}
.agent-rejection {
  display: flex;
  flex: none;
  align-items: baseline;
  gap: 8px;
  padding: 7px 12px;
  border-inline-start: 3px solid var(--warn);
  color: var(--warn);
  background: var(--warn-bg);
  font-size: 12px;
  line-height: 1.5;
}
.agent-rejection svg { flex: none; align-self: flex-start; margin-top: 2px; }
.agent-rejection > div { display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 8px; overflow-wrap: anywhere; }
.agent-rejection span { color: var(--fg); }
</style>
