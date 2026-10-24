<script setup lang="ts">
import { HPM_ISP_BAUD_RATES, type HpmIspConfig } from '../types/offlineFlash'
import { tr } from '../composables/useLanguage'
import { useConfirmation } from '../composables/useConfirmation'

const config = defineModel<HpmIspConfig>({ required: true })
const confirm = useConfirmation()
const voltageChoices = [1800, 3300, 5000] as const

async function updateVoltage(value: number, input: HTMLInputElement): Promise<void> {
  if (value === 5000) {
    input.checked = false
    const previous = input.closest('.voltage-options')?.querySelector<HTMLInputElement>(`input[value="${config.value.completion.restore_voltage_mv}"]`)
    if (previous) previous.checked = true
    if (!await confirm(tr(
      '5V 可能永久损坏不耐受 5V 的目标板。仅在确认当前目标硬件支持 5V 时选择。确定选择 5V？',
      '5 V may permanently damage a target that is not 5 V tolerant. Select it only after verifying the connected hardware. Select 5 V?',
    ))) return
    if (config.value.completion.reset !== 'power_cycle') return
  }
  config.value.completion.restore_voltage_mv = value
}
</script>

<template>
  <fieldset class="isp-settings" data-testid="hpm-isp-settings">
    <legend>USART ISP</legend>
    <label>{{ tr('串口速率（baud，8N1）', 'Baud rate (8N1)') }}<select v-model.number="config.baud_rate" data-testid="isp-baud-rate"><option v-for="rate in HPM_ISP_BAUD_RATES" :key="rate" :value="rate">{{ rate === 115200 ? '115200' : `${rate / 1000000}M (${rate})` }} · 8N1</option></select></label>
    <label>{{ tr('握手超时（ms）', 'Handshake timeout (ms)') }}<input v-model.number="config.connect_timeout_ms" type="number" min="1000" max="3600000" /></label>
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
    <label>{{ tr('蜂鸣时长（ms）', 'Beep duration (ms)') }}<input v-model.number="config.completion.beep_duration_ms" data-testid="isp-beep-duration" type="number" min="1" max="10000" step="1" :disabled="!config.completion.beep" /></label>
    <label>{{ tr('下载完成复位', 'Reset on completion') }}
      <select v-model="config.completion.reset" data-testid="isp-reset" @change="config.completion.restore_voltage_mv = config.completion.reset === 'power_cycle' ? 3300 : null">
        <option value="none">{{ tr('不复位', 'No reset') }}</option>
        <option value="software">{{ tr('软件复位', 'Software reset') }}</option>
        <option value="power_cycle">{{ tr('断电复位', 'Power-cycle reset') }}</option>
      </select>
    </label>
    <div v-if="config.completion.reset === 'power_cycle'" class="voltage-setting">
      <span>{{ tr('VCC 恢复电压（默认 3.3V）', 'VCC restore voltage (3.3 V default)') }}</span>
      <div class="voltage-options">
        <label v-for="choice in voltageChoices" :key="choice">
          <input :data-testid="`isp-voltage-${choice}`" type="radio" name="isp-restore-voltage" :value="choice" :checked="config.completion.restore_voltage_mv === choice" @change="updateVoltage(choice, $event.target as HTMLInputElement)" />
          {{ choice / 1000 }}V
        </label>
      </div>
    </div>
    <label v-if="config.completion.reset === 'power_cycle'">{{ tr('断电持续时间（ms）', 'Power-off duration (ms)') }}<input v-model.number="config.completion.power_off_ms" type="number" min="10" max="5000" /></label>
  </fieldset>
</template>

<style scoped>
.isp-settings{margin:10px 0;padding:10px;border:1px solid var(--border);border-radius:5px;font-size:12px}
legend{font-weight:600}p{color:var(--muted);font-size:11px;line-height:1.6}
label{display:grid;grid-template-columns:1fr minmax(100px,1fr);align-items:center;gap:8px;margin:8px 0}
input,select{min-width:0;width:100%;padding:5px;border:1px solid var(--border);border-radius:4px;background:var(--input-bg);color:var(--fg)}
.check{display:flex}.check input{width:auto}summary{cursor:pointer;margin:10px 0}
.voltage-setting{display:grid;gap:7px;margin:10px 0;color:var(--muted)}.voltage-options{display:flex;gap:14px}.voltage-options label{display:flex;gap:5px;margin:0}.voltage-options input{width:auto}
</style>
