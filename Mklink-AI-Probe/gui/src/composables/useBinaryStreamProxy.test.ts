import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { useBinaryStream, type BinaryStreamName } from './useBinaryStream'
import type { StreamClientOptions } from '../lib/stream/streamClient'

vi.mock('../lib/runtimeEndpoint', () => ({ API_BASE: '/apps/probe/content', IS_REMOTE: false }))

describe('binary streams behind a directory proxy', () => {
  it.each<[BinaryStreamName, string]>([
    ['serial', ''], ['superwatch', '?continuity=1&latest64=1'], ['rtt', ''],
    ['rtt-terminal', ''], ['systemview', ''], ['vofa', ''],
  ])(
    'connects %s under the same prefix as HTTP', (stream, expectedSearch) => {
      let options: StreamClientOptions | undefined
      const dispose = vi.fn()
      const wrapper = mount(defineComponent({
        setup() {
          useBinaryStream(stream, {
            capacity: 10, channelCount: 1,
            createClient: next => {
              options = next
              return {
                start: vi.fn(), stop: vi.fn(), reset: vi.fn(), configure: vi.fn(),
                requestVisibleRange: vi.fn(), dispose,
              }
            },
          })
          return () => null
        },
      }))
      const url = new URL(options!.url)
      expect(url.host).toBe(window.location.host)
      expect(url.pathname).toBe(`/apps/probe/content/ws/streams/${stream}`)
      if (stream.startsWith('rtt')) {
        expect(url.searchParams.get('view')).toBeTruthy()
        url.searchParams.delete('view')
      }
      expect(url.search).toBe(expectedSearch)
      expect(url.hash).toBe('')
      wrapper.unmount()
      expect(dispose).toHaveBeenCalledOnce()
    },
  )
})
