import type { TargetRecord } from './onlineFlash'

export interface OfflineDiskStatus {
  probe_id?: string
  probes?: Array<{ probe_id: string; port: string }>
  reason?: string
  available: boolean
  disk_path: string | null
  python_dir: string | null
  flm_dir: string | null
}

export interface OfflineAlgorithmCandidate {
  id: string
  file_name: string
  flash_base: string
  ram_base: string
  source_kind: 'pack' | 'profile' | 'existing'
  source_token: string | null
  origin: string
  available: boolean
  on_probe: boolean
}

export interface OfflineAlgorithmConfig {
  id: string
  file_name: string
  flash_base: string
  ram_base: string
  source_kind: 'upload' | 'pack' | 'profile' | 'existing'
  source_token?: string | null
  upload_index?: number | null
  source_path?: string | null
}

export interface OfflineFirmwareConfig {
  id: string
  file_name: string
  format: 'bin' | 'hex'
  base_address: string | null
  algorithm_id: string
  upload_index?: number | null
  source_path?: string | null
}

export interface HpmOfflineOtp {
  words: { word: number; expected: string; desired: string }[]
  locks: number[]
  expected_hard_lock: string
  confirm_irreversible: boolean
}
export const HPM_ISP_BAUD_RATES = [115200, 1000000, 2000000, 4000000, 5000000, 10000000] as const
export interface HpmIspConfig {
  baud_rate: number
  connect_timeout_ms: number
  command_timeout_ms: number
  flash_base: string
  flash_size: string
  sector_size: number
  memory_id: string
  config_address: string
  nor_options: string[]
  rearm_mode: 'isp_reconnect'
  confirm_reconnect_cycles: boolean
  completion: {
    beep: boolean
    reset: 'none' | 'software' | 'hardware' | 'power_cycle'
    restore_voltage_mv: number | null
    power_off_ms: number
  }
}
export interface OfflineConfigPayload {
  programming_protocol?: 'debug' | 'hpm_rom_isp_uart'
  hpm_isp?: HpmIspConfig
  beep_on_completion?: boolean
  reset_after_download?: boolean
  model: 'V2' | 'V3' | 'V4'
  port?: string | null
  script_name: string
  auto_download_count: number
  wait_idcode_timeout_ms: number
  swd_clock_hz: number
  target_part?: string | null
  board?: string | null
  hpm_flash_cfg?: [string, string, string, string] | null
  erase_all_before_download: boolean
  unlock_before_download: boolean
  lock_after_download: boolean
  security_voltage_mv: number | null
  option_bytes?: Record<string, number | string>
  hpm_user_otp?: HpmOfflineOtp
  algorithms: OfflineAlgorithmConfig[]
  firmwares: OfflineFirmwareConfig[]
}

export interface OfflineSecurityCapability {
  apply_method?: 'ctrl-ap'
  model: string
  part_number: string
  supported: boolean
  unlock_supported: boolean
  lock_supported: boolean
  family: string
  reason: string
  unlock_erases_flash: boolean
  reversible_lock: boolean
  voltage_options_mv: number[]
  default_voltage_mv: number | null
}

export interface OfflinePreview {
  model: 'V2' | 'V3' | 'V4'
  script_name: string
  script: string
}

export interface OfflineDeployResult {
  acquisition?: { errors: string[] }
  status: 'deployed'
  model: 'V2' | 'V3' | 'V4'
  script_name: string
  files: string[]
  file_count?: number
  truncated?: boolean
}

export interface OfflineTriggerResult {
  acquisition?: { errors: string[] }
  status: 'completed' | 'failed' | 'unknown'
  lines: string[]
}

export interface OfflineTargetState {
  query: string
  results: TargetRecord[]
  busy: boolean
  error: string
}
