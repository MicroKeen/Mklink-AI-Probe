/** Bounded arithmetic expressions. Never evaluates JavaScript or accesses objects. */
const functions = {
  abs: [1, Math.abs], sqrt: [1, Math.sqrt], sin: [1, Math.sin], cos: [1, Math.cos],
  tan: [1, Math.tan], log: [1, Math.log], log10: [1, Math.log10], exp: [1, Math.exp],
  floor: [1, Math.floor], ceil: [1, Math.ceil], round: [1, Math.round],
  min: [2, Math.min], max: [2, Math.max], pow: [2, Math.pow],
}
export function compileSignalFormula(source) {
  if (source.length > 256) throw new Error('公式最多 256 字符 / Maximum 256 characters')
  if (!source.trim()) return x => x
  const tokens = source.match(/(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|[a-zA-Z_][a-zA-Z_0-9]*|\*\*|[^\s]/g) || []
  let index = 0, depth = 0
  const fail = () => { throw new Error('无效公式 / Invalid formula: ' + (tokens[index] || 'end')) }
  function primary() {
    if (++depth > 32) fail()
    const token = tokens[index++]
    let result
    if (/^(?:\d|\.)/.test(token || '') && Number.isFinite(Number(token))) {
      const n = Number(token); result = () => n
    } else if (token === 'x') result = x => x
    else if (token === 'pi' || token === 'e') result = () => token === 'pi' ? Math.PI : Math.E
    else if (token === '(') { result = expression(); if (tokens[index++] !== ')') fail() }
    else if (Object.prototype.hasOwnProperty.call(functions, token)) {
      const [arity, fn] = functions[token]
      if (tokens[index++] !== '(') fail()
      const args = [expression()]
      while (tokens[index] === ',') { index++; args.push(expression()); if (args.length > arity) fail() }
      if (tokens[index++] !== ')' || args.length !== arity) fail()
      result = x => fn(...args.map(arg => arg(x)))
    } else return fail()
    depth--; return result
  }
  function unary() {
    if (tokens[index] === '+' || tokens[index] === '-') {
      const sign = tokens[index++]; if (++depth > 32) fail()
      const value = unary(); depth--; return x => sign === '-' ? -value(x) : value(x)
    }
    const left = primary()
    if (tokens[index] === '^' || tokens[index] === '**') { index++; if (++depth > 32) fail(); const right = unary(); depth--; return x => left(x) ** right(x) }
    return left
  }
  function product() {
    let left = unary()
    while (['*', '/', '%'].includes(tokens[index])) {
      const op = tokens[index++], a = left, b = unary()
      left = x => op === '*' ? a(x) * b(x) : op === '/' ? a(x) / b(x) : a(x) % b(x)
    }
    return left
  }
  function expression() {
    let left = product()
    while (tokens[index] === '+' || tokens[index] === '-') {
      const op = tokens[index++], a = left, b = product()
      left = x => op === '+' ? a(x) + b(x) : a(x) - b(x)
    }
    return left
  }
  const evaluate = expression()
  if (index !== tokens.length) fail()
  return x => { const value = evaluate(x); return Number.isFinite(value) ? value : NaN }
}
const cache = new Map()
export function signalFormula(source = '') {
  let compiled = cache.get(source)
  if (!compiled) {
    try { compiled = compileSignalFormula(source) } catch { compiled = () => NaN }
    if (cache.size >= 1024) cache.clear()
    cache.set(source, compiled)
  }
  return compiled
}
