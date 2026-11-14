/** Component-owned actions; the frontend bridge validates these before dispatch. */
export type DomainArgs = Record<string, any>
export type DomainAction = {
  name: string
  description: string
  args: { type: 'object'; properties: Record<string, unknown>; required: string[]; additionalProperties: false }
  effect: 'view' | 'device' | 'file'
}
export function domainAction(name: string, description: string, properties: Record<string, unknown> = {}, required: string[] = [], effect: DomainAction['effect'] = 'view'): DomainAction {
  return { name, description, args: { type: 'object', properties, required, additionalProperties: false }, effect }
}
export const pathArg = { type: 'string', maxLength: 512 }
export const pathsArg = { type: 'array', items: pathArg, maxItems: 500 }
export const boolArg = { type: 'boolean' }
export function requireDomain(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message)
}
