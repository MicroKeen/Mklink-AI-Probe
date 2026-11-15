import type { InjectionKey } from 'vue'
import { interaction, type JsonObject, type SemanticAction, type SemanticSurface, type SemanticExecutionContext } from './frontendControl'

export interface BindingTarget { id: string; title: string; type: string; surface: SemanticSurface }
export interface BindingHost {
  targets(): BindingTarget[]
  invoke(panelId: string, action: string, args: JsonObject, context?: SemanticExecutionContext): Promise<unknown>
}
export const bindingHostKey: InjectionKey<BindingHost> = Symbol('workbench-bindings')
export interface ControlBinding { panel_id?: string; action?: string; state_path?: string; args?: JsonObject; contract?: string }
const forbidden = new Set(['__proto__', 'prototype', 'constructor'])
const plain = (value: unknown): value is JsonObject => value !== null && typeof value === 'object' && !Array.isArray(value)
function canonical(value: any): any { return Array.isArray(value) ? value.map(canonical) : plain(value) ? Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])])) : value }
export function sameBinding(a: ControlBinding, b: ControlBinding) { return JSON.stringify(canonical(a)) === JSON.stringify(canonical(b)) }
export function bindingContract(action: SemanticAction) { return JSON.stringify(canonical({ args: action.args, effect: action.effect || 'view' })) }
export function bindingTarget(host: BindingHost, panelId?: string) {
  const target = host.targets().find(item => item.id === panelId && item.type !== 'controls')
  if (!target) throw new Error('Binding target is unavailable; choose the intended panel again')
  return target
}
export function bindingAction(host: BindingHost, binding: ControlBinding, checkContract = true) {
  const target = bindingTarget(host, binding.panel_id)
  const action = target.surface.catalog().find(item => item.name === binding.action && !item.name.startsWith('component.'))
  if (!action) throw new Error('Bound action is unavailable; choose an advertised action')
  if (checkContract && binding.contract !== bindingContract(action)) throw new Error('Bound action contract changed; explicitly rebind this control')
  return action
}
export function parseArguments(text: string): JsonObject {
  if (text.length > 8192) throw new Error('Arguments exceed 8192 characters')
  const args: unknown = JSON.parse(text || '{}')
  if (!plain(args)) throw new Error('Arguments must be a JSON object')
  return args
}
export function validateStatePath(path: string) {
  if (!path || path.length > 512 || path.split('.').some(part => !part || forbidden.has(part) || /[\x00-\x1f]/.test(part))) throw new Error('Invalid public state path')
}
export function readBoundValue(host: BindingHost, binding: ControlBinding) {
  validateStatePath(binding.state_path || '')
  let value: any = bindingTarget(host, binding.panel_id).surface.read()
  for (const key of binding.state_path!.split('.')) {
    if (value === null || typeof value !== 'object' || !Object.hasOwn(value, key)) throw new Error('Public state field is unavailable; explicitly rebind this control')
    value = value[key]
  }
  if (value === undefined) throw new Error('Public state field is unavailable; explicitly rebind this control')
  if (JSON.stringify(value)?.length > 8192) throw new Error('State field is too large; choose a narrower field')
  return value
}
export function makeBinding(host: BindingHost, type: 'button' | 'form' | 'value', input: ControlBinding): ControlBinding {
  if (!input.panel_id) throw new Error('Choose a binding target')
  if (type === 'value') {
    const binding = { panel_id: input.panel_id, state_path: input.state_path || '' }
    readBoundValue(host, binding)
    return binding
  }
  const action = bindingAction(host, input, false), args = input.args || {}
  interaction.validateArgs(args, type === 'form' ? { ...action.args, required: [] } : action.args)
  const contract = bindingContract(action)
  if (contract.length > 16384 || new TextEncoder().encode(JSON.stringify(args)).length > 8192) throw new Error('Binding configuration is too large')
  return { panel_id: input.panel_id, action: action.name, args: JSON.parse(JSON.stringify(args)), contract }
}
export async function invokeBinding(host: BindingHost, binding: ControlBinding, overrides: JsonObject = {}, context?: SemanticExecutionContext) {
  const action = bindingAction(host, binding)
  const args = { ...binding.args, ...overrides }
  interaction.validateArgs(args, action.args)
  return host.invoke(binding.panel_id!, action.name, args, context)
}
