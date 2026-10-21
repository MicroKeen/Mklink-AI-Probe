import { describe, expect, it } from 'vitest'
import { applyOtpFields, hpmOtpProfile, otpFieldValue } from './hpmOtpProfiles'
import { customOtpEntries, parseOtpCsv } from './otpConfiguration'

describe('official HPM OTP field maps', () => {
  it.each(['HPM5301xEGx', 'HPM6280', 'HPM6360', 'HPM6450', 'HPM6750', 'HPM6880', 'HPM6E80', 'HPM6P81', 'HPM5E31'])('loads all 128 word definitions for %s', part => {
    const profile = hpmOtpProfile(part)!
    expect(profile.words.map(item => item.word)).toEqual(Array.from({ length: 128 }, (_, i) => i))
    for (const word of profile.words) for (const field of word.fields) {
      expect(field.width).toBeGreaterThan(0)
      for (const offset of field.offsets) expect(offset + field.width).toBeLessThanOrEqual(32)
    }
  })
  it('keeps family differences and rejects unsupported families', () => {
    expect(hpmOtpProfile('STM32F407VE')).toBeNull()
    expect(hpmOtpProfile('HPM5100')).toBeNull()
    expect(hpmOtpProfile('HPM5301')!.words[104]!.fields).toHaveLength(0)
    expect(hpmOtpProfile('HPM6750')!.words[104]!.fields[0]!.name).toContain('EXIP1_KEK')
  })
  it('updates both lifecycle nibbles and preserves other security bits', () => {
    const field = hpmOtpProfile('HPM5301')!.words[1]!.fields.find(item => item.name === 'LIFE_CYCLE')!
    const entries = applyOtpFields([{ word: 1, value: 0x10010101 }], [{ word: 1, field, value: '3' }])
    expect(entries).toEqual([{ word: 1, value: 0x30010103 }])
    expect(otpFieldValue(entries[0]!.value, field)).toBe('3 / 3')
    expect(() => applyOtpFields([], [{ word: 1, field, value: '3' }])).toThrow('refresh')
    expect(() => applyOtpFields(entries, [{ word: 1, field, value: '16' }])).toThrow('exceeds')
  })
  it('supports full unsigned words and bounded 128-word CSV without weakening legacy user-only helpers', () => {
    const range = { first: 0, last: 127 }
    expect(customOtpEntries(0, 1, 'FFFFFFFF', range)).toEqual([{ word: 0, value: 0xFFFFFFFF }])
    expect(parseOtpCsv('word,value\n127,0x80000000', range)).toEqual([{ word: 127, value: 0x80000000 }])
    expect(() => customOtpEntries(127, 2, '00000001,00000002', range)).toThrow()
    expect(() => parseOtpCsv('word,value\n128,0x00000001', range)).toThrow()
    expect(() => customOtpEntries(0, 1, 'FFFFFFFF')).toThrow()
  })
})
