import { afterEach, describe, expect, it } from 'vitest'
import { guiControl, interactGuiControl, listGuiControls } from './guiControls'
afterEach(() => { document.body.innerHTML = '' })
describe('GUI control addressing', () => {
  it('enumerates visible controls, drives real input handlers and refuses changed/hidden controls', () => {
    document.body.innerHTML = '<button>Start</button><label>Name<input value="old"></label><button disabled>Stop</button><div style="display:none"><button>Hidden</button></div><details><summary>More</summary><input value="inside"></details>'
    const page = listGuiControls()
    expect(page.total).toBe(4)
    const input = page.controls.find(c => c.tag === 'input')!
    let observed = ''
    document.querySelector('input')!.addEventListener('input', e => { observed = (e.target as HTMLInputElement).value })
    interactGuiControl(input.id, 'control.set', 'new')
    expect(observed).toBe('new')
    expect(() => interactGuiControl(input.id, 'control.set', 'lost')).toThrow('changed')
    const start = page.controls[0]!
    document.querySelector('button')!.textContent = 'Erase'
    expect(() => interactGuiControl(start.id, 'control.click')).toThrow('changed')
    expect(() => guiControl(page.controls.find(c => c.disabled)!.id)).toThrow('disabled')
  })
  it('preserves select and checkbox semantics and rejects unsupported choices', () => {
    document.body.innerHTML = '<select><option value="1">one</option><option disabled value="2">two</option><option value="3">three</option></select><input type="checkbox">'
    const [select, checkbox] = listGuiControls().controls
    expect(() => interactGuiControl(select!.id, 'control.set', '2')).toThrow('available')
    interactGuiControl(select!.id, 'control.set', '3')
    interactGuiControl(checkbox!.id, 'control.set', true)
    expect(document.querySelector('select')!.value).toBe('3')
    expect(document.querySelector('input')!.checked).toBe(true)
  })
})

it('addresses only the owning panel modal and keeps background controls blocked', () => {
  document.body.innerHTML = '<section data-gui-panel-id="one"><button>Background one</button></section><section data-gui-panel-id="two"><button>Background two</button></section><dialog open data-gui-panel-owner="one"><button>Confirm</button><input type="file"></dialog>'
  const one = document.querySelector<HTMLElement>('[data-gui-panel-id="one"]')!
  const two = document.querySelector<HTMLElement>('[data-gui-panel-id="two"]')!
  const controls = listGuiControls(0, one)
  expect(controls.controls.map(control => control.label)).toEqual(['Confirm', 'INPUT'])
  expect(controls.controls[1]?.file_picker).toBe(true)
  expect(listGuiControls(0, two).total).toBe(0)
  expect(() => guiControl(controls.controls[0]!.id, two)).toThrow('outside')
  document.querySelector('dialog')!.removeAttribute('open')
  expect(listGuiControls(0, one).controls.map(control => control.label)).toEqual(['Background one'])
})

it('names a nested select by its label without including changing option text', () => {
  document.body.innerHTML = '<label>Port <select><option>COM2</option><option>COM3</option></select></label>'
  expect(listGuiControls().controls[0]?.label).toBe('Port')
})
