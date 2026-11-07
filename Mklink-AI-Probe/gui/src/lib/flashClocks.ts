export type FlashInterface = 'JTAG' | 'SWD'
export type FlashClocks = Partial<Record<FlashInterface, number[]>>

// Configuration choices when the selected probe has no cached capability report.
const jtagCatalog = [1000, 5000, 10000, 20000, 50000, 100000, 200000, 500000,
  1000000, 2000000, 4000000, 5000000, 10000000, 20000000, 30000000]
const onlineSwd = [1000000, 2000000, 4000000, 8000000, 10000000, 20000000, 30000000]
const offlineSwd = [...jtagCatalog, 8000000].sort((a, b) => a - b)

export function flashClocks(capabilities: FlashClocks | undefined, bus: FlashInterface, offline = false): number[] {
  return capabilities?.[bus] ?? (bus === 'JTAG' ? jtagCatalog : offline ? offlineSwd : onlineSwd)
}

export function formatFlashClock(hz: number): string {
  return hz >= 1000000 ? `${hz / 1000000} MHz` : hz >= 1000 ? `${hz / 1000} kHz` : `${hz} Hz`
}
