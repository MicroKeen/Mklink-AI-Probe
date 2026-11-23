import { interaction, objectSchema } from './frontendControl'

export interface NumericOptions { unit?: string; precision?: number; stale_ms?: number; valid_path?: string; note?: string; min?: number; max?: number }
export const isMeter = (type?: string) => type === 'gauge' || type === 'bar-meter'
export const isNumeric = (type?: string) => type === 'numeric' || isMeter(type)
export const meterFields = { min: { type: 'number', minimum: -1e12, maximum: 1e12 }, max: { type: 'number', minimum: -1e12, maximum: 1e12 } }
export const numericFields = {
  unit: { type: 'string', maxLength: 32 }, precision: { type: 'integer', minimum: 0, maximum: 6 },
  stale_ms: { type: 'integer', minimum: 250, maximum: 60000 },
  valid_path: { type: 'string', maxLength: 512 }, note: { type: 'string', maxLength: 200 },
}
export const numericDefaults = { unit: '', precision: 0, stale_ms: 2000, valid_path: '', note: '' }
export function validateNumericOptions(options: NumericOptions, type = 'numeric') {
  interaction.validateArgs(options, objectSchema(isMeter(type) ? { ...numericFields, ...meterFields } : numericFields, []))
  if (isMeter(type) && (options.min ?? 0) >= (options.max ?? 100)) throw new Error('量程下限必须小于上限')
}
export interface NumericSample {
  value: number | null; session: string; sequence: string | null; received_at: number | null
  connected: boolean; replay: boolean
}
export interface NumericReading { sample: NumericSample; validity?: NumericSample }

// Only newly accepted source frames renew freshness; neither reads nor paints do.
export function createNumericSamples() {
  let session = crypto.randomUUID(), sequence: bigint | null = null, receivedAt: number | null = null
  let values: Record<string, number> = {}
  return {
    reset() { session = crypto.randomUUID(); sequence = null; receivedAt = null; values = {} },
    accept(next: bigint, latest: Record<string, number>, now = Date.now()) {
      if (sequence !== null && next <= sequence) return
      sequence = next; receivedAt = now; values = { ...latest }
    },
    read(names: string[], connected: boolean, replay: boolean): Record<string, NumericSample> {
      return Object.fromEntries(names.map(name => ['signal:' + name, {
        value: Number.isFinite(values[name]) ? values[name]! : null,
        session, sequence: sequence?.toString() ?? null, received_at: receivedAt, connected, replay,
      }]))
    },
  }
}
export function numericStatus(reading: NumericReading | undefined, options: NumericOptions, now: number) {
  const sample = reading?.sample, validity = reading?.validity
  if (!sample) return '未绑定或来源不可用'
  if (sample.replay) return '回放中 · 实时数值暂停'
  if (!sample.connected) return '已断开'
  if (sample.received_at === null || sample.sequence === null) return '等待采样'
  const age = now - sample.received_at
  if (age < 0 || age >= (options.stale_ms ?? numericDefaults.stale_ms)) return '数据已过期'
  if (options.valid_path && (!validity || !validity.connected || validity.replay || validity.session !== sample.session || validity.sequence !== sample.sequence || validity.value !== 1)) return '待稳定 · 信号无效'
  if (sample.value === null || !Number.isFinite(sample.value)) return '待稳定 · 数值无效'
  return ''
}
