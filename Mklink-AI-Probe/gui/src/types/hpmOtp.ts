export interface HpmIspOtpSnapshot {
  part_number: string
  chip_id: number
  hard_lock: number
  read_at: string
  source: string
  words: { word: number; current: number; shadow: number | null; locked: boolean | null }[]
}

export interface HpmIspOtpChange {
  word: number
  expected: number
  desired: string
}

export interface HpmIspOtpPlan {
  plan_id: string | null
  word: number
  expected: number
  desired: number
  delta: number
  expires_in: number
  qualified: boolean
  write_supported: boolean
  reason: string | null
  before: number | null
}
