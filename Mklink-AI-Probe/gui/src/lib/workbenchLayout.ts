import { interaction, objectSchema, type JsonObject } from './frontendControl'
import type { WatchWorkspace } from '../composables/useWatchWorkspace'
import { validateWidgets, type ControlWidget } from './workbenchControls'

export type PanelType = 'watch' | 'variables' | 'rtt' | 'serial' | 'controls'
export interface WorkbenchPanel { id: string; type: PanelType; title: string; source: { signals?: string[]; channel?: number; port?: string }; x: number; y: number; w: number; h: number; view?: JsonObject; widgets?: ControlWidget[] }
export interface DockGroup { id: string; panels: string[]; active: string }
export interface WorkbenchLayout { version: 1 | 2; revision: number; panels: WorkbenchPanel[]; docks?: DockGroup[] }
export const panelTypes: PanelType[] = ['watch', 'variables', 'rtt', 'serial', 'controls']
export const panelMinimum = { watch: { w: 4, h: 4 }, variables: { w: 3, h: 4 }, rtt: { w: 3, h: 3 }, serial: { w: 3, h: 3 }, controls: { w: 4, h: 3 } }
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
  if (type === 'controls') return {}
  if (type === 'watch' || type === 'variables') {
    const signals: string[] = args.signals || []
    if (signals.some(name => !name || /[\x00-\x1f]/.test(name)) || new Set(signals).size !== signals.length) throw new Error('Signal paths must be distinct and nonempty')
    return { signals }
  }
  if (type === 'rtt') return { channel: args.channel ?? 0 }
  if (/[\x00-\x1f]/.test(args.port || '')) throw new Error('Invalid port name')
  return { port: args.port || '' }
}

export const overlaps = (a: Pick<WorkbenchPanel, 'x' | 'y' | 'w' | 'h'>, b: Pick<WorkbenchPanel, 'x' | 'y' | 'w' | 'h'>) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y
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
  const panel = placePanel(visibleWindows(layout), { id: crypto.randomUUID(), type: args.type, title: args.title,
    source: panelSource(args.type, args), x: 0, y: 0, w: 6, h: 4, ...(args.type === 'controls' ? { widgets: [] } : {}) })
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
  if (![1, 2].includes(value?.version) || !Number.isSafeInteger(value.revision) || value.revision < 0 || !Array.isArray(value.panels) || value.panels.length > 32) throw new Error('Invalid saved layout')
  const ids = new Set<string>()
  for (const panel of value.panels) {
    if (!panel || !/^[a-zA-Z0-9_-]{1,80}$/.test(panel.id) || ids.has(panel.id) || reservedIds.has(panel.id) || !panelTypes.includes(panel.type) || typeof panel.title !== 'string' || panel.title.length > 200) throw new Error('Invalid panel identity')
    ids.add(panel.id)
    const source = panel.source
    if (value.version === 1 && panel.type === 'controls') throw new Error('Controls require layout version 2')
    const properties = panel.type === 'watch' || panel.type === 'variables' ? { signals: signalsSchema }
      : panel.type === 'rtt' ? { channel: { type: 'integer', minimum: 0, maximum: 255 } } : panel.type === 'controls' ? {} : { port: { type: 'string', maxLength: 256 } }
    interaction.validateArgs(source, objectSchema(properties))
    panelSource(panel.type, source)
    const { x, y, w, h } = panel
    interaction.validateArgs({ x, y, w, h }, objectSchema(geometrySchema))
    if (x + w > 12) throw new Error('Invalid panel width')
    if (panel.view !== undefined && (!panel.view || Array.isArray(panel.view) || typeof panel.view !== 'object' || JSON.stringify(panel.view).length > 16384)) throw new Error('Invalid saved view')
    if (panel.type === 'controls') validateWidgets(panel.widgets || [])
    else if (panel.widgets !== undefined) throw new Error('Only a controls panel can contain widgets')
  }
  if (value.version === 2) {
    if (!Array.isArray(value.docks) || value.docks.length > 16) throw new Error('Invalid dock groups')
    const members = new Set<string>(), allIds = new Set(ids)
    for (const dock of value.docks) {
      if (!/^[a-zA-Z0-9_-]{1,80}$/.test(dock.id) || allIds.has(dock.id) || reservedIds.has(dock.id) || !Array.isArray(dock.panels) || dock.panels.length < 2 || !dock.panels.includes(dock.active)) throw new Error('Invalid dock identity')
      allIds.add(dock.id)
      for (const id of dock.panels) {
        if (!ids.has(id) || members.has(id)) throw new Error('Missing or duplicate dock member')
        members.add(id)
      }
    }
    let count = 0
    for (const panel of value.panels) for (const widget of panel.widgets || []) {
      if (allIds.has(widget.id) || reservedIds.has(widget.id)) throw new Error('Duplicate widget ID')
      allIds.add(widget.id); count++
    }
    if (count > 128) throw new Error('A layout supports at most 128 controls')
    const windows = visibleWindows(value)
    for (const panel of windows) {
      const minimum = windowMinimum(value, panel.id)
      if (panel.w < minimum.w || panel.h < minimum.h) throw new Error('Window is smaller than its components can display')
      if (windows.some(other => other.id !== panel.id && overlaps(panel, other))) throw new Error('Windows overlap')
    }
  }
  if (JSON.stringify(value).length > 256 * 1024) throw new Error('Layout is too large')
  return JSON.parse(JSON.stringify(value))
}

export function dockFor(layout: WorkbenchLayout, id: string) { return layout.docks?.find(dock => dock.panels.includes(id)) }
export function windowPanel(layout: WorkbenchLayout, id: string) {
  const hostId = dockFor(layout, id)?.panels[0] || id
  const panel = layout.panels.find(panel => panel.id === hostId)
  if (!panel) throw new Error('Panel no longer exists')
  return panel
}
export function visibleWindows(layout: WorkbenchLayout) {
  return layout.panels.filter(panel => windowPanel(layout, panel.id).id === panel.id)
}
export function windowMinimum(layout: WorkbenchLayout, id: string) {
  const ids = dockFor(layout, id)?.panels || [id]
  return ids.reduce((size, id) => {
    const panel = layout.panels.find(panel => panel.id === id)!
    return { w: Math.max(size.w, panelMinimum[panel.type].w), h: Math.max(size.h, panelMinimum[panel.type].h) }
  }, { w: 1, h: 1 })
}
export function upgradeLayout(input: WorkbenchLayout): WorkbenchLayout {
  const layout = validateLayout(input)
  if (layout.version === 2) return layout
  layout.version = 2; layout.docks = []
  const placed: WorkbenchPanel[] = []
  for (const panel of layout.panels) {
    const minimum = panelMinimum[panel.type]
    placed.push(placePanel(placed, { ...panel, x: Math.min(panel.x, 12 - Math.max(panel.w, minimum.w)), w: Math.max(panel.w, minimum.w), h: Math.max(panel.h, minimum.h) }))
  }
  layout.panels = placed
  return validateLayout(layout)
}

export function moveWindow(layout: WorkbenchLayout, id: string, geometry: JsonObject) {
  const host = windowPanel(layout, id), minimum = windowMinimum(layout, id)
  const candidate = { ...host, ...geometry }
  if (candidate.w < minimum.w || candidate.h < minimum.h) throw new Error(`Window needs at least ${minimum.w} columns and ${minimum.h} rows`)
  const next = placePanel(visibleWindows(layout), candidate)
  Object.assign(host, next)
  return host
}

function detach(layout: WorkbenchLayout, id: string) {
  const dock = dockFor(layout, id)
  if (!dock) return
  const host = windowPanel(layout, id)
  dock.panels = dock.panels.filter(member => member !== id)
  const successor = layout.panels.find(panel => panel.id === dock.panels[0])!
  if (host.id === id) Object.assign(successor, { x: host.x, y: host.y, w: host.w, h: host.h })
  if (dock.active === id) dock.active = successor.id
  if (dock.panels.length < 2) layout.docks = layout.docks!.filter(item => item.id !== dock.id)
}
export function undockPanel(layout: WorkbenchLayout, id: string) {
  const panel = layout.panels.find(panel => panel.id === id)
  if (!panel) throw new Error('Panel no longer exists')
  detach(layout, id)
  const min = panelMinimum[panel.type]
  Object.assign(panel, placePanel(visibleWindows(layout).filter(other => other.id !== id), { ...panel, w: Math.max(panel.w, min.w), h: Math.max(panel.h, min.h) }))
  return panel
}
export function dockPanel(layout: WorkbenchLayout, id: string, target: string) {
  if (id === target || !layout.panels.some(panel => panel.id === id) || !layout.panels.some(panel => panel.id === target)) throw new Error('Choose two different existing panels')
  if (dockFor(layout, id)?.panels.includes(target)) { dockFor(layout, id)!.active = id; return }
  detach(layout, id)
  let dock = dockFor(layout, target)
  if (!dock) {
    dock = { id: crypto.randomUUID(), panels: [target], active: target }
    ;(layout.docks ||= []).push(dock)
  }
  dock.panels.push(id); dock.active = id
  const host = windowPanel(layout, target), min = windowMinimum(layout, target)
  moveWindow(layout, target, { x: Math.min(host.x, 12 - Math.max(host.w, min.w)), w: Math.max(host.w, min.w), h: Math.max(host.h, min.h) })
}
export function removePanel(layout: WorkbenchLayout, id: string) {
  if (!layout.panels.some(panel => panel.id === id)) throw new Error('Panel no longer exists')
  detach(layout, id)
  layout.panels = layout.panels.filter(panel => panel.id !== id)
}
