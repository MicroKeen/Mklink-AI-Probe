// Preserve known LCD messages. CDC events without a timeout stage use a
// generic reason; older progress events have no percentage.
const errors: Record<number, string> = {
  [-1]: 'Invalid settings', [-2]: 'UART I/O error', [-3]: 'timeout',
  [-4]: 'Invalid UART frame', [-5]: 'CRC mismatch', [-6]: 'ROM aborted transfer',
  [-7]: 'ROM rejected command', [-8]: 'Cancelled', [-9]: 'Device busy',
  [-10]: 'BIN file error', [-11]: 'BIN address conflict', [-12]: 'Baud not supported',
}
const errorText = (code: number) => `ISP: ${errors[code] ?? 'Unknown ISP error'}`
const reasons = new Set([...Object.values(errors), 'Unknown ISP error',
  'Upgrade HPMLINK firmware for configurable beep duration'])
// Keep these labels aligned with firmware otp_error_text() on the LCD.
const otpErrors: Record<string, string> = {
  identity_mismatch: 'Target ID mismatch', expected_mismatch: 'Value changed',
  hard_locked: 'OTP is locked', profile_mismatch: 'Wrong chip profile',
  geometry_mismatch: 'OTP layout unsupported', write_outcome_unknown: 'Write uncertain; check OTP',
  readback_mismatch: 'OTP verify mismatch', readback_failed: 'OTP readback failed',
  rom_rejected: 'ROM rejected OTP write', cancelled: 'Cancelled', read_failed: 'OTP read failed',
}
const otpReasons = new Set([...Object.values(otpErrors), 'OTP failed'])

export type IspConnection = 'idle' | 'waiting' | 'connected' | 'cycle_done'

// Waiting for the next board starts while the previous board is still present.
// Keep its connection until firmware confirms loss of ROM responses.
export function hpmIspConnection(previous: IspConnection, line: string): IspConnection {
  if (!line.startsWith('HPM_ISP ')) return previous
  try {
    const event = JSON.parse(line.slice(8))
    if (!event || event.schema !== 1) return previous
    if (event.event === 'connected') return 'connected'
    if (event.event === 'cycle_done') return previous === 'connected' ? 'cycle_done' : previous
    if (event.event === 'disconnected') return 'waiting'
    if (event.event === 'waiting') {
      if (event.stage === 'reconnect' && (previous === 'connected' || previous === 'cycle_done')) return previous
      return 'waiting'
    }
    if (event.event === 'result') return 'idle'
  } catch { /* An invalid record never changes connection state. */ }
  return previous
}

export function hpmIspOutput(lines: string[]): string[] {
  const output: string[] = []
  let otpFailure = false
  for (const raw of lines) {
    const line = raw.trim()
    let text = ''
    if (line.startsWith('HPM_ISP ')) {
      try {
        const event = JSON.parse(line.slice(8))
        if (!event || event.schema !== 1) continue
        const validCount = (value: unknown): value is number =>
          Number.isInteger(value) && Number(value) >= 0 && Number(value) <= 9999
        if (event.event === 'connected') text = 'ISP connected'
        else if (event.event === 'disconnected') text = 'ISP disconnected'
        else if (event.event === 'waiting' && validCount(event.cycle) && validCount(event.total))
          text = event.stage === 'reconnect' ? `ISP next ${event.cycle}/${event.total}: reconnect` : `ISP waiting ${event.cycle}/${event.total}`
        else if (event.event === 'reset_wait') text = 'ISP reset; wait ROM'
        else if (event.event === 'image_begin' && Number.isInteger(event.image_first)
          && Number.isInteger(event.image_last) && Number.isInteger(event.image_total)
          && event.image_first >= 1 && event.image_first <= event.image_last
          && event.image_last <= event.image_total && event.image_total <= 8)
          text = `ISP BIN ${event.image_first}${event.image_last === event.image_first ? '' : `-${event.image_last}`}/${event.image_total}`
        else if (event.event === 'cycle_done' && validCount(event.completed) && validCount(event.total))
          text = `ISP done ${event.completed}/${event.total}`
        else if (event.event === 'result' && Number.isInteger(event.code)
          && validCount(event.completed) && validCount(event.total)) {
          otpFailure = event.code !== 0 && typeof event.otp_reason === 'string' && event.otp_reason !== 'ok'
          text = event.code === 0 ? `ISP OK ${event.completed}/${event.total}`
            : otpFailure ? `ISP OTP: ${otpErrors[event.otp_reason] ?? 'OTP read failed'}` : errorText(event.code)
        }
      } catch { /* Script echoes and malformed protocol records are not LCD output. */ }
    } else {
      // Old SD scripts/firmware may still emit numbers. Render the reason
      // without changing the structured event used to determine success.
      const legacy = /^(?:ISP error (-?\d+) \(\d+\/\d+\)|USART ISP failed: (-?\d+))$/.exec(line)
      const reason = /^ISP(?: config)?: (.+)$/.exec(line)
      const scriptReason = /^USART ISP (config: )?(.+)$/.exec(line)
      const otpReason = /^ISP OTP: (.+)$/.exec(line)
      if (otpReason && otpReasons.has(otpReason[1]!)) text = line
      else if (line === 'Timeout' && output.at(-1)?.startsWith('ISP OTP: ')) text = line
      else if (legacy && !otpFailure) text = errorText(Number(legacy[1] ?? legacy[2]))
      else if (scriptReason && !otpFailure) {
        const message = [...reasons].find(reason => reason.toLowerCase() === scriptReason[2]?.toLowerCase())
          ?? (scriptReason[2] === 'unknown error' ? 'Unknown ISP error' : undefined)
        if (message) text = `ISP${scriptReason[1] ? ' config' : ''}: ${message}`
      } else if ((reason && reasons.has(reason[1]!))
        || /^ISP (?:waiting \d+\/\d+|connected|disconnected|done \d+\/\d+|OK \d+\/\d+)$/.test(line)
        || /^ISP (?:BIN [1-8](?:-[1-8])?\/[1-8]|next \d+\/\d+: reconnect|reset; wait ROM)$/.test(line)
        || /^ISP (?:wait|reconnect|prepare|baud|config|write|baud restore|reset|reset reconnect|UART) timeout$/.test(line)
        || line === 'Check BOOT/UART after reset'
        || line === 'Reconnect target' || line === 'Check UART/BOOT/power'
        || line === 'Upgrade HPMLINK firmware: USART ISP API v1 required') text = line
    }
    if (text && output[output.length - 1] !== text) output.push(text)
  }
  return output
}
