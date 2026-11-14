<template>
  <aside class="frontend-intent" v-if="open">
    <header><strong>{{ tr('请 Agent 协作', 'Ask Agent') }}</strong><button type="button" @click="emit('close')" :aria-label="tr('关闭', 'Close')">×</button></header>
    <p>{{ pending ? pending.object_id : objectTitle }}</p>
    <form @submit.prevent="submit">
      <select v-model="intent" :disabled="Boolean(pending)" :aria-label="tr('请求类型', 'Request type')"><option value="explain">{{ tr('解释', 'Explain') }}</option><option value="inspect">{{ tr('检查', 'Inspect') }}</option><option value="plan">{{ tr('制定方案', 'Plan') }}</option></select>
      <textarea v-model="message" :disabled="Boolean(pending)" maxlength="4000" required :placeholder="tr('描述需要 Agent 分析的内容…', 'Describe what the Agent should analyze…')" :aria-label="tr('请求内容', 'Request')"></textarea>
      <button class="btn btn-primary" :disabled="sending || !message.trim()" type="submit">{{ pending ? tr('查询并重试原请求', 'Retry original request') : tr('发送给 Agent', 'Send to Agent') }}</button>
    </form>
    <div v-if="pending && canDiscard">
      <p>{{ tr('可以放弃本页的未确认请求。后台已有记录会保留，新的请求需要你重新提交。', 'You may discard this pending request. Existing backend records remain; a new request requires a new submission.') }}</p>
      <button type="button" data-testid="discard-pending-intent" :disabled="sending" @click="discardPending">{{ tr('放弃此未确认请求', 'Discard pending request') }}</button>
    </div>
    <p v-if="error" role="alert">{{ error }}</p>
    <div v-if="request" class="intent-result" role="status"><small>{{ request.status }} · {{ request.request_id }}</small><p>{{ request.reply || tr('请求已保存，等待当前 Agent 读取并答复。', 'Request saved; awaiting an Agent reply.') }}</p></div>
  </aside>
</template>
<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import { tr } from '../../composables/useLanguage'
import { frontendRequest, type JsonObject } from '../../lib/frontendControl'
const props = defineProps<{ open: boolean; objectId: string; objectTitle: string; send: (id: string, object: string, intent: string, message: string, pending?: JsonObject) => Promise<JsonObject> }>()
const emit = defineEmits<{ close: [] }>()
const intent = ref('inspect'), message = ref(''), error = ref(''), sending = ref(false)
const pending = ref<JsonObject | undefined>(), request = ref<JsonObject | null>(null)
const canDiscard = ref(false)
let requestId = '', timer: ReturnType<typeof setTimeout> | undefined, disposed = false
watch(() => props.objectId, () => { if (!pending.value) { message.value = ''; error.value = ''; request.value = null } })
async function poll() {
  if (!request.value || disposed) return
  const id = request.value.request_id
  try {
    const result = await frontendRequest(`intent?request_id=${encodeURIComponent(id)}`)
    if (disposed || request.value?.request_id !== id) return
    request.value = result
  } catch { /* Keep the original receipt visible during a disconnection. */ }
  if (!disposed && request.value?.status !== 'replied') timer = setTimeout(poll, 1500)
}
async function submit() {
  sending.value = true; error.value = ''; canDiscard.value = false
  if (!pending.value) requestId = crypto.randomUUID()
  try {
    request.value = await props.send(requestId, props.objectId, intent.value, message.value.trim(), pending.value)
    pending.value = undefined; message.value = ''; clearTimeout(timer); void poll()
  } catch (cause) {
    pending.value = (cause as { pending?: JsonObject }).pending || pending.value
    canDiscard.value = (cause as { canDiscard?: boolean }).canDiscard === true
    error.value = String(cause)
  }
  finally { sending.value = false }
}
function discardPending() {
  if (!canDiscard.value || sending.value) return
  pending.value = undefined; request.value = null; canDiscard.value = false
  message.value = ''; error.value = ''; requestId = ''; clearTimeout(timer)
}
onUnmounted(() => { disposed = true; clearTimeout(timer) })
</script>
<style scoped>
.frontend-intent { position:fixed; z-index:100; right:20px; bottom:20px; width:min(380px,calc(100vw - 40px)); box-sizing:border-box; max-height:calc(100dvh - 40px); overflow:auto; padding:16px; border:1px solid var(--border); border-radius:10px; background:var(--surface); box-shadow:0 8px 32px #0005; }.frontend-intent header { display:flex; justify-content:space-between; }.frontend-intent header button { border:0; background:transparent; color:var(--fg); cursor:pointer; }.frontend-intent p { font-size:12px; white-space:pre-wrap; word-break:break-word; }.frontend-intent textarea { display:block; width:100%; box-sizing:border-box; min-height:90px; margin:8px 0; resize:vertical; }.intent-result { margin-top:12px; border-top:1px solid var(--border); padding-top:10px; }.intent-result small { word-break:break-all; color:var(--muted); }
</style>
