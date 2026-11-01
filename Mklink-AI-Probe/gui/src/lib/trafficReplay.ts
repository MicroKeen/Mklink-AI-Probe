export type TrafficFrame = { source: string; session: string; direction: 'RX' | 'TX'; time: number; hex: string; lost_bytes: number }
export type TrafficLog = { frames: TrafficFrame[]; sources: string[]; warning: boolean }
export const TRAFFIC_FILE_LIMIT = 16 * 1024 * 1024

export function parseTrafficLog(text: string, kind: 'rtt' | 'serial'): TrafficLog {
  if (text.length > TRAFFIC_FILE_LIMIT) throw new Error('Log part exceeds 16 MiB')
  const lines = text.trim().split(/\r?\n/)
  const header = JSON.parse(lines.shift() || '{}')
  if (header.type !== 'mklink-traffic' || header.version !== 1 || header.kind !== kind) throw new Error('Not a compatible ' + kind + ' traffic log')
  const frames: TrafficFrame[] = [], sources = new Set<string>()
  let complete = false, warning = false
  for (const [index, line] of lines.entries()) {
    let row
    try { row = JSON.parse(line) } catch {
      if (index !== lines.length - 1 || !frames.length) throw new Error('Invalid traffic log')
      warning = true; break
    }
    if (row.type === 'end' && index === lines.length - 1) { complete = row.complete === true; break }
    if (row.type !== 'data' || !['RX', 'TX'].includes(row.direction)
        || typeof row.source !== 'string' || !row.source || row.source.length > 256
        || typeof row.session !== 'string' || row.session.length > 256
        || !Number.isFinite(row.time) || row.time < 0
        || !Number.isSafeInteger(row.lost_bytes) || row.lost_bytes < 0
        || typeof row.hex !== 'string' || !/^(?:[a-fA-F0-9]{2})+$/.test(row.hex) || row.hex.length > 32768
        || frames.length >= 20000) throw new Error('Invalid traffic record')
    sources.add(row.source)
    if (sources.size > 16) throw new Error('Too many traffic sources')
    warning ||= row.lost_bytes > 0
    frames.push(row as TrafficFrame)
  }
  if (!frames.length) throw new Error('Log contains no traffic')
  return { frames, sources: [...sources], warning: warning || !complete }
}

export function trafficBytes(frame: TrafficFrame): Uint8Array {
  return Uint8Array.from(frame.hex.match(/../g)!, value => parseInt(value, 16))
}

/** A decoder per source/direction/session preserves split multibyte characters. */
export class TrafficTextDecoder {
  private decoders = new Map<string, TextDecoder>()
  private encoding: string
  constructor(encoding = 'utf-8') { this.encoding = encoding }
  decode(frame: TrafficFrame): string {
    const key = `${frame.source}:${frame.direction}`
    const sessionKey = `${key}:${frame.session}`
    // Discard stale sessions instead of retaining an unbounded decoder history.
    for (const previous of this.decoders.keys()) if (previous.startsWith(key + ':') && previous !== sessionKey) this.decoders.delete(previous)
    let decoder = this.decoders.get(sessionKey)
    if (!decoder) { decoder = new TextDecoder(this.encoding); this.decoders.set(sessionKey, decoder) }
    return decoder.decode(trafficBytes(frame), { stream: true })
  }
}
