import { openRecording, type RecordingBlock } from '../../../mklink/static/recording_file.js'

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

export async function indexedTraffic(file: File, kind: 'rtt' | 'serial') {
  const capture = await openRecording(file, kind)
  type Entry = { block: RecordingBlock; first: number; count: number; previousEnd: number; end: number }
  const tracks = new Map<string, { entries: Entry[]; count: number; origin: number }>()
  let warning = !capture.complete
  for (const block of capture.blocks) {
    warning ||= block.loss
    for (const [source, meta] of Object.entries(block.tracks)) {
      const track = tracks.get(source) ?? { entries: [], count: 0, origin: meta[1]! }
      const previousEnd = track.entries.at(-1)?.end ?? track.origin
      track.entries.push({ block, first: track.count, count: meta[0]!, previousEnd, end: Math.max(previousEnd, meta[2]!) })
      track.count += meta[0]!
      tracks.set(source, track)
    }
  }
  let cached: { block: RecordingBlock; frames: TrafficFrame[] } | undefined
  async function page(source: string, index: number) {
    const track = tracks.get(source)!
    let lo = 0, hi = track.entries.length
    while (lo < hi) {
      const mid = Math.floor((lo + hi) / 2)
      if (track.entries[mid]!.first <= index) lo = mid + 1
      else hi = mid
    }
    const { block, first, count, previousEnd } = track.entries[lo - 1]!
    if (!cached || cached.block !== block) {
      const text = await (await capture.payload(block)).text()
      const header = JSON.stringify({type:'mklink-traffic', version:1, kind})
      const frames = parseTrafficLog(header + '\n' + text + '{"type":"end","complete":true}', kind).frames
      if (frames.length !== block.rows) throw new Error('Traffic block record count differs from index')
      cached = { block, frames }
    }
    const frames = cached.frames.filter(f => f.source === source)
    if (frames.length !== count) throw new Error('Traffic channel count differs from index')
    let clock = previousEnd
    const times = frames.map(f => ((clock = Math.max(clock, f.time)) - track.origin) * 1000)
    return { frames, first, times }
  }
  function duration(source: string) {
    const t = tracks.get(source)
    return t ? (t.entries.at(-1)!.end - t.origin) * 1000 : 0
  }
  async function cursorAt(source: string, ms: number) {
    const track = tracks.get(source)!, entries = track.entries
    if (ms >= duration(source)) return track.count
    let lo = 0, hi = entries.length
    while (lo < hi) {
      const mid = Math.floor((lo + hi) / 2)
      if ((entries[mid]!.end - track.origin) * 1000 <= ms) lo = mid + 1
      else hi = mid
    }
    const chunk = await page(source, entries[lo]!.first)
    const next = chunk.times.findIndex(t => t > ms)
    return chunk.first + (next < 0 ? chunk.frames.length : next)
  }
  return { sources: [...tracks.keys()], warning, count: (source: string) => tracks.get(source)?.count || 0,
    duration, cursorAt, page }
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
