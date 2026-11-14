import { describe, expect, it, vi } from 'vitest'
import { SystemViewIntervalRing } from './systemViewRing'

describe('SystemViewIntervalRing visible-range lookup', () => {
  it('starts at the first interval whose end overlaps the requested range', () => {
    const ring = new SystemViewIntervalRing(8)
    ring.append(1, 0n, 10n)
    ring.append(2, 20n, 30n)
    ring.append(3, 40n, 50n)

    expect(ring.firstOverlappingIndex(0n)).toBe(0)
    expect(ring.firstOverlappingIndex(15n)).toBe(1)
    expect(ring.firstOverlappingIndex(35n)).toBe(2)
    expect(ring.firstOverlappingIndex(60n)).toBe(3)
  })

  it('keeps binary lookup correct after the ring wraps', () => {
    const ring = new SystemViewIntervalRing(3)
    ring.append(1, 0n, 10n)
    ring.append(2, 20n, 30n)
    ring.append(3, 40n, 50n)
    ring.append(4, 60n, 70n)

    expect(ring.length).toBe(3)
    expect(ring.startTickAt(0)).toBe(20n)
    expect(ring.firstOverlappingIndex(15n)).toBe(0)
    expect(ring.firstOverlappingIndex(55n)).toBe(2)
  })

  it('matches the exhaustive first/last pixel envelope at exact 64-bit ticks', () => {
    const ring = new SystemViewIntervalRing(2000)
    const origin = 9_007_199_254_740_993n
    let tick = origin
    for (let i=0;i<3000;i++) {
      const end = tick + BigInt(i%31+1)
      ring.append(i%9,tick,end,i%3+1)
      tick=end+BigInt(i%7)
    }
    for (const width of [1,3,64,1000,4096]) {
      for (const [start,end] of [[origin,tick], [origin+30000n,tick-1000n], [tick,tick], [tick+1n,tick+9n]]) {
        const first = new Map<number,number>(), last = new Map<number,number>()
        let candidates=0
        const span=end>start?end-start:1n
        for (let i=0;i<ring.length;i++) {
          if (ring.endTickAt(i)<start || ring.startTickAt(i)>end) continue
          candidates++
          const mid=(ring.startTickAt(i)+ring.endTickAt(i))/2n
          const offset=mid<=start?0n:mid>=end?span:mid-start
          const pixel=Math.min(width-1,Number(offset*BigInt(width)/span))
          if (!first.has(pixel)) first.set(pixel,i)
          last.set(pixel,i)
        }
        const expected=[...first].flatMap(([p,i])=>last.get(p)===i?[i]:[i,last.get(p)!])
        const actual=ring.selectEnvelope(start,end,width)
        expect([...actual.logicalIndices.slice(0,actual.count)]).toEqual(expected)
        expect(actual.candidateCount).toBe(candidates)
      }
    }
  })

  it('skips the interior of dense pixels instead of reading every interval', () => {
    const ring=new SystemViewIntervalRing(300_000)
    for (let i=0;i<300_000;i++) ring.append(i%9,BigInt(i*10),BigInt(i*10+9))
    const reads=vi.spyOn(ring,'startTickAt')
    const selection=ring.selectEnvelope(0n,3_000_000n,1000)
    expect(selection.count).toBe(2000)
    expect(selection.candidateCount).toBe(300_000)
    expect(reads.mock.calls.length).toBeLessThan(25_000)
  })
})
