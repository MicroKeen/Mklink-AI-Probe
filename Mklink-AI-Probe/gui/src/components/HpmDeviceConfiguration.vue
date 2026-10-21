<script setup lang="ts">
import { tr } from '../composables/useLanguage'
import HpmUserOtpPanel from './HpmUserOtpPanel.vue'
defineProps<{
  partNumber: string; model: string; readAt?: string
  fields: { id: string; label: string; description: string; bit_width?: number; current: number | string | null; shadow: number | null }[]
}>()
function value(item: number | string | null, width = 32): string {
  return item === null ? '—' : typeof item === 'number' ? `0x${item.toString(16).toUpperCase().padStart(Math.ceil(width / 4), '0')}` : item
}
</script>
<template>
  <section data-testid="hpm-device-configuration">
    <p v-if="readAt" data-testid="configuration-timestamp">{{ tr('读取快照', 'Snapshot') }} · {{ readAt }}</p>
    <div class="configuration-table" v-if="fields.length"><table><thead><tr><th>{{ tr('OTP 字段', 'OTP field') }}</th><th>{{ tr('熔丝值', 'Fuse') }}</th><th>{{ tr('影子值', 'Shadow') }}</th></tr></thead><tbody><tr v-for="field in fields" :key="field.id" :data-testid="`configuration-field-${field.id}`"><td :title="field.description"><b>{{ field.id }}</b><small>{{ field.label }}</small></td><td>{{ value(field.current, field.bit_width) }}</td><td>{{ value(field.shadow, field.bit_width) }}</td></tr></tbody></table></div>
    <p data-testid="otp-reading-help">{{ tr('系统字段只读。熔丝值与影子值分别显示；— 表示未读取。用户区写入与永久写保护在下方配置。', 'System fields are read-only. Fuse and shadow values are shown separately; — means not read. Configure user data and permanent protection below.') }}</p>
    <HpmUserOtpPanel v-if="model === 'V4' && ['HPM5301', 'HPM5301XEGX'].includes(partNumber.toUpperCase())" :part-number="partNumber" :model="model" />
  </section>
</template>
<style scoped>
p{font-size:11px;line-height:1.6;color:var(--muted)}.configuration-table{overflow:auto;max-height:300px;border:1px solid var(--border);border-radius:5px}table{width:100%;border-collapse:collapse;font:11px var(--font-mono)}th,td{text-align:left;padding:8px;border-bottom:1px solid var(--border)}th{background:var(--bg)}small{display:block;margin-top:3px;color:var(--muted)}td:not(:first-child){white-space:nowrap}
</style>
