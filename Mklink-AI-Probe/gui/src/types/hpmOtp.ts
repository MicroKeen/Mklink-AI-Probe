export interface HpmIspOtpSnapshot {
  part_number: string
  chip_id: number
  hard_lock: number
  read_at: string
  source: string
  words: { word: number; current: number; shadow: number | null; locked: boolean | null }[]
}
