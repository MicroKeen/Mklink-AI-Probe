/** Exact retained-duration histogram; duplicate durations need no sorting. */
export class SystemViewDurations {
  private readonly frequencies = new Map<number, number>()
  private sorted: number[] | null = null
  private count = 0
  private total = 0

  add(value: number): void {
    const count = this.frequencies.get(value) || 0
    if (!count) this.sorted = null
    this.frequencies.set(value, count + 1)
    this.count++
    this.total += value
  }

  remove(value: number): void {
    const count = this.frequencies.get(value)
    if (!count) throw new RangeError('duration is not retained')
    if (count === 1) {
      this.frequencies.delete(value)
      this.sorted = null
    } else this.frequencies.set(value, count - 1)
    this.count--
    this.total -= value
  }

  summary(openDuration?: number) {
    const extra = openDuration !== undefined && openDuration > 0 ? openDuration : undefined
    const count = this.count + (extra === undefined ? 0 : 1)
    if (!this.sorted) this.sorted = [...this.frequencies.keys()].sort((a, b) => a - b)
    const ranks = [0, ...[0.25, 0.5, 0.75].flatMap(q => {
      const rank = Math.max(0, count - 1) * q
      return [Math.floor(rank), Math.ceil(rank)]
    }), Math.max(0, count - 1)]
    const values: number[] = []
    const requests = ranks.map((rank, index) => ({ rank, index })).sort((a,b) => a.rank-b.rank)
    let cumulative = 0
    let rankIndex = 0
    let extraPending = extra !== undefined
    const accept = (value: number, frequency: number) => {
      cumulative += frequency
      while (rankIndex < requests.length && requests[rankIndex]!.rank < cumulative) {
        values[requests[rankIndex++]!.index] = value
      }
    }
    for (const value of this.sorted) {
      if (extraPending && extra! <= value) { accept(extra!, 1); extraPending = false }
      accept(value, this.frequencies.get(value)!)
      if (rankIndex === ranks.length) break
    }
    if (extraPending) accept(extra!, 1)
    const quantile = (q: number, index: number) => {
      const fraction = Math.max(0, count - 1) * q % 1
      const lower = values[index] || 0
      return lower + ((values[index + 1] || 0) - lower) * fraction
    }
    return {
      count, totalTicks: this.total + (extra || 0), minTicks: values[0] || 0,
      p25Ticks: quantile(0.25, 1), p50Ticks: quantile(0.5, 3),
      p75Ticks: quantile(0.75, 5), maxTicks: values[7] || 0,
    }
  }
}
