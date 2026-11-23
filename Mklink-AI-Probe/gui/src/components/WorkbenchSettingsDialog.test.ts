import { DOMWrapper, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import WorkbenchSettingsDialog from './WorkbenchSettingsDialog.vue'

it('preserves drafts when clicking dialog padding, closes on the backdrop, and restores focus', async () => {
  const opener = document.createElement('button')
  document.body.append(opener); opener.focus()
  const wrapper = mount(WorkbenchSettingsDialog, { props: { title: 'Configuration' }, slots: { default: '<input value="unsaved draft" />' } })
  const element = document.body.querySelector('dialog')!
  vi.spyOn(element, 'getBoundingClientRect').mockReturnValue({ left: 100, right: 500, top: 100, bottom: 500 } as DOMRect)
  const dialog = new DOMWrapper(element)
  await dialog.trigger('click', { clientX: 110, clientY: 110 })
  expect(wrapper.emitted('close')).toBeUndefined()
  expect(element.querySelector('input')!.value).toBe('unsaved draft')
  await dialog.trigger('click', { clientX: 90, clientY: 110 })
  expect(wrapper.emitted('close')).toHaveLength(1)
  wrapper.unmount(); expect(document.activeElement).toBe(opener); opener.remove()
})
