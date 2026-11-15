<template>
  <aside v-if="compatibility?.warnings.length" class="compatibility-banner" role="status" data-testid="firmware-compatibility">
    <details>
      <summary>{{ tr('下载器固件缺少部分能力，建议升级', 'Some probe capabilities require a firmware upgrade') }} · {{ compatibility.version }}</summary>
      <ul>
        <li v-for="warning in compatibility.warnings" :key="warning.required">
          {{ tr(warning.feature_zh, warning.feature) }}
        </li>
      </ul>
      <p>{{ tr('请选择与下载器型号匹配的固件，升级完成后重新连接。', 'Choose firmware matching the probe model, then reconnect after upgrading.') }}</p>
    </details>
    <button v-if="!remote" class="btn" @click="$emit('openFirmware')">{{ tr('查看固件升级', 'Open Firmware Update') }}</button>
    <span v-else>{{ tr('请联系现场用户升级', 'Ask the site operator to upgrade') }}</span>
  </aside>
</template>

<script setup lang="ts">
import type { FirmwareCompatibility } from '../types/mklink'
import { tr } from '../composables/useLanguage'
defineProps<{ compatibility?: FirmwareCompatibility | null; remote?: boolean }>()
defineEmits<{ openFirmware: [] }>()
</script>

<style scoped>
.compatibility-banner { display: flex; align-items: start; justify-content: space-between; gap: 16px; padding: 10px 20px; background: var(--info-bg); color: var(--info); border-bottom: 1px solid var(--border); font-size: 13px; }
summary { cursor: pointer; }
ul { margin: 10px 0; padding-left: 20px; }
p { margin: 6px 0; }
button { flex-shrink: 0; }
</style>
