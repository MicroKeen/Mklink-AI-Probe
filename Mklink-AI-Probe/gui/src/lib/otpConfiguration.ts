export interface OtpEntry { word: number; value: number }
export const otpHex = (value: number) => `0x${value.toString(16).toUpperCase().padStart(8, '0')}`

export interface OtpRange { first: number; last: number }
const userRange: OtpRange = { first: 69, last: 79 }

function wordIndex(value: string | number, range: OtpRange): number {
  const word = typeof value === 'number' ? value : /^\d+$/.test(value.trim()) ? Number(value) : NaN
  if (!Number.isInteger(word) || word < range.first || word > range.last) throw new Error(`Word ${range.first}–${range.last}`)
  return word
}
function wordValue(value: string): number {
  if (!/^(?:0x)?[\da-f]{8}$/i.test(value.trim())) throw new Error('0x00000000–0xFFFFFFFF')
  return parseInt(value.replace(/^0x/i, ''), 16)
}
export function customOtpEntries(start: number, count: number, text: string, range: OtpRange = userRange): OtpEntry[] {
  wordIndex(start, range)
  if (!Number.isInteger(count) || count < 1 || start + count > range.last + 1) throw new Error(`Word ${range.first}–${range.last}`)
  const values = text.trim().split(/[,，\s]+/)
  if (values.length !== count) throw new Error('Word count ≠ value count')
  return values.map((value, offset) => ({ word: start + offset, value: wordValue(value) }))
}
export function parseOtpCsv(text: string, range: OtpRange = userRange): OtpEntry[] {
  const lines = text.replace(/^\uFEFF/, '').trim().split(/\r?\n/)
  if (lines.shift()?.replace(/\s/g, '').toLowerCase() !== 'word,value') throw new Error('CSV: word,value')
  const entries: OtpEntry[] = [], seen = new Set<number>()
  for (const line of lines) {
    if (!line.trim()) continue
    const cells = line.split(',').map(value => value.trim())
    if (cells.length !== 2) throw new Error('CSV: word,value')
    const word = wordIndex(cells[0]!, range)
    if (seen.has(word)) throw new Error(`Duplicate Word ${word}`)
    seen.add(word)
    if (!cells[1]) continue
    const value = wordValue(cells[1])
    if (value !== 0) entries.push({ word, value })
  }
  if (!entries.length) throw new Error('CSV: no non-zero values')
  return entries.sort((a, b) => a.word - b.word)
}
export function otpCsv(entries: OtpEntry[]): string {
  return ['word,value', ...entries.map(item => `${item.word},${otpHex(item.value)}`)].join('\r\n') + '\r\n'
}
