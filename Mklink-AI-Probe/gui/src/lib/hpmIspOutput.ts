// Preserve known LCD messages. CDC events without a timeout stage use a
// generic reason; progress events do not contain the LCD's percentage.
const errors: Record<number, string> = {
  [-1]: 'Invalid settings', [-2]: 'UART I/O error', [-3]: 'timeout',
  [-4]: 'Invalid UART frame', [-5]: 'CRC mismatch', [-6]: 'ROM aborted transfer',
  [-7]: 'ROM rejected command', [-8]: 'Cancelled', [-9]: 'Device busy',
  [-10]: 'BIN file error', [-11]: 'BIN address conflict', [-12]: 'Baud not supported',
}
const errorText = (code: number) => `ISP: ${errors[code] ?? 'Unknown ISP error'}`
const reasons = new Set([...Object.values(errors), 'Unknown ISP error'])

export function hpmIspOutput(lines: string[]): string[] {
  const output: string[] = []
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
        else if (event.event === 'waiting' && validCount(event.cycle) && validCount(event.total))
          text = `ISP waiting ${event.cycle}/${event.total}`
        else if (event.event === 'cycle_done' && validCount(event.completed) && validCount(event.total))
          text = `ISP done ${event.completed}/${event.total}`
        else if (event.event === 'result' && Number.isInteger(event.code)
          && validCount(event.completed) && validCount(event.total))
          text = event.code === 0 ? `ISP OK ${event.completed}/${event.total}`
            : errorText(event.code)
      } catch { /* Script echoes and malformed protocol records are not LCD output. */ }
    } else {
      // Old SD scripts/firmware may still emit numbers. Render the reason
      // without changing the structured event used to determine success.
      const legacy = /^(?:ISP error (-?\d+) \(\d+\/\d+\)|USART ISP failed: (-?\d+))$/.exec(line)
      const reason = /^ISP(?: config)?: (.+)$/.exec(line)
      const scriptReason = /^USART ISP (config: )?(.+)$/.exec(line)
      if (legacy) text = errorText(Number(legacy[1] ?? legacy[2]))
      else if (scriptReason) {
        const message = [...reasons].find(reason => reason.toLowerCase() === scriptReason[2]?.toLowerCase())
          ?? (scriptReason[2] === 'unknown error' ? 'Unknown ISP error' : undefined)
        if (message) text = `ISP${scriptReason[1] ? ' config' : ''}: ${message}`
      } else if ((reason && reasons.has(reason[1]!))
        || /^ISP (?:waiting \d+\/\d+|connected|done \d+\/\d+|OK \d+\/\d+)$/.test(line)
        || /^ISP (?:wait|reconnect|prepare|baud|config|write|baud restore|reset|UART) timeout$/.test(line)
        || line === 'Reconnect target' || line === 'Check UART/BOOT/power'
        || line === 'Upgrade HPMLINK firmware: USART ISP API v1 required') text = line
    }
    if (text && output[output.length - 1] !== text) output.push(text)
  }
  return output
}
