import { describe, expect, it } from 'vitest'
import { addPanel, migrateLegacyWorkbench, placePanel, validateLayout, upgradeLayout, dockPanel, undockPanel, removePanel, moveWindow, windowPanel, type WorkbenchLayout } from './workbenchLayout'

describe('composable layouts', () => {
  it('upgrades old overlapping windows without overwriting the original configuration', () => {
    const original: WorkbenchLayout = { version: 1, revision: 7, panels: [
      { id: 'one', type: 'rtt', title: 'One', source: { channel: 0 }, x: 0, y: 0, w: 1, h: 1 },
      { id: 'two', type: 'watch', title: 'Two', source: { signals: ['rpm'] }, x: 0, y: 0, w: 2, h: 1 },
    ] }
    const before = JSON.stringify(original), upgraded = upgradeLayout(original)
    expect(upgraded).toMatchObject({ version: 2, revision: 7, docks: [] })
    expect(upgraded.panels[0]).toMatchObject({ w: 3, h: 3 })
    expect(upgraded.panels[1]).toMatchObject({ y: 3, w: 4, h: 4 })
    expect(JSON.stringify(original)).toBe(before)
  })
  it('docks and detaches tabs without changing source identities or view configuration', () => {
    const layout = upgradeLayout({ version: 1, revision: 1, panels: [] })
    const a = addPanel(layout, { type: 'watch', title: 'A', signals: ['rpm'] })
    const b = addPanel(layout, { type: 'rtt', title: 'B', channel: 1 })
    a.view = { legend: true }; b.view = { mode: 'hex' }
    dockPanel(layout, a.id, b.id)
    expect(layout.docks?.[0]).toMatchObject({ panels: [b.id, a.id], active: a.id })
    moveWindow(layout, a.id, { x: 6, y: 0, w: 6, h: 4 })
    expect(windowPanel(layout, a.id).id).toBe(b.id)
    expect(validateLayout(layout).panels[0]?.view).toEqual({ legend: true })
    undockPanel(layout, a.id)
    expect(layout.docks).toEqual([])
    expect(validateLayout(layout).panels.map(panel => panel.source)).toEqual([{ signals: ['rpm'] }, { channel: 1 }])
    dockPanel(layout, a.id, b.id); removePanel(layout, b.id)
    expect(layout.docks).toEqual([])
    expect(layout.panels[0]).toMatchObject({ id: a.id, x: 6, y: 0, view: { legend: true } })
  })
  it('rejects duplicate dock membership, undersized hosts and overlapping v2 windows', () => {
    const layout = upgradeLayout({ version: 1, revision: 1, panels: [] })
    const a = addPanel(layout, { type: 'watch', title: 'A' }), b = addPanel(layout, { type: 'controls', title: 'B' })
    const wrong = structuredClone(layout); wrong.panels[1]!.y = 0
    expect(() => validateLayout(wrong)).toThrow('overlap')
    dockPanel(layout, a.id, b.id)
    const badDock = structuredClone(layout); badDock.docks![0]!.panels.push(a.id)
    expect(() => validateLayout(badDock)).toThrow()
    expect(() => moveWindow(layout, a.id, { w: 2 })).toThrow('at least')
  })
  it('projects existing groups into unsaved cards without mutating shared styles or IDs', () => {
    const workspace = { defaultGroup: 'motor', groups: [{ id: 'motor', name: 'Motor', collapsed: false, height: 240 }, { id: 'adc:raw', name: 'ADC', collapsed: false, height: 200 }], signals: { rpm: { group: 'motor', pane: 'motor', alias: 'Speed', emphasis: true }, volts: { group: 'adc:raw', pane: 'adc:raw', alias: '', emphasis: false } } }
    const before = JSON.stringify(workspace)
    const result = migrateLegacyWorkbench({ version: 1, revision: 0, panels: [] }, workspace, ['rpm', 'volts', 'unconfigured'])
    expect(result.migrated).toBe(true)
    expect(result.layout.revision).toBe(0)
    expect(result.layout.panels.map(panel => panel.type)).toEqual(['variables', 'watch', 'watch'])
    expect(result.layout.panels[1]).toMatchObject({ id: 'legacy_watch_motor', source: { signals: ['rpm', 'unconfigured'] } })
    expect(result.layout.panels[2]).toMatchObject({ id: 'legacy_watch_adc_raw', source: { signals: ['volts'] } })
    expect(JSON.stringify(workspace)).toBe(before)
  })
  it('respects an intentionally saved empty layout and limits first-use projection', () => {
    const groups = Array.from({ length: 40 }, (_, index) => ({ id: `g${index}`, name: `Group ${index}`, collapsed: false, height: 200 }))
    const workspace = { groups, signals: Object.fromEntries(groups.map(group => [group.id, { group: group.id, pane: group.id, alias: '', emphasis: false }])) }
    const saved: WorkbenchLayout = { version: 1, revision: 1, panels: [] }
    expect(migrateLegacyWorkbench(saved, workspace)).toMatchObject({ migrated: false, layout: saved })
    const first = migrateLegacyWorkbench({ ...saved, revision: 0 }, workspace)
    expect(first.layout.panels).toHaveLength(32)
    expect(first.omittedGroups).toBe(9)
    const empty = migrateLegacyWorkbench({ ...saved, revision: 0 }, { groups: [], signals: {} })
    expect(empty.layout.panels.map(panel => panel.type)).toEqual(['variables', 'watch'])
    expect(empty.layout.panels[1]?.source.signals).toEqual([])
  })
  it('retains independent instances of the same source and avoids overlap on resize', () => {
    const layout: WorkbenchLayout = { version: 1, revision: 0, panels: [] }
    const first = addPanel(layout, { type: 'rtt', title: 'RTT A', channel: 0 })
    const second = addPanel(layout, { type: 'rtt', title: 'RTT B', channel: 0 })
    expect(first.id).not.toBe(second.id)
    expect(second.y).toBe(first.y + first.h)
    const moved = placePanel(layout.panels, { ...second, x: 6, y: 0 })
    expect(moved.y).toBe(0)
    first.view = { paused: true }; second.view = { paused: false }
    expect(validateLayout(layout).panels.map(panel => panel.view?.paused)).toEqual([true, false])
  })
  it('rejects malformed saved sources, duplicate IDs and overflowing geometry', () => {
    const layout: WorkbenchLayout = { version: 1, revision: 1, panels: [] }
    const panel = addPanel(layout, { type: 'serial', title: 'Port', port: 'COM3' })
    expect(() => validateLayout({ ...layout, panels: [panel, panel] })).toThrow()
    expect(() => validateLayout({ ...layout, panels: [{ ...panel, source: { channel: 1 } }] })).toThrow()
    expect(() => placePanel([], { ...panel, x: 11, w: 2 })).toThrow()
    expect(() => addPanel(layout, { type: 'watch', title: 'Bad', signals: Array(501).fill('x') })).toThrow()
  })
})
