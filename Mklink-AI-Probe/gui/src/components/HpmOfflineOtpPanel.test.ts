import { mount } from '@vue/test-utils'
import { afterEach, expect, it } from 'vitest'
import HpmOfflineOtpPanel from './HpmOfflineOtpPanel.vue'
import { setLanguage } from '../composables/useLanguage'

afterEach(() => setLanguage('zh'))
it('defaults off and invalidates irreversible confirmation after any value change', async () => {
  const w=mount(HpmOfflineOtpPanel)
  expect(w.find('[data-testid=offline-otp-confirm]').exists()).toBe(false)
  await w.get('[data-testid=offline-otp-enable]').setValue(true)
  await w.get('[aria-label="Offline OTP desired 0"]').setValue('0x1')
  await w.get('[data-testid=offline-otp-confirm]').setValue(true)
  expect(w.emitted('change')!.at(-1)![0]).toMatchObject({confirm_irreversible:true, words:[{word:69,desired:'0x1'}]})
  await w.get('[aria-label="Offline OTP desired 0"]').setValue('0x3')
  expect(w.emitted('change')!.at(-1)![0]).toMatchObject({confirm_irreversible:false})
  await w.get('[data-testid=offline-otp-enable]').setValue(false)
  expect(w.emitted('change')!.at(-1)![0]).toBeUndefined()
  w.unmount()
})
it('explains verified programming and permanent groups in English without programming requests', async () => {
  setLanguage('en')
  const w=mount(HpmOfflineOtpPanel)
  await w.get('[data-testid=offline-otp-enable]').setValue(true)
  expect(w.text()).toContain('byte-verify every image')
  expect(w.text()).toContain('Older probe firmware requires an upgrade')
  expect(w.text()).toContain('72–75')
  expect(w.text()).toContain('76–79')
  w.unmount()
})
