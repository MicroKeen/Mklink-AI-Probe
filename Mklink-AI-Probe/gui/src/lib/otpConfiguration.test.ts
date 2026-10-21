import { describe, expect, it } from 'vitest'
import { customOtpEntries, otpCsv, parseOtpCsv } from './otpConfiguration'
describe('HPM manufacturing tool OTP configuration', () => {
  it('roundtrips the official word,value format and ignores empty/zero values', () => {
    const entries = customOtpEntries(69, 2, '0x80000001, FFFFFFFF')
    expect(parseOtpCsv(otpCsv(entries))).toEqual(entries)
    expect(parseOtpCsv('\uFEFFword,value\r\n69,0x00000000\n70,\n71,00000001')).toEqual([{ word: 71, value: 1 }])
  })
  it.each(['word,value\n68,00000001', 'word,value\n80,00000001', 'word,value\n69,00000001\n69,00000002', 'word,value\n69,0x100000000', 'word,value\n69,00000001,extra', 'word,value\n69,1'])('rejects unsupported or ambiguous configuration %s', text => {
    expect(() => parseOtpCsv(text)).toThrow()
  })
  it('requires an exact, bounded contiguous list before adding any values', () => {
    expect(() => customOtpEntries(79, 2, '00000001,00000002')).toThrow()
    expect(() => customOtpEntries(69, 2, '00000001')).toThrow()
    expect(() => customOtpEntries(69, 1.5, '00000001')).toThrow()
    expect(customOtpEntries(79, 1, '00000001')).toEqual([{ word: 79, value: 1 }])
  })
})
