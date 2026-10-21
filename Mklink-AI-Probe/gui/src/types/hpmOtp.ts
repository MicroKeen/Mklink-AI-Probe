export interface HpmIspOtpSnapshot {
  part_number: string
  chip_id: number
  rom_version?: number
  soc_revision?: number
  capability?: string
  hard_lock: number
  read_at: string
  source: string
  words: { word: number; current: number | null; shadow: number | null; locked: boolean | null }[]
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

export interface HpmIspOtpBatchPlan {
  plan_id: string | null
  changes: HpmIspOtpPlan[]
  qualified: boolean
  write_supported: boolean
  expires_in: number
}
