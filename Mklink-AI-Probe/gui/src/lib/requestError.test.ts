import { expect, it } from 'vitest'
import { requestError } from './requestError'

it('names the acquisition holding a nested configuration request', () => {
  const value = requestError({ detail: { detail: { busy: ['rtt', 'superwatch'] } } }, 409, 'MKLink')
  expect(value).toContain('RTT')
  expect(value).toContain('SuperWatch')
})
