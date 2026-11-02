import { expect, it } from 'vitest'
import { parseTrafficLog, trafficBytes, TrafficTextDecoder } from './trafficReplay'
const row = (hex = 'e4', direction = 'RX', session = 'a') => ({type:'data',source:'0',session,direction,time:123.4,hex,lost_bytes:0})
const file = (...rows: unknown[]) => [JSON.stringify({type:'mklink-traffic',version:1,kind:'rtt'}), ...rows.map(r=>JSON.stringify(r))].join('\n')
it('preserves raw bytes, direction, time and split multibyte text across independent streams', () => {
  const log = parseTrafficLog(file(row(),row('ff00','TX'),row('b8ad'),{type:'end',complete:true}), 'rtt')
  const decoder = new TrafficTextDecoder()
  expect(log.warning).toBe(false)
  expect(decoder.decode(log.frames[0]!)).toBe('')
  expect(Array.from(trafficBytes(log.frames[1]!))).toEqual([255,0])
  decoder.decode(log.frames[1]!)
  expect(decoder.decode(log.frames[2]!)).toBe('中')
  expect(log.frames[1]!.time).toBe(123.4)
  expect(log.frames[1]!.direction).toBe('TX')
})
it('reports truncated, failed or lossy recordings and rejects invalid/unrelated data', () => {
  expect(parseTrafficLog(file(row()), 'rtt').warning).toBe(true)
  expect(parseTrafficLog(file(row())+'\n{"unfinished":', 'rtt').warning).toBe(true)
  expect(parseTrafficLog(file({...row(),lost_bytes:5},{type:'end',complete:true}), 'rtt').warning).toBe(true)
  expect(parseTrafficLog(file(row(),{type:'end',complete:false}), 'rtt').warning).toBe(true)
  for (const invalid of [row('xx'),row('0'),{...row(), time:NaN}, {...row(),direction:'EXEC'}]) {
    expect(()=>parseTrafficLog(file(invalid),'rtt')).toThrow()
  }
  expect(()=>parseTrafficLog(file(row()),'serial')).toThrow()
})
it('does not combine a partial character across capture sessions', () => {
  const decoder = new TrafficTextDecoder()
  const log = parseTrafficLog(file(row(),row('b8ad','RX','new')), 'rtt')
  expect(decoder.decode(log.frames[0]!)).toBe('')
  expect(decoder.decode(log.frames[1]!)).not.toBe('中')
})
