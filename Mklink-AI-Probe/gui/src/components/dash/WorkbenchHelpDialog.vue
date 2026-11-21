<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { tr } from '../../composables/useLanguage'
import { writeClipboard } from '../../lib/writeClipboard'
import WorkbenchSettingsDialog from '../WorkbenchSettingsDialog.vue'

defineEmits<{ close: [] }>()
const title = computed(() => tr('灵活面板帮助', 'Flexible Panels help'))
const sections = computed(() => [
  [tr('观察数据', 'Observe data'), tr('把变量、SuperWatch 波形、RTT 和日志放在同一工作区。“定位面板”可跳到指定卡片；“专注查看”可放大一张卡，按 Esc 返回。', 'Keep variables, SuperWatch waveforms, RTT and logs in one workspace. Use Go to panel to jump to a card, or Enlarge panel to focus on it. Press Esc to return.')],
  [tr('调整布局', 'Arrange panels'), tr('拖动标题移动卡片，拖动边缘调整大小。进入“编辑布局”可添加面板；把标题旁的把手拖到另一张卡的左侧、右侧或中央，可分栏或合并为标签。', 'Drag a title to move a card or an edge to resize it. Open Edit layout to add panels. Drag a title grip to the left, right or center of another card to split the space or group the cards as tabs.')],
  [tr('保存和找回', 'Save and restore'), tr('布局有改动时，“保存布局”会亮起。“另存为”可保存到工程或全局模板库。误关的卡片可从“最近关闭”恢复；保存布局后，关闭记录也会保留。', 'Save layout becomes available when the layout changes. Use Save as to keep a named project layout or a global template. Reopen a card from Recently closed. Saving the layout also keeps this history.')],
])
const examples = computed(() => [
  tr('把变量和波形左右分栏，变量占 7 列、波形占 5 列。', 'Place variables and waveforms side by side, using seven columns for variables and five for waveforms.'),
  tr('在全局模板中搜索“RTT”，先列出匹配项让我选。', 'Search global templates for “RTT” and list the matches so I can choose one.'),
  tr('找回刚才关闭的变量面板，把这次操作结果显示在信息面板。', 'Restore the variable panel I just closed and show the result in the information panel.'),
])
const agentText = computed(() => [
  title.value,
  tr('请先解释灵活面板的用途和下面的示例。等我选定操作后，再按我的要求操作。', 'First explain Flexible Panels and the examples below. Wait for me to choose an operation before carrying it out.'),
  ...sections.value.map(([heading, body]) => heading + '\n' + body),
  tr('我可以这样说', 'Example requests') + '\n' + examples.value.map(line => '• ' + line).join('\n'),
  tr('接入时请使用 MKLink skill 的 references/agent-ui.md。通过 runtime_status 查找目标工程后台，用 gui_control 枚举窗口并核对目标；有多个匹配项时请让我选择。读取窗口快照中的 panels.workbench，再经 gui_frontend_pages 和 gui_frontend_read 核对在线页面、能力和 revision。用该页公布的动作完成我的请求，核对原命令回执和界面结果。', 'For access, use references/agent-ui.md in the MKLink skill. Discover the project runtime with runtime_status and list its windows with gui_control. Ask me to select among multiple matches. Inspect panels.workbench in the window snapshot, then use gui_frontend_pages and gui_frontend_read to verify the online page, its capabilities and revision. Use its advertised actions and verify the original receipt and resulting view.'),
].join('\n\n'))

const status = ref<'idle' | 'copying' | 'copied' | 'manual'>('idle')
const manual = ref<HTMLTextAreaElement>()
async function copyGuide() {
  status.value = 'copying'
  try { await writeClipboard(agentText.value); status.value = 'copied' }
  catch {
    status.value = 'manual'
    await nextTick()
    manual.value?.focus(); manual.value?.select()
  }
}
</script>

<template>
  <WorkbenchSettingsDialog :title="title" :close-label="tr('关闭帮助', 'Close help')" @close="$emit('close')">
    <div class="workbench-help-body" tabindex="0" role="region" :aria-label="tr('操作说明和示例', 'Instructions and examples')">
      <section v-for="[heading, body] in sections" :key="heading"><h3>{{ heading }}</h3><p>{{ body }}</p></section>
      <section><h3>{{ tr('可以这样对 Agent 说', 'Try asking your agent') }}</h3>
        <ul><li v-for="line in examples" :key="line">{{ line }}</li></ul>
      </section>
      <textarea v-if="status === 'manual'" ref="manual" readonly :value="agentText" :aria-label="tr('可手动复制的说明', 'Guide for manual copying')" rows="4"></textarea>
    </div>
    <footer class="workbench-help-footer">
      <button class="btn btn-primary" type="button" :disabled="status === 'copying'" @click="copyGuide">{{ tr('复制给 Agent', 'Copy for agent') }}</button>
      <span role="status">{{ status === 'manual' ? tr('请选择并复制说明文字。', 'Select and copy the guide text.') : status === 'copied' ? tr('已复制，可粘贴到 Agent 会话。', 'Copied. Paste it into your agent chat.') : tr('包含操作说明、示例和接入步骤。', 'Includes instructions, examples and connection steps.') }}</span>
    </footer>
  </WorkbenchSettingsDialog>
</template>

<style scoped>
:global(.workbench-settings-dialog[open]:has(> .workbench-help-body)) { display:flex; flex-direction:column; }
.workbench-help-body { overflow:auto; min-height:0; overscroll-behavior:contain; padding:2px 6px 2px 2px; }
.workbench-help-body section + section { margin-top:16px; }
.workbench-help-body h3 { margin:0 0 4px; font-size:14px; }
.workbench-help-body p,.workbench-help-body ul { margin:0; font-size:14px; line-height:1.55; }
.workbench-help-body ul { padding-inline-start:20px; }
.workbench-help-body li + li { margin-top:4px; }
.workbench-help-body textarea { width:100%; box-sizing:border-box; margin-top:12px; }
.workbench-help-footer { display:flex; flex-wrap:wrap; align-items:center; gap:8px 12px; margin-top:12px; padding-top:12px; border-top:1px solid var(--border); }
.workbench-help-footer span { font-size:12px; color:var(--muted); }
</style>
