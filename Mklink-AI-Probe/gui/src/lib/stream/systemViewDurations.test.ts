import { describe, expect, it } from 'vitest'
import { SystemViewDurations } from './systemViewDurations'

function reference(input: number[]) {
  const values = [...input].sort((a, b) => a - b)
  const q = (p: number) => {
    const rank = (values.length - 1) * p
    const low = Math.floor(rank)
    return !values.length ? 0 : values[low]! + (values[Math.ceil(rank)]! - values[low]!) * (rank - low)
  }
  return { count: values.length, totalTicks: values.reduce((a,b) => a+b, 0),
    minTicks: values[0] || 0, p25Ticks: q(.25), p50Ticks: q(.5), p75Ticks: q(.75), maxTicks: values.at(-1) || 0 }
}

describe('retained SystemView duration statistics', () => {
  it('matches exact sorting across duplicate values, eviction and an open interval', () => {
    const durations = new SystemViewDurations()
    const retained: number[] = []
    expect(durations.summary()).toEqual(reference([]))
    for (let i=0;i<3000;i++) {
      const value = (i * 7919 % 121) + 1
      if (retained.length === 100) durations.remove(retained.shift()!)
      retained.push(value); durations.add(value)
      if (i % 7 === 0) {
        expect(durations.summary()).toEqual(reference(retained))
        for (const open of [1,17,121,150]) expect(durations.summary(open)).toEqual(reference([...retained,open]))
      }
    }
    for (const value of retained) durations.remove(value)
    expect(durations.summary()).toEqual(reference([]))
    expect(durations.summary(42)).toEqual(reference([42]))
  })
})
