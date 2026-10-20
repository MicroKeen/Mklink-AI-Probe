<script setup lang="ts">
import { HPM_ISP_BAUD_RATES, type HpmIspConfig } from '../types/offlineFlash'
import { tr } from '../composables/useLanguage'

const config = defineModel<HpmIspConfig>({ required: true })
defineProps<{ count: number }>()
</script>

<template>
  <fieldset class="isp-settings" data-testid="hpm-isp-settings">
    <legend>USART ISP</legend>
    <p>{{ tr('使用下载器独立 UART 接口，目标须进入 ROM ISP。仅支持启用 HPMLINK 的 V4 固件。', 'Use the probe’s dedicated UART port with the target in ROM ISP. Requires HPMLINK-enabled V4 firmware.') }}</p>
    <label>{{ tr('串口速率（baud，8N1）', 'Baud rate (8N1)') }}<select v-model.number="config.baud_rate" data-testid="isp-baud-rate"><option v-for="rate in HPM_ISP_BAUD_RATES" :key="rate" :value="rate">{{ rate === 115200 ? '115200' : `${rate / 1000000}M (${rate})` }} · 8N1</option></select></label>
    <p>{{ tr('档位依据下载器 UART 时钟分频设置，目标 ROM 是否支持以执行结果为准。配置不支持时停止，不自动回退。', 'Rates match the probe UART clock dividers. Target ROM support is checked during execution. Unsupported configurations stop without automatic fallback.') }}</p>
    <p v-if="config.baud_rate !== 115200">{{ tr('高速下载中断后，如无法重新握手，请给目标重新上电恢复默认速率。', 'If an interrupted high-speed transfer prevents reconnection, power-cycle the target to restore its default baud rate.') }}</p>
    <label>{{ tr('握手超时（ms）', 'Handshake timeout (ms)') }}<input v-model.number="config.connect_timeout_ms" type="number" min="1000" max="3600000" /></label>
    <label>{{ tr('Flash 容量（字节）', 'Flash size (bytes)') }}<input v-model="config.flash_size" data-testid="isp-flash-size" :placeholder="tr('按板卡填写，如 0x800000', 'Enter board capacity, e.g. 0x800000')" required /></label>
    <p>{{ tr('握手成功后自动烧录。多轮模式等待目标退出 ISP，再重新握手；无法识别是否换了芯片。', 'Programming starts after a successful handshake. Subsequent rounds wait for the target to leave ISP and reconnect; this does not identify a different chip.') }}</p>
    <label v-if="count > 1" class="check">
      <input v-model="config.confirm_reconnect_cycles" type="checkbox" data-testid="isp-confirm-cycles" />
      {{ tr('我选择等待目标退出 ISP 后重新握手开始下一轮（不识别是否换板）', 'Start the next round after the target leaves ISP and reconnects (does not identify board changes)') }}
    </label>
    <details>
      <summary>{{ tr('Flash 配置', 'Flash configuration') }}</summary>
      <label>Memory ID<input v-model="config.memory_id" /></label>
      <label>{{ tr('命令超时（ms）', 'Command timeout (ms)') }}<input v-model.number="config.command_timeout_ms" type="number" min="1000" max="120000" /></label>
      <label>{{ tr('Flash 基址', 'Flash base') }}<input v-model="config.flash_base" /></label>
      <label>{{ tr('擦除扇区（字节）', 'Erase sector (bytes)') }}<input v-model.number="config.sector_size" type="number" min="256" max="65536" /></label>
      <label>{{ tr('配置 RAM 地址', 'Configuration RAM address') }}<input v-model="config.config_address" /></label>
      <label v-for="(_, index) in config.nor_options" :key="index">{{ index === 0 ? 'NOR header' : `NOR option ${index}` }}<input v-model="config.nor_options[index]" /></label>
      <p>{{ tr('请核对板级 NOR 配置。JTAG 配置中的控制器基址不能作为 NOR option。', 'Verify board-specific NOR options. The controller base in JTAG configuration is not a NOR option.') }}</p>
    </details>
    <p>{{ tr('ROM 自动擦除并内部校验；以写入命令最终成功状态为准。', 'ROM automatically erases and verifies internally; completion requires the final successful write status.') }}</p>
    <label class="check"><input v-model="config.completion.beep" type="checkbox" />{{ tr('下载完成响蜂鸣器', 'Beep on completion') }}</label>
    <label>{{ tr('下载完成复位', 'Reset on completion') }}
      <select v-model="config.completion.reset" data-testid="isp-reset" @change="config.completion.restore_voltage_mv = null">
        <option value="none">{{ tr('不复位', 'No reset') }}</option>
        <option value="software">{{ tr('软件复位', 'Software reset') }}</option>
        <option value="hardware">{{ tr('硬件复位', 'Hardware reset') }}</option>
        <option value="power_cycle">{{ tr('断电复位', 'Power-cycle reset') }}</option>
      </select>
    </label>
    <template v-if="config.completion.reset === 'power_cycle'">
      <label>{{ tr('恢复电压（mV）', 'Restore voltage (mV)') }}<input v-model.number="config.completion.restore_voltage_mv" data-testid="isp-voltage" type="number" min="1201" max="5499" required :placeholder="tr('填写目标允许的电压', 'Enter the target’s supported voltage')" /></label>
    </template>
    <label v-if="config.completion.reset === 'power_cycle' || config.completion.reset === 'hardware'">{{ tr('复位持续时间（ms）', 'Reset duration (ms)') }}<input v-model.number="config.completion.power_off_ms" type="number" min="10" max="5000" /></label>
  </fieldset>
</template>

<style scoped>
.isp-settings{margin:10px 0;padding:10px;border:1px solid var(--border);border-radius:5px;font-size:12px}
legend{font-weight:600}p{color:var(--muted);font-size:11px;line-height:1.6}
label{display:grid;grid-template-columns:1fr minmax(100px,1fr);align-items:center;gap:8px;margin:8px 0}
input,select{min-width:0;width:100%;padding:5px;border:1px solid var(--border);border-radius:4px;background:var(--input-bg);color:var(--fg)}
.check{display:flex}.check input{width:auto}summary{cursor:pointer;margin:10px 0}
</style>
