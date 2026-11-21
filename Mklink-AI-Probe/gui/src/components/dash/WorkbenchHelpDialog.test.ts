import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import WorkbenchHelpDialog from './WorkbenchHelpDialog.vue'
import { language, setLanguage } from '../../composables/useLanguage'
import { writeClipboard } from '../../lib/writeClipboard'

vi.mock('../../lib/writeClipboard', () => ({ writeClipboard: vi.fn() }))
const initialLanguage = language.value
afterEach(() => { vi.resetAllMocks(); setLanguage(initialLanguage) })

it.each(['zh', 'en'] as const)('copies the visible %s instructions, examples and discovery steps', async lang => {
  setLanguage(lang)
  const wrapper = mount(WorkbenchHelpDialog, { attachTo: document.body })
  try {
    const dialog = document.querySelector<HTMLDialogElement>('dialog')!
    dialog.querySelector<HTMLButtonElement>('footer button')!.click()
    await flushPromises()
    const text = vi.mocked(writeClipboard).mock.calls[0]![0]
    for (const item of dialog.querySelectorAll('section p, li')) expect(text).toContain(item.textContent)
    for (const entry of ['references/agent-ui.md','runtime_status','gui_control','gui_frontend_read']) expect(text).toContain(entry)
    expect(dialog.querySelector('[role=status]')?.textContent).toContain(lang === 'zh' ? '已复制' : 'Copied')
    expect(text).not.toMatch(/https?:\/\/|[A-Z]:\\|_runtime\/open#/)
  } finally { wrapper.unmount() }
})

it('selects the same instructions for manual copy and allows a retry', async () => {
  vi.mocked(writeClipboard).mockRejectedValueOnce(Error('denied'))
  const wrapper = mount(WorkbenchHelpDialog, { attachTo: document.body })
  try {
    const dialog = document.querySelector('dialog')!
    const button = dialog.querySelector<HTMLButtonElement>('footer button')!
    button.click()
    await flushPromises(); await nextTick()
    const field = dialog.querySelector('textarea')!
    expect(field.value).toBe(vi.mocked(writeClipboard).mock.calls[0]![0])
    expect([field.selectionStart, field.selectionEnd]).toEqual([0, field.value.length])
    expect(document.activeElement).toBe(field)
    button.click()
    await flushPromises()
    expect(dialog.querySelector('textarea')).toBeNull()
    expect(dialog.querySelector('[role=status]')?.textContent).toMatch(/已复制|Copied/)
  } finally { wrapper.unmount() }
})
