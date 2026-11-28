import { File as NodeFile } from 'node:buffer'
import { describe, expect, it, vi } from 'vitest'
import { indexedTraffic } from './trafficReplay'
// @ts-ignore Shared module also runs in the standalone viewer.
import { indexedWaveform } from '../../../mklink/static/indexed_waveform.js'
import { openRecording } from '../../../mklink/static/recording_file.js'

function capture(kind: string, blocks: {meta: object; rows: object[]}[], interrupted = false) {
  const pieces: Buffer[] = [Buffer.from('MKLOG1 ' + kind + '\n')], index: string[] = []
  let offset = pieces[0]!.length
  const payloads: number[] = []
  for (const b of blocks) {
    const meta = Buffer.from(JSON.stringify(b.meta)), payload = Buffer.from(b.rows.map(r => JSON.stringify(r)).join('\n') + '\n')
    const prefix = Buffer.alloc(8)
    prefix.writeUInt32LE(meta.length); prefix.writeUInt32LE(payload.length, 4)
    index.push(JSON.stringify([offset, meta.length, payload.length, b.meta]))
    payloads.push(offset + 8 + meta.length)
    pieces.push(prefix, meta, payload); offset += 8 + meta.length + payload.length
  }
  if (interrupted) pieces.push(Buffer.from([5, 0, 0]))
  else {
    const tail = Buffer.alloc(16)
    tail.writeBigUInt64LE(BigInt(offset + 8)); tail.write('MKIDX1\r\n', 8)
    pieces.push(Buffer.alloc(8), Buffer.from([JSON.stringify({complete:true, blocks:blocks.length}), ...index, ''].join('\n')), tail)
  }
  return { file: new NodeFile(pieces, 'record.mklog') as unknown as File, payloads }
}

describe('indexed capture playback', () => {
  it('opens the overview from the footer and reads only the zoomed block, with raw peaks and breaks', async () => {
    const { file, payloads } = capture('superwatch', [0, 10, 20].map((start, i) => ({
      meta: {start, end:start+2, rows:3, gap:i===1?1:0, loss:false, tracks:{a:[3,start,2,start+1,-8,start+2,6,start+2,6]}},
      rows: [{_t:start,a:2},{_t:start+1,a:-8},{_t:start+2,a:6}],
    })))
    const slices = vi.spyOn(file, 'slice')
    const replay = await indexedWaveform(file)
    expect(replay.metadata).toMatchObject({rows:9, values:9, duration:22, incomplete:false})
    expect(slices.mock.calls.some(c => payloads.includes(c[0]!))).toBe(false)
    const view = await replay.range(9, 13, 11, 100, ['a'], false)
    expect(view.channels[0].points).toEqual([[10,2],[11,-8],[12,6]])
    expect(view.channels[0].latest).toBe(-8)
    expect(view.channels[0].segments).toEqual([1,1,1])
    expect(view.channels[0].columns[0]).toBe(1)
    expect(slices.mock.calls.filter(c => payloads.includes(c[0]!)).map(c=>c[0])).toEqual([payloads[1]])
  })
  it.each(['serial','rtt'] as const)('seeks to the right %s frame and restores finished blocks after an interruption', async kind => {
    const {file} = capture(kind, [10,21].map(start => ({
      meta: {start,end:start+1,rows:2,gap:0,loss:false,tracks:{A:[2,start,start+1]}},
      rows: [start,start+1].map(time=>({type:'data', time, session:'s', source:'A', hex:'4142', lost_bytes:0, direction:'TX'})),
    })), true)
    const log = await indexedTraffic(file,kind)
    expect(log.warning).toBe(true)
    expect(log.count('A')).toBe(4)
    expect(log.duration('A')).toBe(12000)
    expect(await log.cursorAt('A',5000)).toBe(2)
    expect(await log.cursorAt('A',11000)).toBe(3)
    expect((await log.page('A',3)).frames[1]).toMatchObject({time:22,hex:'4142',direction:'TX'})
    await expect(openRecording(file,'superwatch')).rejects.toThrow('recording type')
  })
})
