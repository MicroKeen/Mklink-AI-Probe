import { describe, expect, it } from 'vitest'
import { hpmIspOutput, hpmIspConnection } from './hpmIspOutput'

const event = (name: string, values = {}) => 'HPM_ISP ' + JSON.stringify({
  schema: 1, event: name, cycle: 1, completed: 0, total: 10, code: 0, ...values,
})

describe('ISP LCD output', () => {
  it('shows OTP reasons matching the LCD instead of a misleading baud error', () => {
    expect(hpmIspOutput([event('result', { code: -12, otp_reason: 'geometry_mismatch' }),
      'ISP OTP: OTP layout unsupported', 'USART ISP Baud not supported']))
      .toEqual(['ISP OTP: OTP layout unsupported'])
    expect(hpmIspOutput([event('result', { code: -3, otp_reason: 'write_outcome_unknown' }),
      'ISP OTP: Write uncertain; check OTP', 'Timeout', 'USART ISP timeout']))
      .toEqual(['ISP OTP: Write uncertain; check OTP', 'Timeout'])
  })
  it('keeps the completed round connected until firmware detects disconnect', () => {
    let state = hpmIspConnection('idle', event('waiting'))
    state = hpmIspConnection(state, event('connected'))
    state = hpmIspConnection(state, event('cycle_done', { completed: 1 }))
    expect(state).toBe('cycle_done')
    expect(hpmIspConnection(state, 'HPM_ISP broken')).toBe('cycle_done')
    state = hpmIspConnection(state, event('disconnected'))
    expect(state).toBe('waiting')
    state = hpmIspConnection(state, event('connected'))
    expect(state).toBe('connected')
    expect(hpmIspConnection(state, event('result'))).toBe('idle')
    expect(hpmIspOutput([event('disconnected'), 'ISP disconnected'])).toEqual(['ISP disconnected'])
  })
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

  it('renders a timeout reason for structured events and legacy scripts', () => {
    expect(hpmIspOutput([event('connected'), 'ISP connected',
      event('result', { code: -3, completed: 2 }), 'ISP error -3 (2/10)',
      'USART ISP failed: -3'])).toEqual(['ISP connected', 'ISP: timeout'])
  })

  it.each([
    [-1, 'Invalid settings'], [-2, 'UART I/O error'], [-3, 'timeout'],
    [-4, 'Invalid UART frame'], [-5, 'CRC mismatch'], [-6, 'ROM aborted transfer'],
    [-7, 'ROM rejected command'], [-8, 'Cancelled'], [-9, 'Device busy'],
    [-10, 'BIN file error'], [-11, 'BIN address conflict'], [-12, 'Baud not supported'],
    [-999, 'Unknown ISP error'],
  ])('describes result %s without exposing its numeric code', (code, reason) => {
    expect(hpmIspOutput([event('result', { code })])).toEqual([`ISP: ${reason}`])
  })

  it('keeps firmware timeout stages, recovery hints and script configuration failures', () => {
    const lines = ['ISP reconnect timeout', 'Reconnect target', 'ISP write timeout',
      'Check UART/BOOT/power', 'ISP config: Invalid settings', 'ISP: Cancelled']
    expect(hpmIspOutput(lines)).toEqual(lines)
  })

  it('accepts readable SD script errors and preserves cancellation', () => {
    expect(hpmIspOutput(['USART ISP timeout', 'USART ISP cancelled',
      'USART ISP config: Invalid settings', 'USART ISP unknown error']))
      .toEqual(['ISP: timeout', 'ISP: Cancelled', 'ISP config: Invalid settings', 'ISP: Unknown ISP error'])
  })

  it.each(['HPM_ISP broken', 'HPM_ISP null', event('result', { code: '0' }),
    event('waiting', { cycle: '<script>' }), event('result', { schema: 2 }),
    'print("ISP connected")', 'print(isp_label, "timeout")', 'ISP: untrusted arbitrary text',
    'ISP arbitrary timeout'])('ignores malformed or non-display text: %s', line => {
    expect(hpmIspOutput([line])).toEqual([])
  })
})
