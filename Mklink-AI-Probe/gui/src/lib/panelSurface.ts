import { nextTick, type Ref } from 'vue'
import { dispatchFrontend, interaction, objectSchema, type SemanticAction, type SemanticSurface } from './frontendControl'
import { listGuiControls, interactGuiControl, guiPanelRoots, guiControl, guiControlLabel } from './guiControls'
import { guiFileState, selectGuiDirectory } from './guiFileSelection'
import type { GuiPanelScope } from './guiAutomation'

/** Reuse the rendered GUI handlers and their confirmations inside one stable panel. */
export function panelSurface(root: Ref<HTMLElement | null>, scope: GuiPanelScope, child: Ref<SemanticSurface | null>): SemanticSurface {
  const control = { control_id: { type: 'string', maxLength: 100 } }
  const offset = { offset: { type: 'integer', minimum: 0, maximum: 100000 } }
  const originalActions = () => [...scope.panels.values()].flatMap(panel => Object.keys(panel.actions))
  function element() { if (!root.value?.isConnected) throw new Error('Panel is not mounted'); return root.value }
  function text() { return guiPanelRoots(element()).filter(node => !(node instanceof HTMLDialogElement) || node.open).map(node => node.innerText || node.textContent || '').join('\n') }
  function catalog(): SemanticAction[] {
    return [...(child.value?.catalog?.() || []),
      { name: 'view.controls', description: 'List this panel’s current visible controls and file pickers; fresh IDs are required', args: objectSchema(offset, []), effect: 'view' },
      { name: 'view.read', description: 'Read rendered results, errors and registered chart/replay state in this panel', args: objectSchema(offset, []), effect: 'view' },
      { name: 'view.control.click', description: 'Activate the original GUI control. Dispatched is not device completion; inspect resulting state/confirmation/job', args: objectSchema(control), effect: 'device' },
      { name: 'view.control.set', description: 'Change a field through its original handlers, including automatic device/settings updates; inspect resulting state', args: objectSchema({ ...control, value: { type: 'string', maxLength: 32768 } }), effect: 'device' },
      { name: 'view.control.check', description: 'Set a checkbox/radio through its original handler; some switches change device settings', args: objectSchema({ ...control, checked: { type: 'boolean' } }), effect: 'device' },
      { name: 'view.directory.select', description: 'Supply a directory to a declared picker in this panel', args: objectSchema({ ...control, path: { type: 'string', maxLength: 4096 } }), effect: 'file' },
      ...(originalActions().length ? [{ name: 'view.action', description: 'Run a component-owned display action in this instance only', args: objectSchema({ name: { type: 'string', enum: originalActions() }, seconds: { type: 'number', minimum: 0, maximum: 60 } }, ['name']), effect: 'view' }] : []),
    ]
  }
  function states() { return Object.fromEntries([...scope.panels].map(([id, panel]) => [id, panel.snapshot()])) }
  return {
    catalog,
    readValues: () => child.value?.readValues?.() || {},
    // Live counters and output belong to view.read, not optimistic configuration revisions.
    read: () => ({ ...(child.value?.read?.() || {}), ready: !!root.value, gui: root.value ? { registered_panels: [...scope.panels.keys()], file: { ...guiFileState } } : null }),
    restore: value => child.value?.restore?.(value),
    execute: async (action, args, context) => {
      const descriptor = catalog().find(item => item.name === action)
      if (!descriptor) throw new Error('Panel action is unavailable')
      interaction.validateArgs(args, descriptor.args)
      if (!action.startsWith('view.')) {
        if (!child.value) throw new Error('Panel is still loading')
        return child.value.execute(action, args, context)
      }
      const host = element()
      if (action === 'view.controls') return listGuiControls(args.offset || 0, host)
      if (action === 'view.read') {
        const content = text(), start = args.offset || 0
        return { text: content.slice(start, start + 8000), next_offset: start + 8000 < content.length ? start + 8000 : null, states: states(), file: { ...guiFileState } }
      }
      const operation = args.control_id ? guiControlLabel(guiControl(args.control_id, host)) : args.name
      if (action === 'view.directory.select') selectGuiDirectory(args.control_id, args.path, host)
      else if (action === 'view.action') {
        const panel = [...scope.panels.values()].find(item => item.actions[args.name])
        if (!panel) throw new Error('Component action is no longer available')
        await panel.actions[args.name]!({ action: args.name, seconds: args.seconds })
      } else dispatchFrontend(context, () => interactGuiControl(args.control_id, action === 'view.control.click' ? 'control.click' : 'control.set', action === 'view.control.check' ? args.checked : args.value, host))
      await nextTick()
      return { status: 'dispatched', operation, message: 'Inspect panel state and the original operation/job before treating this as complete or retrying.', states: states() }
    },
  }
}
