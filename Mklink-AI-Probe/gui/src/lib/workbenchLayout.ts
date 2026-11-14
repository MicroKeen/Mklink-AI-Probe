import { interaction, objectSchema, type JsonObject } from './frontendControl'
import type { WatchWorkspace } from '../composables/useWatchWorkspace'

export type PanelType = 'watch' | 'variables' | 'rtt' | 'serial'
export interface WorkbenchPanel { id: string; type: PanelType; title: string; source: { signals?: string[]; channel?: number; port?: string }; x: number; y: number; w: number; h: number; view?: JsonObject }
export interface WorkbenchLayout { version: 1; revision: number; panels: WorkbenchPanel[] }
export const panelTypes: PanelType[] = ['watch', 'variables', 'rtt', 'serial']
const reservedIds = new Set(['dashboard', 'superwatch', 'workbench', 'SuperWatch', 'VOFA'])
export const textSchema = { type: 'string', maxLength: 200 }
export const signalsSchema = { type: 'array', items: { type: 'string', maxLength: 512 }, maxItems: 500 }
export const geometrySchema = {
  x: { type: 'integer', minimum: 0, maximum: 11 }, y: { type: 'integer', minimum: 0, maximum: 200 },
  w: { type: 'integer', minimum: 1, maximum: 12 }, h: { type: 'integer', minimum: 1, maximum: 12 },
}
export const panelInputSchema = objectSchema({ type: { type: 'string', enum: panelTypes }, title: textSchema,
  signals: signalsSchema, channel: { type: 'integer', minimum: 0, maximum: 255 }, port: { type: 'string', maxLength: 256 } }, ['type', 'title'])

export function panelSource(type: PanelType, args: JsonObject): WorkbenchPanel['source'] {
  if (type === 'watch' || type === 'variables') {
    const signals: string[] = args.signals || []
    if (signals.some(name => !name || /[\x00-\x1f]/.test(name)) || new Set(signals).size !== signals.length) throw new Error('Signal paths must be distinct and nonempty')
    return { signals }
  }
  if (type === 'rtt') return { channel: args.channel ?? 0 }
  if (/[\x00-\x1f]/.test(args.port || '')) throw new Error('Invalid port name')
  return { port: args.port || '' }
}

const overlaps = (a: WorkbenchPanel, b: WorkbenchPanel) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y
export function placePanel(panels: WorkbenchPanel[], panel: WorkbenchPanel): WorkbenchPanel {
  interaction.validateArgs({ x: panel.x, y: panel.y, w: panel.w, h: panel.h }, objectSchema(geometrySchema))
  if (panel.x + panel.w > 12) throw new Error('Panel extends beyond the twelve-column layout')
  const placed = { ...panel }
  while (panels.some(other => other.id !== panel.id && overlaps(placed, other))) {
    placed.y++
    if (placed.y > 200) throw new Error('No room in the layout')
  }
  return placed
}

export function addPanel(layout: WorkbenchLayout, args: JsonObject): WorkbenchPanel {
  interaction.validateArgs(args, panelInputSchema)
  if (layout.panels.length >= 32) throw new Error('A layout supports at most 32 panels')
  const panel = placePanel(layout.panels, { id: crypto.randomUUID(), type: args.type, title: args.title,
    source: panelSource(args.type, args), x: 0, y: 0, w: 6, h: 4 })
  layout.panels.push(panel)
  return panel
}

/** First-use projection only. Existing group IDs/styles stay in their original store. */
export function migrateLegacyWorkbench(saved: WorkbenchLayout, workspace: Pick<WatchWorkspace, 'groups' | 'signals' | 'defaultGroup'>, selectedPaths: string[] = []) {
  if (saved.revision !== 0 || saved.panels.length) return { layout: validateLayout(saved), migrated: false, omittedGroups: 0, omittedSignals: 0 }
  const groups = workspace.groups.length ? workspace.groups : [{ id: 'main', name: 'SuperWatch', collapsed: false, height: 240 }]
  const fallback = groups.find(group => group.id === workspace.defaultGroup)?.id || groups[0]!.id
  const allPaths = [...new Set([...Object.keys(workspace.signals), ...selectedPaths])]
  const knownGroups = new Set(groups.map(group => group.id))
  let projected = groups.map(group => ({ group, paths: allPaths.filter(path => {
    const assigned = workspace.signals[path]?.group
    return (assigned && knownGroups.has(assigned) ? assigned : fallback) === group.id
  }) }))
  // Empty shared groups have no plot in the original workspace either.
  projected = projected.filter(item => item.paths.length)
  if (!projected.length) projected = [{ group: groups.find(group => group.id === fallback)!, paths: [] }]
  const layout: WorkbenchLayout = { version: 1, revision: 0, panels: [{ id: 'legacy_variables', type: 'variables', title: 'Variables', source: { signals: [] }, x: 0, y: 0, w: 4, h: 6 }] }
  const ids = new Set(layout.panels.map(panel => panel.id))
  let omittedSignals = 0
  for (const [index, item] of projected.slice(0, 31).entries()) {
    const base = `legacy_watch_${item.group.id.replace(/[^a-zA-Z0-9_-]/g, '_') || 'group'}`.slice(0, 72)
    let id = base
    let suffix = index
    while (ids.has(id)) id = `${base}_${suffix++}`
    ids.add(id)
    const signals = item.paths.slice(0, 500)
    omittedSignals += item.paths.length - signals.length
    layout.panels.push({ id, type: 'watch', title: item.group.name || 'SuperWatch', source: { signals }, x: 4, y: index * 4, w: 8, h: 4 })
  }
  return { layout: validateLayout(layout), migrated: true, omittedGroups: Math.max(0, projected.length - 31), omittedSignals }
}

export function validateLayout(value: WorkbenchLayout): WorkbenchLayout {
  if (value?.version !== 1 || !Number.isSafeInteger(value.revision) || value.revision < 0 || !Array.isArray(value.panels) || value.panels.length > 32) throw new Error('Invalid saved layout')
  const ids = new Set<string>()
  for (const panel of value.panels) {
    if (!panel || !/^[a-zA-Z0-9_-]{1,80}$/.test(panel.id) || ids.has(panel.id) || reservedIds.has(panel.id) || !panelTypes.includes(panel.type) || typeof panel.title !== 'string' || panel.title.length > 200) throw new Error('Invalid panel identity')
    ids.add(panel.id)
    const source = panel.source
    const properties = panel.type === 'watch' || panel.type === 'variables' ? { signals: signalsSchema }
      : panel.type === 'rtt' ? { channel: { type: 'integer', minimum: 0, maximum: 255 } } : { port: { type: 'string', maxLength: 256 } }
    interaction.validateArgs(source, objectSchema(properties))
    panelSource(panel.type, source)
    const { x, y, w, h } = panel
    interaction.validateArgs({ x, y, w, h }, objectSchema(geometrySchema))
    if (x + w > 12) throw new Error('Invalid panel width')
    if (panel.view !== undefined && (!panel.view || Array.isArray(panel.view) || typeof panel.view !== 'object' || JSON.stringify(panel.view).length > 16384)) throw new Error('Invalid saved view')
  }
  return JSON.parse(JSON.stringify(value))
}
