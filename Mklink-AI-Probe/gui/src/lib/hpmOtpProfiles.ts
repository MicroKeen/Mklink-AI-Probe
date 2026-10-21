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
