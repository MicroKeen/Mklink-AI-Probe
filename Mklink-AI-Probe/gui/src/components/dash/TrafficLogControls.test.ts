import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, expect, it, vi } from 'vitest'
import TrafficLogControls from './TrafficLogControls.vue'
const logText = (kind='rtt') => [
  {type:'mklink-traffic',version:1,kind},
  {type:'data',source:'0',session:'s',direction:'RX',time:10,hex:'00ff',lost_bytes:0},
  {type:'data',source:'1',session:'s',direction:'RX',time:11,hex:'01',lost_bytes:0},
  {type:'data',source:'0',session:'s',direction:'TX',time:12,hex:'6162',lost_bytes:0},
  {type:'end',complete:true},
].map(r=>JSON.stringify(r)).join('\n')
afterEach(()=>vi.useRealTimers())
async function open(wrapper: any, text=logText()) {
  const input = wrapper.get('input[type=file]')
  Object.defineProperty(input.element,'files',{configurable:true,value:[{name:'test.jsonl',size:text.length,text:async()=>text}]})
  await input.trigger('change'); await flushPromises()
}
it('replays by recorded time, pauses, seeks, selects sources and exits without hardware requests', async()=>{
  vi.useFakeTimers()
  const wrapper=mount(TrafficLogControls,{props:{kind:'rtt'},global:{stubs:{SuperWatchRecording:true}}})
  try {
    await open(wrapper)
    expect(wrapper.emitted('state')).toEqual([[true]])
    await wrapper.get('[data-testid=traffic-play]').trigger('click')
    await vi.advanceTimersByTimeAsync(30)
    expect(wrapper.emitted('batch')!.at(-1)![0]).toEqual([expect.objectContaining({hex:'00ff'})])
    await wrapper.get('[data-testid=traffic-play]').trigger('click')
    const count=wrapper.emitted('batch')!.length
    await vi.advanceTimersByTimeAsync(4000)
    expect(wrapper.emitted('batch')!.length).toBe(count)
    await wrapper.get('[data-testid=traffic-seek]').setValue('2')
    expect(wrapper.emitted('batch')!.at(-1)![0]).toHaveLength(2)
    await wrapper.get('select').setValue('1')
    await wrapper.get('[data-testid=traffic-seek]').setValue('1')
    expect(wrapper.emitted('batch')!.at(-1)![0]).toEqual([expect.objectContaining({source:'1'})])
    await wrapper.get('[data-testid=traffic-close]').trigger('click')
    expect(wrapper.emitted('state')!.at(-1)).toEqual([false])
    expect(wrapper.find('[data-testid=traffic-replay]').exists()).toBe(false)
  } finally {wrapper.unmount()}
})
it('rejects wrong formats without disturbing a loaded replay and blocks opening during recording',async()=>{
  const wrapper=mount(TrafficLogControls,{props:{kind:'serial'},global:{stubs:{SuperWatchRecording:true}}})
  try {
    await open(wrapper)
    expect(wrapper.find('[role=alert]').exists()).toBe(true)
    expect(wrapper.emitted('state')).toBeUndefined()
    await open(wrapper,logText('serial'))
    await open(wrapper,'bad')
    expect(wrapper.find('[data-testid=traffic-replay]').exists()).toBe(true)
    wrapper.findComponent({name:'SuperWatchRecording'}).vm.$emit('state','recording')
    await flushPromises()
    expect(wrapper.get('[data-testid=traffic-open]').attributes('disabled')).toBeDefined()
  } finally {wrapper.unmount()}
})
