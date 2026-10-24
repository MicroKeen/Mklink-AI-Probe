import { expect, it } from 'vitest'
import { compileSignalFormula, signalFormula } from './signalFormula'
import { TypedRingBuffer } from './stream/typedRingBuffer'

it('evaluates engineering formulas with bounded arithmetic and normal precedence', () => {
  expect(compileSignalFormula('x * 3.3 / 4095')(4095)).toBe(3.3)
  expect(compileSignalFormula('-x^2 + max(2, sqrt(16))')(-3)).toBe(-5)
  expect(compileSignalFormula('sin(pi / 2) + 1e-3 * x')(1000)).toBe(2)
  expect(compileSignalFormula('')(7)).toBe(7)
  expect(compileSignalFormula('1 / x')(0)).toBeNaN()
  expect(compileSignalFormula('sqrt(x)')(-1)).toBeNaN()
})
it('rejects code, properties, invalid arguments and excessive nesting', () => {
  for (const formula of ['window.alert(1)', 'x.constructor', 'x=2', '1;2', 'min(1)', 'pow(1,2,3)', 'sqrt()', '1e999', '('.repeat(40) + 'x' + ')'.repeat(40), '-'.repeat(50) + 'x']) {
    expect(() => compileSignalFormula(formula), formula).toThrow()
    expect(signalFormula(formula)(2)).toBeNaN()
  }
})
it('selects extrema after non-linear conversion, preserving raw history for inspection and export', () => {
  const ring = new TypedRingBuffer(10, 2)
  ;[-3, -1, 0, 2].forEach((x, index) => ring.append(index, Float32Array.of(x, x)))
  const before = ring.snapshot()
  const selection = ring.selectMinMaxEnvelope(0, 3, 1, [signalFormula('x^2'), signalFormula('-x * 100')])
  expect([...selection.logicalIndices.slice(0, selection.channelOffsets[1])]).toEqual([0, 2])
  expect(ring.snapshot()).toEqual(before)
  const invalid = ring.selectMinMaxEnvelope(0, 3, 1, [signalFormula('sqrt(-abs(x)-1)')])
  expect(invalid.channelOffsets[1]).toBe(0)
})
