import defaults from '../../../mklink/hpm_flash_defaults.json'

export type HpmFlashWords = [string, string, string, string]
export const HPM_FLASH_FIELDS = ['header', 'opt0', 'opt1', 'xpi_base_addr'] as const

export function hpmFlashPreset(target: string): { board: string; words: HpmFlashWords } {
  const part = target.trim().toLowerCase()
  const board = defaults.targets.find(([prefix]) => part.startsWith(prefix!))?.[1] || ''
  const words = (defaults.boards as Record<string, string[]>)[board]
  return { board, words: words ? [...words] as HpmFlashWords : ['', '', '', ''] }
}

export function parseHpmFlashWords(value: unknown): HpmFlashWords {
  if (!Array.isArray(value) || value.length !== 4 || !value.every(word =>
    typeof word === 'string' && /^0x[\da-f]{1,8}u?$/i.test(word.trim()),
  )) throw new Error('Invalid HPM Flash configuration')
  return value.map(word => word.trim()) as HpmFlashWords
}

export function parseHpmFlashFile(text: string, target: string): HpmFlashWords {
  const data = JSON.parse(text)
  if (data?.schema_version !== 1 || typeof data.target_part !== 'string'
    || data.target_part.trim().toLowerCase() !== target.trim().toLowerCase()) {
    throw new Error('HPM Flash configuration target or schema mismatch')
  }
  return parseHpmFlashWords(data.hpm_flash_cfg)
}

export function hpmFlashFile(target: string, words: HpmFlashWords): string {
  return JSON.stringify({ schema_version: 1, target_part: target, hpm_flash_cfg: parseHpmFlashWords(words) }, null, 2) + '\n'
}
