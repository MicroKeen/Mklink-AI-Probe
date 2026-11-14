import { describe, expect, it } from 'vitest'
import { LiveFollowClock } from '../svTimeline'

describe('live viewport presentation clock', () => {
  it('keeps advancing between jittery batches without running ahead of received data', () => {
    const clock = new LiveFollowClock(10_000_000, 0, 1000)
    let delivery = 0, latest = 10_000_000, previous = latest
    const steps: number[] = []
    for (let now=10;now<=5000;now+=10) {
      if (now >= delivery) {
        latest = 10_000_000 + now * 1000
        clock.receive(latest, now)
        delivery = now + [50,80,40,120,60][Math.floor(now/10)%5]!
      }
      const current = clock.advance(now, 10_000_000)
      expect(current).toBeGreaterThanOrEqual(previous)
      expect(current).toBeLessThanOrEqual(latest)
      if (now>1500) steps.push(current-previous)
      previous = current
    }
    expect(Math.min(...steps)).toBeGreaterThan(6000)
    expect(Math.max(...steps)).toBeLessThan(14000)
    expect(latest-previous).toBeLessThan(300_000)
    for (let now=5010;now<6000;now+=10) previous=clock.advance(now,10_000_000)
    expect(previous).toBe(latest) // a stopped source cannot invent more time
  })

  it('catches up a returning tab without exceeding the source or changing span', () => {
    const clock = new LiveFollowClock(1_000_000,0,1000)
    clock.receive(6_000_000,5000)
    const end=clock.advance(5000,500_000)
    expect(end).toBeGreaterThan(5_800_000)
    expect(end).toBeLessThanOrEqual(6_000_000)
  })
})
