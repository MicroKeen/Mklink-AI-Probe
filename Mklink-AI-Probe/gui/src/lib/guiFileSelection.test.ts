import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { listGuiControls } from './guiControls'
import { guiFileState, selectGuiFile, selectGuiDirectory, takeGuiFile, takeGuiDirectory } from './guiFileSelection'

beforeEach(() => { guiFileState.state = 'idle'; guiFileState.error = '' })
afterEach(() => { document.body.innerHTML = ''; vi.unstubAllGlobals() })

it('preserves the original backend path for symbol sidecars and directory pickers', async () => {
  document.body.innerHTML = '<button data-gui-file-picker>Symbols</button><button data-gui-directory-picker>Record</button>'
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, blob: async () => new Blob(['elf']) }))
  const [file, directory] = listGuiControls().controls
  let selected: unknown, folder: unknown
  document.querySelectorAll('button')[0]!.onclick = () => { selected = takeGuiFile() }
  document.querySelectorAll('button')[1]!.onclick = () => { folder = takeGuiDirectory() }
  selectGuiFile(file!.id, { url: '/api/runtime/control/gui-files/token', name: 'app.elf', size: 3, path: '/project/app.elf' }, () => true)
  await flushPromises()
  expect(selected).toBe('/project/app.elf')
  expect(guiFileState.state).toBe('delivered')
  expect(takeGuiFile()).toBeNull()
  selectGuiDirectory(directory!.id, '/logs')
  expect(folder).toBe('/logs')
  expect(takeGuiDirectory()).toBeNull()
})

it('does not deliver a completed file to a changed page or target', async () => {
  document.body.innerHTML = '<button data-gui-file-picker>Symbols</button>'
  const click = vi.fn()
  document.querySelector('button')!.onclick = click
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, blob: async () => new Blob(['elf']) }))
  selectGuiFile(listGuiControls().controls[0]!.id,
    { url: '/api/runtime/control/gui-files/token', name: 'app.elf', size: 3 }, () => false)
  await flushPromises()
  expect(guiFileState.state).toBe('failed')
  expect(click).not.toHaveBeenCalled()
  expect(takeGuiFile()).toBeNull()
})

it('rejects undeclared file/directory buttons and external delivery URLs', () => {
  document.body.innerHTML = '<button>Start</button><button data-gui-file-picker>Import</button>'
  const [ordinary, picker] = listGuiControls().controls
  expect(() => selectGuiDirectory(ordinary!.id, '/logs')).toThrow('declared')
  expect(() => selectGuiFile(ordinary!.id, { url: '/api/runtime/control/gui-files/token', name: 'log', size: 0 }, () => true)).toThrow('picker')
  expect(() => selectGuiFile(picker!.id, { url: 'https://other/file', name: 'log', size: 0 }, () => true)).toThrow('Invalid')
})
