import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import HpmOfflineOtpPanel from './HpmOfflineOtpPanel.vue'
import { setLanguage } from '../composables/useLanguage'

const status = ref({ connected: false, probe_id: 'usb-a', device_generation: 1 })
vi.mock('../composables/useMklinkApi', () => ({ useMklinkApi: () => ({ deviceStatus: status }) }))
const fetchMock = vi.fn()
const wrappers: ReturnType<typeof mount>[] = []
const snapshot = () => ({ words: Array.from({ length: 11 }, (_, i) => ({ word: i + 69, current: 0, shadow: 0, locked: false })), hard_lock: 0 })
function panel() {
  const w = mount(HpmOfflineOtpPanel, { props: { partNumber: 'HPM5301', probeId: 'usb-a' }, global: { stubs: { DeviceConfigurationPanel: true } } })
  wrappers.push(w); return w
}
async function add(w: ReturnType<typeof panel>, desired = '0x00000001') {
  await w.get('[data-testid=offline-otp-write-view]').trigger('click')
  await w.get('[data-testid=offline-otp-add]').trigger('click')
  await w.get('[aria-label="OTP word values"]').setValue(desired)
  await w.get('form').trigger('submit')
}
beforeEach(() => { status.value = { connected: false, probe_id: 'usb-a', device_generation: 1 }; fetchMock.mockReset(); vi.stubGlobal('fetch', fetchMock) })
afterEach(() => { wrappers.splice(0).forEach(w => w.unmount()); vi.unstubAllGlobals(); setLanguage('zh') })

it('keeps offline recipes inactive until explicit expected values and confirmation; edits invalidate confirmation', async () => {
  const w = panel()
  expect(w.get('[data-testid=offline-otp-read]').attributes('disabled')).toBeDefined()
  await add(w)
  expect(w.get('[data-testid=offline-otp-confirm]').attributes('disabled')).toBeDefined()
  expect(w.emitted('change')!.at(-1)).toEqual([undefined, true])
  await w.get('[aria-label="OTP expected 69"]').setValue('0')
  await w.get('[data-testid=offline-otp-confirm]').setValue(true)
  expect(w.emitted('change')!.at(-1)![0]).toMatchObject({ confirm_irreversible: true, words: [{ word: 69, expected: '0x00000000', desired: '0x00000001' }] })
  await w.get('[aria-label="OTP expected 69"]').setValue('2')
  expect(w.emitted('change')!.at(-1)).toEqual([undefined, true])
  expect(w.get('[data-testid=offline-otp-confirm]').attributes('disabled')).toBeDefined()
  await w.get('[data-testid=offline-otp-clear]').trigger('click')
  expect(w.emitted('change')!.at(-1)).toEqual([undefined, false])
  expect(fetchMock).not.toHaveBeenCalled()
})

it('reads the selected current generation and retains a draft across ordinary status polls', async () => {
  status.value.connected = true
  fetchMock.mockResolvedValue({ ok: true, json: async () => snapshot() })
  const w = panel()
  await w.get('[data-testid=offline-otp-read]').trigger('click'); await flushPromises()
  expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/hpm-user-otp/read'), expect.objectContaining({ headers: expect.objectContaining({ 'X-MKLink-Probe': 'usb-a', 'X-MKLink-Device-Generation': '1' }) }))
  await add(w)
  expect(w.get<HTMLInputElement>('[aria-label="OTP expected 69"]').element.value).toBe('0x00000000')
  await w.get('[data-testid=offline-otp-confirm]').setValue(true)
  status.value = { ...status.value }; await flushPromises()
  expect(w.get<HTMLInputElement>('[data-testid=offline-otp-confirm]').element.checked).toBe(true)
  status.value = { ...status.value, device_generation: 2 }; await flushPromises()
  expect(w.find('[aria-label="OTP expected 69"]').exists()).toBe(false)
  expect(w.emitted('change')!.at(-1)).toEqual([undefined, false])
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

it('does not read another probe and discards a response after device switching', async () => {
  status.value = { connected: true, probe_id: 'usb-b', device_generation: 1 }
  const w = panel()
  expect(w.get('[data-testid=offline-otp-read]').attributes('disabled')).toBeDefined()
  status.value.probe_id = 'usb-a'; await flushPromises()
  let resolve!: (v: unknown) => void
  fetchMock.mockReturnValue(new Promise(r => { resolve = r }))
  await w.get('[data-testid=offline-otp-read]').trigger('click')
  status.value.probe_id = 'usb-b'; await flushPromises()
  resolve({ ok: true, json: async () => snapshot() }); await flushPromises()
  expect(w.text()).not.toContain('HARD_LOCK 0x00000000')
  expect(w.get('[data-testid=offline-otp-read]').attributes('disabled')).toBeDefined()
})

it('rejects words outside the qualified user area and disables confirmation for locked words', async () => {
  status.value.connected = true
  const data = snapshot(); data.words[0]!.locked = true
  fetchMock.mockResolvedValue({ ok: true, json: async () => data })
  const w = panel(); await w.get('[data-testid=offline-otp-read]').trigger('click'); await flushPromises()
  await add(w)
  expect(w.get('[data-testid=offline-otp-confirm]').attributes('disabled')).toBeDefined()
  await w.get('[data-testid=offline-otp-add]').trigger('click')
  await w.get('[aria-label="OTP start word"]').setValue(68)
  await w.get('form').trigger('submit')
  expect(w.get('[role=alert]').text()).toContain('69–79')
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

it('requires an explicit HARD_LOCK value and reconfirmation for permanent groups', async () => {
  setLanguage('en')
  const w = panel(); await w.get('[data-testid=offline-otp-write-view]').trigger('click')
  expect(w.text()).toContain('byte-verify every image')
  expect(w.text()).toContain('Older probe firmware requires an upgrade')
  await w.get('input[type=checkbox][value="18"]').setValue(true)
  expect(w.get('[data-testid=offline-otp-confirm]').attributes('disabled')).toBeDefined()
  await w.get('[aria-label="Offline OTP hard lock"]').setValue('0x00000000')
  await w.get('[data-testid=offline-otp-confirm]').setValue(true)
  expect(w.emitted('change')!.at(-1)![0]).toMatchObject({ locks: [18], expected_hard_lock: '0x00000000', words: [], confirm_irreversible: true })
  await w.get('input[type=checkbox][value="19"]').setValue(true)
  expect(w.emitted('change')!.at(-1)).toEqual([undefined, true])
  expect(fetchMock).not.toHaveBeenCalled()
})
