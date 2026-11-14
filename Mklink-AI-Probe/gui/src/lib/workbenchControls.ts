import { interaction, objectSchema, type JsonObject } from './frontendControl'
import { validateStatePath, type ControlBinding } from './workbenchBindings'
import { markRaw, reactive, type Component, type InjectionKey } from 'vue'
import manifest from '../../../mklink/frontend_components.json'

export interface ControlDefinition { title: string; description: string; presentation: 'button' | 'form' | 'value'; minW: number; minH: number; defaultW: number; defaultH: number; renderer?: Component }
export const controlTypes: Record<string, ControlDefinition> = Object.create(null)
// Build-owned registration; saved layouts never supply executable definitions.
function registerControlType(id: string, definition: ControlDefinition) {
  if (!/^[a-z][a-z0-9-]{0,63}$/.test(id) || Object.hasOwn(controlTypes, id)) throw new Error('Invalid or duplicate component type')
  if (!['button', 'form', 'value'].includes(definition.presentation)) throw new Error('Invalid component presentation')
  if (![definition.minW, definition.minH, definition.defaultW, definition.defaultH].every(n => Number.isSafeInteger(n) && n >= 1 && n <= 12) || definition.defaultW < definition.minW || definition.defaultH < definition.minH) throw new Error('Invalid component design dimensions')
  controlTypes[id] = Object.freeze({ ...definition })
}
export function registerControlRenderer(id: string, renderer: Component) {
  const definition = controlTypes[id]
  if (!definition) throw new Error('Register component metadata before its renderer')
  controlTypes[id] = Object.freeze({ ...definition, renderer: markRaw(renderer) })
}
if (manifest.version !== 1) throw new Error('Unsupported component manifest')
for (const [id, definition] of Object.entries(manifest.components)) registerControlType(id, definition as ControlDefinition)
export type ControlType = string
export interface ControlState {
  drafts: Record<string, Record<string, string>>
  values: Record<string, unknown>
  results: Record<string, unknown>
  statuses: Record<string, { status: string; message?: string }>
  operations: Record<string, string>
  clear(id: string): void
}
export const controlStateKey: InjectionKey<ControlState> = Symbol('control-state')
export function createControlState(): ControlState {
  const state = reactive({ drafts: {}, values: {}, results: {}, statuses: {}, operations: {} }) as Omit<ControlState, 'clear'>
  return { ...state, clear(id: string) { delete state.drafts[id]; delete state.values[id]; delete state.results[id]; delete state.statuses[id]; delete state.operations[id] } }
}
export interface ControlWidget { id: string; version: 1; type: ControlType; title: string; x: number; y: number; w: number; h: number; binding: ControlBinding }
export const controlGeometrySchema = {
  x: { type: 'integer', minimum: 0, maximum: 11 }, y: { type: 'integer', minimum: 0, maximum: 200 },
  w: { type: 'integer', minimum: 1, maximum: 12 }, h: { type: 'integer', minimum: 1, maximum: 12 },
}
export const controlIdSchema = { type: 'string', maxLength: 80 }
const keys = (value: JsonObject, allowed: string[]) => { if (Object.keys(value).some(key => !allowed.includes(key))) throw new Error('Unexpected control field') }
export function validateControl(widget: ControlWidget): ControlWidget {
  if (!widget || typeof widget !== 'object') throw new Error('Invalid control')
  keys(widget, ['id', 'version', 'type', 'title', 'x', 'y', 'w', 'h', 'binding'])
  if (typeof widget.id !== 'string' || !/^[a-zA-Z0-9_-]{1,80}$/.test(widget.id) || widget.version !== 1 || typeof widget.type !== 'string' || !Object.hasOwn(controlTypes, widget.type) || typeof widget.title !== 'string' || widget.title.length > 200) throw new Error('Invalid control identity')
  interaction.validateArgs({ x: widget.x, y: widget.y, w: widget.w, h: widget.h }, objectSchema(controlGeometrySchema))
  const definition = controlTypes[widget.type]
  if (widget.x + widget.w > 12 || widget.w < definition.minW || widget.h < definition.minH) throw new Error('Control is smaller than its readable size or outside the grid')
  const binding = widget.binding
  if (!binding || typeof binding !== 'object' || Array.isArray(binding)) throw new Error('Invalid control binding')
  if (Object.keys(binding).length) {
    if (typeof binding.panel_id !== 'string' || !/^[a-zA-Z0-9_-]{1,80}$/.test(binding.panel_id)) throw new Error('Invalid binding target')
    if (definition.presentation === 'value') {
      keys(binding, ['panel_id', 'state_path']); validateStatePath(binding.state_path || '')
    } else {
      keys(binding, ['panel_id', 'action', 'args', 'contract'])
      if (typeof binding.action !== 'string' || !/^[A-Za-z0-9_.-]{1,128}$/.test(binding.action) || !binding.args || typeof binding.args !== 'object' || Array.isArray(binding.args) || new TextEncoder().encode(JSON.stringify(binding.args)).length > 8192 || typeof binding.contract !== 'string' || binding.contract.length > 16384 || !binding.contract) throw new Error('Invalid action binding')
    }
  }
  return JSON.parse(JSON.stringify(widget))
}
export function validateControls(widgets: ControlWidget[]) {
  if (!Array.isArray(widgets) || widgets.length > 32) throw new Error('A control window supports at most 32 components')
  const ids = new Set<string>()
  const validated = widgets.map(widget => {
    const validated = validateControl(widget)
    if (ids.has(widget.id)) throw new Error('Duplicate component ID')
    ids.add(widget.id)
    return validated
  })
  for (let i = 0; i < validated.length; i++) for (let j = i + 1; j < validated.length; j++) {
    const a = validated[i]!, b = validated[j]!
    if (a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y) throw new Error('Components overlap')
  }
  return validated
}
export const validateWidgets = validateControls
export function placeControl(widgets: ControlWidget[], widget: ControlWidget) {
  const next = validateControl(widget)
  const overlap = (other: ControlWidget) => other.id !== next.id && other.x < next.x + next.w && other.x + other.w > next.x && other.y < next.y + next.h && other.y + other.h > next.y
  while (widgets.some(overlap)) { if (++next.y > 200) throw new Error('No room for this control') }
  return next
}
export function createControl(widgets: ControlWidget[], type: ControlType, title: string) {
  if (!Object.hasOwn(controlTypes, type)) throw new Error('Unsupported control type')
  if (widgets.length >= 32) throw new Error('A control window supports at most 32 components')
  const definition = controlTypes[type]
  return placeControl(widgets, { id: crypto.randomUUID(), version: 1, type, title, x: 0, y: 0, w: definition.defaultW, h: definition.defaultH, binding: {} })
}
export const placeWidget = placeControl
