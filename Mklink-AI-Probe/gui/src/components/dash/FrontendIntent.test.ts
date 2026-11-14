import { mount, flushPromises } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import FrontendIntent from './FrontendIntent.vue'

it('requires an explicit discard before composing a new request and never sends on discard', async () => {
  const pending = { request_id: 'original', session_id: 'old', page_id: 'page', object_id: 'first', message: 'Inspect first' }
  const send = vi.fn().mockRejectedValueOnce(Object.assign(new TypeError('Response lost'), { pending }))
    .mockRejectedValueOnce(Object.assign(new Error('Original target ended'), { pending, canDiscard: true }))
  const wrapper = mount(FrontendIntent, { props: { open: true, objectId: 'first', objectTitle: 'First', send } })
  try {
    await wrapper.get('textarea').setValue('Inspect first')
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(wrapper.get('textarea').attributes('disabled')).toBeDefined()
    expect(wrapper.find('[data-testid=discard-pending-intent]').exists()).toBe(false)
    await wrapper.setProps({ objectId: 'second', objectTitle: 'Second' })
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(send.mock.calls[1]![4]).toEqual(pending)
    await wrapper.get('[data-testid=discard-pending-intent]').trigger('click')
    expect(send).toHaveBeenCalledTimes(2)
    expect(wrapper.get('textarea').attributes('disabled')).toBeUndefined()
    expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toBe('')
    expect(wrapper.find('[data-testid=discard-pending-intent]').exists()).toBe(false)
  } finally { wrapper.unmount() }
})
