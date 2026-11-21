import { afterEach, expect, it, vi } from 'vitest'
import { mountDetailsMenu } from './detailsMenu'

const disposers: Array<() => void> = []
afterEach(() => { disposers.splice(0).forEach(dispose => dispose()); document.body.innerHTML = ''; vi.restoreAllMocks() })
function fixture(native = true) {
  const details = document.createElement('details')
  details.innerHTML = '<summary>Logs</summary><div><button>Record</button></div>'
  document.body.append(details)
  const summary = details.querySelector('summary')!, menu = details.querySelector('div')!
  Object.defineProperty(menu, 'showPopover', { value: native ? vi.fn() : undefined })
  Object.defineProperty(menu, 'hidePopover', { value: vi.fn() })
  vi.spyOn(summary, 'getBoundingClientRect').mockReturnValue({ left: innerWidth - 50, right: innerWidth - 10, top: innerHeight - 35, bottom: innerHeight - 10 } as DOMRect)
  vi.spyOn(menu, 'getBoundingClientRect').mockReturnValue({ width: 180, height: 90 } as DOMRect)
  const dispose = mountDetailsMenu(details, menu); disposers.push(dispose)
  const open = () => { details.open = true; details.dispatchEvent(new Event('toggle')) }
  return { details, summary, menu, open, dispose }
}
it('keeps the menu on screen, uses the top layer, and restores focus on Escape', () => {
  const { details, summary, menu, open } = fixture(); open()
  expect(menu.showPopover).toHaveBeenCalledOnce()
  expect(parseFloat(menu.style.left) + 180).toBeLessThanOrEqual(innerWidth - 8)
  expect(parseFloat(menu.style.top) + 90).toBeLessThan(innerHeight - 35)
  menu.querySelector('button')!.focus()
  document.activeElement!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
  expect(details.open).toBe(false); expect(menu.hidePopover).toHaveBeenCalledOnce()
  expect(document.activeElement).toBe(summary)
})
it('keeps inside clicks and menu scrolling, dismisses outside, and releases listeners', () => {
  const { details, menu, open, dispose } = fixture(); open()
  menu.querySelector('button')!.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }))
  menu.dispatchEvent(new Event('scroll'))
  expect(details.open).toBe(true)
  document.body.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }))
  expect(details.open).toBe(false)
  open(); document.dispatchEvent(new Event('scroll')); expect(details.open).toBe(false)
  dispose(); details.open = true
  document.body.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }))
  expect(details.open).toBe(true)
  details.open = false
})
it('retains disclosure and dismissal when the host lacks Popover support', () => {
  const { details, menu, open } = fixture(false); open()
  expect(menu.hasAttribute('popover')).toBe(false); expect(menu.style.display).toBe('')
  document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
  expect(details.open).toBe(false); expect(menu.style.display).toBe('none')
})
it('opening another instance closes only the old menu and does not steal focus', () => {
  const first = fixture(), second = fixture()
  first.open(); second.summary.focus()
  second.summary.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }))
  second.open()
  expect(first.details.open).toBe(false); expect(second.details.open).toBe(true)
  expect(document.activeElement).toBe(second.summary)
  first.dispose(); expect(second.details.open).toBe(true)
})
