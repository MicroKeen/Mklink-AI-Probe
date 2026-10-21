import { describe, expect, it } from 'vitest'
import { hpmIspOutput } from './hpmIspOutput'

const event = (name: string, values = {}) => 'HPM_ISP ' + JSON.stringify({
  schema: 1, event: name, cycle: 1, completed: 0, total: 10, code: 0, ...values,
})

describe('ISP LCD output', () => {
  it('matches LCD messages across rounds without script or protocol dumps', () => {
    expect(hpmIspOutput([
      'import hpm', 'rc = hpm.isp_program("job", 10)',
      event('waiting'), event('connected'), event('progress'),
      event('cycle_done', { completed: 1 }),
      event('waiting', { cycle: 2, completed: 1 }), event('connected'),
      event('result', { cycle: 10, completed: 10 }),
    ])).toEqual(['ISP waiting 1/10', 'ISP connected', 'ISP done 1/10',
      'ISP waiting 2/10', 'ISP connected', 'ISP OK 10/10'])
  })

  it('keeps error codes and LCD text while collapsing echoed duplicates', () => {
    expect(hpmIspOutput([event('connected'), 'ISP connected',
      event('result', { code: -3, completed: 2 }), 'ISP error -3 (2/10)',
      'USART ISP failed: -3'])).toEqual(['ISP connected', 'ISP error -3 (2/10)', 'USART ISP failed: -3'])
  })

  it.each(['HPM_ISP broken', 'HPM_ISP null', event('result', { code: '0' }),
    event('waiting', { cycle: '<script>' }), event('result', { schema: 2 }),
    'print("ISP connected")'])('ignores malformed or non-display text: %s', line => {
    expect(hpmIspOutput([line])).toEqual([])
  })
})
