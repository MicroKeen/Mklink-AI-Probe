import { expect, it } from 'vitest'
import { display, formArguments, operationFields } from './capabilityPresentation'

it('formats recording timestamps without reinterpreting ordinary numeric measurements', () => {
  const timestamp = 1794730842.123
  expect(display(timestamp, 'started_at')).toBe(new Date(timestamp * 1000).toLocaleString('zh-CN', { hour12: false }))
  expect(display(timestamp, 'value')).toBe(String(timestamp))
  expect(display(null, 'stopped_at')).toBe('—')
})

it('preserves zero, false, enum types and omitted defaults in form submissions', () => {
  const { fields, guided } = operationFields({ parameters: [{ name:'count', required:true, schema:{ type:'integer', minimum:0 } }], requestBody:{ content:{ 'application/json':{ schema:{ properties:{
    enabled:{ type:'boolean' }, mode:{ enum:[2, 4] }, names:{ type:'array', items:{ type:'string' } }, delay:{ anyOf:[{ type:'number' }, { type:'null' }] },
  } } } } } })
  expect(guided).toBe(false)
  expect(formArguments(fields, { count:'0', enabled:'false', mode:'1', names:'a\nb', delay:'' })).toEqual({ count:0, enabled:false, mode:4, names:['a','b'] })
  expect(() => formArguments(fields, { count:'1.5' })).toThrow('整数')
  expect(() => formArguments(fields, { count:'-1' })).toThrow('范围')
  expect(() => formArguments(fields, {})).toThrow('填写')
  expect(display('D:/my_project/log_file.jsonl')).toBe('D:/my_project/log_file.jsonl')
})

it('routes open objects and required complex parameters to conversation without inventing an editable JSON field', () => {
  const body = (schema: object) => ({ requestBody:{ content:{ 'application/json':{ schema } } } })
  expect(operationFields(body({ type:'object', additionalProperties:true })).guided).toBe(true)
  const complex = operationFields(body({ properties:{ configuration:{ type:'object' } }, required:['configuration'] }))
  expect(complex.guided).toBe(true)
  expect(complex.fields[0]?.kind).toBe('guided')
})
