import definitions from '../data/hpmOtpProfiles.json'
import type { OtpEntry } from './otpConfiguration'

export interface OtpField {
  name: string
  offsets: number[]
  width: number
  kind: string
  options: { value: number; label: string }[]
}
export interface OtpWord {
  word: number
  category: string
  name: string
  fields: OtpField[]
}
const prefixes: Record<string, keyof typeof definitions> = {
  HPM53: 'HPM5300', HPM62: 'HPM6200', HPM63: 'HPM6300',
  HPM64: 'HPM6700/HPM6400', HPM67: 'HPM6700/HPM6400', HPM68: 'HPM6800',
  HPM6E: 'HPM6E00', HPM6P: 'HPM6P00', HPM5E: 'HPM5E00',
}
export function hpmOtpProfile(part: string): { name: string; words: OtpWord[] } | null {
  const normalized = part.trim().toUpperCase()
  if (!/^HPM[0-9A-Z]{4,16}$/.test(normalized)) return null
  const name = prefixes[normalized.slice(0, 5)]
  return name ? { name, words: definitions[name] } : null
}
export function otpFieldValue(value: number, field: OtpField): string {
  return field.offsets.map(offset => ((BigInt(value) >> BigInt(offset)) & ((1n << BigInt(field.width)) - 1n)).toString(16).toUpperCase()).join(' / ')
}

// HPM5100 has an SDK OTP table but no Manufacturing Tool UART ISP template.
// Tuples are word, bit offset, field width, name (SDK 1.13.0 hpm_otp_table.h).
const sdk51 = Array.from({ length: 128 }, (_, word): OtpWord => ({
  word, category: 'GENERAL', name: '', fields: [],
}))
const fields51: [number, number, number, string][] = [
  [0, 0, 32, 'HARD_LOCK'], [1, 0, 4, 'LIFECYCLE_A'], [1, 28, 4, 'LIFECYCLE_B'],
  [1, 8, 8, 'PUK_REVOKE'], [1, 16, 1, 'JTAG_DISABLE'], [1, 17, 1, 'DEBUG_DISABLE'],
  [1, 19, 1, 'TCU_DISABLE'], [2, 16, 16, 'MONO_EPOCH'], [3, 0, 32, 'SW_VER'],
  [8, 0, 128, 'DIE_TRACE'], [12, 0, 128, 'DEBUG_KEY'], [21, 0, 12, 'TSNS_BASE'],
  [21, 12, 12, 'TSNS_SLOPE'], [21, 24, 1, 'TSNS_BASE_EN'], [21, 25, 1, 'TSNS_SLOPE_EN'],
  [64, 0, 32, 'CHIP_ID'],
  [65, 0, 48, 'MAC0'], [66, 16, 48, 'MAC1'], [68, 0, 16, 'USB_PID'], [68, 16, 16, 'USB_VID'],
  [80, 0, 256, 'PUBLIC_KEY_HASH'], [88, 0, 128, 'UUID'], [96, 0, 128, 'EXIP0_KEY'],
  [100, 0, 128, 'EXIP1_KEY'], [104, 0, 256, 'USER_KEY'], [112, 0, 256, 'MASTER_KEY'],
]
for (const [start, shift, bits, name] of fields51) {
  let category = 'GENERAL'
  if (name.endsWith('_KEY')) category = 'SECRET'
  else if (start <= 3 || name === 'PUBLIC_KEY_HASH') category = 'SECURE'
  else if (['CHIP_ID', 'DIE_TRACE', 'UUID', 'MAC0', 'MAC1', 'USB_PID', 'USB_VID'].includes(name)) category = 'IDENTIFY'
  let word = start, offset = shift, remaining = bits
  while (remaining > 0) {
    const width = Math.min(32 - offset, remaining)
    const definition = sdk51[word++]!
    definition.category = category
    definition.fields.push({ name, offsets: [offset], width, kind: 'none', options: [] })
    remaining -= width
    offset = 0
  }
}
export function hpmJtagOtpProfile(part: string) {
  const normalized = part.trim().toUpperCase()
  if (!/^HPM[A-Z0-9]{4,8}$/.test(normalized)) return null
  return normalized.startsWith('HPM51') ? { name: 'HPM5100', words: sdk51 } : hpmOtpProfile(normalized)
}
// Set precisely the reviewed field, preserving every other bit in the word.
// Repeated offsets (LIFE_CYCLE) must receive the same value.
export function applyOtpFields(base: OtpEntry[], edits: { word: number; field: OtpField; value: string }[]): OtpEntry[] {
  const values = new Map(base.map(item => [item.word, BigInt(item.value)]))
  const changed = new Set<number>()
  for (const edit of edits) {
    if (!/^(?:0x[0-9a-f]+|\d+)$/i.test(edit.value)) throw new Error(`${edit.field.name}: invalid value`)
    const value = BigInt(edit.value), mask = (1n << BigInt(edit.field.width)) - 1n
    if (value > mask) throw new Error(`${edit.field.name}: value exceeds ${edit.field.width} bits`)
    if (!values.has(edit.word)) throw new Error(`Word ${edit.word}: refresh current value first`)
    let word = values.get(edit.word)!
    for (const offset of edit.field.offsets) word = (word & ~(mask << BigInt(offset))) | (value << BigInt(offset))
    values.set(edit.word, word); changed.add(edit.word)
  }
  return [...changed].map(word => ({ word, value: Number(values.get(word)!) })).sort((a, b) => a.word - b.word)
}
