/** Address only controls actually rendered by this window, never caller selectors/JS. */
const ids = new WeakMap<Element, string>()
const controls = new Map<string, HTMLElement>()
const signatures = new Map<string, string>()
const prefix = crypto.randomUUID()
let sequence = 0
const selector = 'button,input,select,textarea,summary,a[href],[role="button"],[contenteditable="true"]'
function visible(el: HTMLElement): boolean {
  if (el instanceof HTMLInputElement && el.type === 'file') return !!el.parentElement && visible(el.parentElement)
  for (let node: HTMLElement | null = el; node; node = node.parentElement) {
    const style = getComputedStyle(node)
    if (node.hidden || style.display === 'none' || style.visibility === 'hidden' || node.hasAttribute('inert')) return false
    if (node instanceof HTMLDetailsElement && !node.open && el !== node.querySelector('summary')) return false
  }
  return el.isConnected
}
function label(el: HTMLElement) {
  const input = el as HTMLInputElement
  return (el.getAttribute('aria-label') || input.labels?.[0]?.textContent || el.getAttribute('title') ||
    el.getAttribute('placeholder') || el.textContent || el.id || el.tagName).trim().slice(0, 160)
}
function signature(el: HTMLElement) {
  return JSON.stringify([label(el), el.getAttribute('type'), el.getAttribute('data-testid'),
    el instanceof HTMLInputElement || el instanceof HTMLSelectElement || el instanceof HTMLTextAreaElement ? el.value : null,
    el instanceof HTMLInputElement ? el.checked : null])
}
function describe(el: HTMLElement) {
  let id = ids.get(el)
  if (!id) { id = `${prefix}-${++sequence}`; ids.set(el, id) }
  controls.set(id, el)
  signatures.set(id, signature(el))
  const field = el instanceof HTMLInputElement || el instanceof HTMLSelectElement || el instanceof HTMLTextAreaElement
  const secret = el instanceof HTMLInputElement && el.type === 'password'
  return { id, label: label(el), test_id: el.dataset.testid || null, tag: el.tagName.toLowerCase(),
    type: el instanceof HTMLInputElement ? el.type : null, disabled: el.matches(':disabled') || el.getAttribute('aria-disabled') === 'true',
    file_picker: el.hasAttribute('data-gui-file-picker') || (el instanceof HTMLInputElement && el.type === 'file'),
    directory_picker: el.hasAttribute('data-gui-directory-picker'),
    readonly: field && 'readOnly' in el ? el.readOnly : false,
    value: field && !secret ? el.value.slice(0, 1024) : null,
    checked: el instanceof HTMLInputElement && ['checkbox', 'radio'].includes(el.type) ? el.checked : null,
    options: el instanceof HTMLSelectElement ? [...el.options].slice(0, 64).map(o => ({ value: o.value.slice(0, 160), label: (o.label || o.textContent || '').slice(0, 160), disabled: o.disabled })) : undefined,
    options_total: el instanceof HTMLSelectElement ? el.options.length : undefined,
    context: el.closest('[data-channel]')?.getAttribute('data-channel') || null }
}
export function listGuiControls(offset = 0) {
  const active = [...document.querySelectorAll<HTMLElement>(selector)].filter(visible)
  for (const [key, value] of controls) if (!value.isConnected) { controls.delete(key); signatures.delete(key) }
  const page = active.slice(offset, offset + 50).map(describe)
  while (page.length > 1 && JSON.stringify(page).length > 18_000) page.pop()
  return { total: active.length, offset, next_offset: offset + page.length < active.length ? offset + page.length : null, controls: page }
}
export function guiControl(id: string) {
  const el = controls.get(id)
  if (!el || !visible(el)) throw new Error('Control is stale or hidden; read controls again')
  if (signatures.get(id) !== signature(el)) throw new Error('Control changed; read controls again')
  if (el.matches(':disabled') || el.getAttribute('aria-disabled') === 'true') throw new Error('Control is disabled')
  return el
}
export function interactGuiControl(id: string, action: string, value?: unknown) {
  const el = guiControl(id)
  if (action === 'control.click') {
    if (el instanceof HTMLInputElement && el.type === 'file') throw new Error('Use file.select with a file path')
    if (el instanceof HTMLAnchorElement) throw new Error('External links/downloads use their dedicated API')
    el.click()
    return
  }
  if (el instanceof HTMLInputElement && ['checkbox', 'radio'].includes(el.type)) {
    if (typeof value !== 'boolean') throw new Error('Checkbox value must be boolean')
    if (el.checked !== value) el.click()
    return
  }
  if (!(el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement) ||
      ('readOnly' in el && el.readOnly) || (el instanceof HTMLInputElement && ['file', 'button', 'submit', 'hidden'].includes(el.type))) throw new Error('Control is not an editable field')
  if (typeof value !== 'string' && typeof value !== 'number') throw new Error('Field value must be text or number')
  const text = String(value)
  if (el instanceof HTMLSelectElement && ![...el.options].some(o => o.value === text && !o.disabled)) throw new Error('Choose an available option')
  el.value = text
  el.dispatchEvent(new Event('input', { bubbles: true }))
  el.dispatchEvent(new Event('change', { bubbles: true }))
}
