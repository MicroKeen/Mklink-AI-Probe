import { expect, it } from 'vitest'
import { controlTypes, createControl, placeControl, registerControlRenderer, validateWidgets } from './workbenchControls'

it('keeps repeated components independent and uses registered readable dimensions', () => {
  const a = createControl([], 'form', 'Parameters')
  const b = createControl([a], 'form', 'Other parameters')
  expect(a.id).not.toBe(b.id)
  expect(b.y).toBe(a.h)
  expect(() => placeControl([a], { ...b, w: 2 })).toThrow('readable')
  expect(validateWidgets([a, b])).toEqual([a, b])
  expect(() => validateWidgets([a, { ...b, y: a.y }])).toThrow('overlap')
})
it('supports build-owned registration and rejects duplicate identities and executable config', () => {
  const widget = createControl([], 'indicator', 'Status')
  expect(widget.type).toBe('indicator')
  expect(controlTypes.indicator?.presentation).toBe('value')
  expect(() => registerControlRenderer('unregistered', { template: '<div />' })).toThrow('metadata')
  expect(() => validateWidgets([widget, widget])).toThrow('Duplicate')
  expect(() => validateWidgets([{ ...widget, script: 'execute()' } as any])).toThrow('Unexpected')
})
