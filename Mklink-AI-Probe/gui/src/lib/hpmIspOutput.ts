// Match hpm_isp_job.c's LCD console messages; CDC progress events do not
// contain the percentage shown by the separate LCD progress signal.
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
            : `ISP error ${event.code} (${event.completed}/${event.total})`
      } catch { /* Script echoes and malformed protocol records are not LCD output. */ }
    } else if (/^ISP (?:waiting \d+\/\d+|connected|done \d+\/\d+|OK \d+\/\d+|error -?\d+ \(\d+\/\d+\))$/.test(line)
      || /^USART ISP failed: -?\d+$/.test(line)
      || line === 'Upgrade HPMLINK firmware: USART ISP API v1 required') text = line
    if (text && output[output.length - 1] !== text) output.push(text)
  }
  return output
}
