import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import OfflineFlashView from './OfflineFlashView.vue'
import DeviceConfigurationPanel from '../components/DeviceConfigurationPanel.vue'
import router from '../router'
import { notifyPacksChanged, publishOnlineTarget } from '../lib/targetSelection'

const offlineMocks = vi.hoisted(() => ({
  getStatus: vi.fn(),
  listAlgorithms: vi.fn(),
  getSecurityStatus: vi.fn(),
  preview: vi.fn(),
  deploy: vi.fn(),
  deploymentStatus: vi.fn(),
  trigger: vi.fn(),
}))

const onlineMocks = vi.hoisted(() => ({
  searchTargets: vi.fn(),
  installPack: vi.fn(),
}))

const pickerMocks = vi.hoisted(() => ({ pickFlmFile: vi.fn() }))
vi.mock('../lib/filePicker', async importOriginal => ({
  ...await importOriginal<typeof import('../lib/filePicker')>(),
  pickFlmFile: pickerMocks.pickFlmFile,
}))

vi.mock('../composables/useOfflineFlashApi', async importOriginal => ({
  ...await importOriginal<typeof import('../composables/useOfflineFlashApi')>(),
  useOfflineFlashApi: () => offlineMocks,
}))

vi.mock('../composables/useOnlineFlashApi', () => ({
  useOnlineFlashApi: () => onlineMocks,
}))

describe('OfflineFlashView', () => {
  it('reads UART OTP without a BIN or SD, and discards stale data after a protocol change', async () => {
    onlineMocks.searchTargets.mockResolvedValue([{ part_number: 'HPM5301xEGx', vendor: 'HPMicro', installed: true, source: 'builtin' }])
    offlineMocks.getStatus.mockResolvedValue({ available: false })
    const wrapper = mount(OfflineFlashView)
    await flushPromises()
    await wrapper.get('[data-testid="offline-model"]').setValue('V4')
    await wrapper.get('.target-result').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="offline-protocol"]').setValue('hpm_rom_isp_uart')
    const snapshot = { part_number: 'HPM5301XEGX', chip_id: 0x11705142, hard_lock: 0, read_at: 'now', source: 'rom',
      words: [{ word: 69, current: 123, shadow: null, locked: null }] }
    vi.mocked(fetch).mockResolvedValueOnce({ ok: true, json: async () => snapshot } as Response)
    await wrapper.get('[data-testid="isp-otp-read"]').trigger('click')
    await flushPromises()
    const [url, init] = vi.mocked(fetch).mock.lastCall!
    expect(String(url)).toContain('/hpm-isp-otp/read')
    expect(JSON.parse(init!.body as string)).toEqual({ part_number: 'HPM5301XEGX', model: 'V4' })
    expect(wrapper.get('[data-testid="hpm-isp-otp"]').text()).toContain('0x0000007B')
    expect(wrapper.get('[data-testid="offline-deploy"]').attributes('disabled')).toBeDefined()
    let finish!: (value: Response) => void
    vi.mocked(fetch).mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    await wrapper.get('[data-testid="isp-otp-read"]').trigger('click')
    expect(wrapper.get('[data-testid="hpm-isp-otp"]').text()).not.toContain('0x0000007B')
    expect(wrapper.get('[data-testid="isp-otp-read"]').attributes('disabled')).toBeDefined()
    await wrapper.get('[data-testid="offline-protocol"]').setValue('debug')
    finish({ ok: true, json: async () => snapshot } as Response)
    await flushPromises()
    await wrapper.get('[data-testid="offline-protocol"]').setValue('hpm_rom_isp_uart')
    expect(wrapper.get('[data-testid="hpm-isp-otp"]').text()).not.toContain('0x0000007B')
    expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).includes('/device/connect'))).toBe(false)
    wrapper.unmount()
  })
  it('adopts online chip defaults and refreshes imported targets without a device connection', async () => {
    onlineMocks.searchTargets.mockImplementation(async (part: string) => [{ part_number: part, installed: true, vendor: 'Fixture' }])
    publishOnlineTarget('STM32F103RC')
    const wrapper = mount(OfflineFlashView)
    await flushPromises()
    expect(wrapper.text()).toContain('STM32F103RC')
    expect(offlineMocks.listAlgorithms).toHaveBeenCalledWith('STM32F103RC')
    publishOnlineTarget('STM32F407VG'); await flushPromises()
    expect(offlineMocks.listAlgorithms).toHaveBeenCalledWith('STM32F407VG')
    onlineMocks.searchTargets.mockClear()
    notifyPacksChanged(); await flushPromises()
    expect(onlineMocks.searchTargets).toHaveBeenCalledWith('STM32F407VG', { limit: 30 })
    expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).includes('/device/connect'))).toBe(false)
    wrapper.unmount()
  })
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({
      kind: 'option_bytes', read_supported: false, fields: [], reason: 'Configuration description fixture',
    }) }))
    const stored = new Map<string, string>()
    vi.stubGlobal('localStorage', {
      getItem: (key: string) => stored.get(key) ?? null,
      setItem: (key: string, value: string) => { stored.set(key, value) },
      removeItem: (key: string) => { stored.delete(key) },
      clear: () => { stored.clear() },
    })
    offlineMocks.getStatus.mockResolvedValue({
      available: true,
      disk_path: 'TEST_DISK',
      python_dir: 'TEST_DISK/python',
      flm_dir: 'TEST_DISK/FLM',
    })
    offlineMocks.listAlgorithms.mockResolvedValue([])
    offlineMocks.getSecurityStatus.mockResolvedValue({
      model: 'V3', part_number: '', supported: false,
      unlock_supported: false, lock_supported: false, family: '',
      reason: '该器件尚未通过脱机加锁/解锁真机验证',
      unlock_erases_flash: false, reversible_lock: false,
      voltage_options_mv: [], default_voltage_mv: null,
    })
    onlineMocks.searchTargets.mockResolvedValue([])
    onlineMocks.installPack.mockResolvedValue({ result: { status: 'installed' }, events: [] })
    offlineMocks.deploy.mockResolvedValue({
      status: 'deployed',
      model: 'V4',
      script_name: 'factory-download.py',
      files: ['python/factory-download.py', 'firmware.hex'],
    })
    offlineMocks.preview.mockResolvedValue({
      model: 'V4',
      script_name: 'factory-download.py',
      script: '# generated preview',
    })
    offlineMocks.trigger.mockResolvedValue({ status: 'completed', lines: ['offline download finished'] })
    vi.stubGlobal('confirm', vi.fn(() => true))
  })

  it('offers CTRL-AP recovery without a voltage control or post-download lock', async () => {
    onlineMocks.searchTargets.mockResolvedValue([{
      part_number: 'nRF54L15', vendor: 'Nordic', pack_id: '',
      pack_version: '', installed: true, source: 'builtin',
    }])
    offlineMocks.getSecurityStatus.mockResolvedValue({
      model: 'V4', part_number: 'nRF54L15', supported: true,
      unlock_supported: true, lock_supported: false, family: 'nrf54l15-ctrl-ap', reason: '',
      unlock_erases_flash: true, reversible_lock: false,
      voltage_options_mv: [], default_voltage_mv: null, apply_method: 'ctrl-ap',
    })
    const wrapper = mount(OfflineFlashView)
    await flushPromises()
    await wrapper.get('[data-testid="offline-model"]').setValue('V4')
    await wrapper.get('.target-result').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="offline-security-voltage"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="offline-lock"]').attributes('disabled')).toBeDefined()
    const unlock = wrapper.get<HTMLInputElement>('[data-testid="offline-unlock"]')
    await unlock.setValue(true)
    expect(wrapper.get('[role="alertdialog"]').text()).toContain('UICR')
    expect(wrapper.get('[role="alertdialog"]').text()).toContain('不会切换目标供电电压')
    await wrapper.get('[data-testid="confirmation-accept"]').trigger('click')
    await flushPromises()
    expect(unlock.element.checked).toBe(true)
  })

  it('registers a top-level offline flash route', () => {
    const route = router.getRoutes().find(candidate => candidate.name === 'offline-flash')
    expect(route?.path).toBe('/offline-flash')
  })

  it('requires a manual model selection and forces the V2/V3 script name', async () => {
    const wrapper = mount(OfflineFlashView)
    await flushPromises()

    expect(wrapper.text()).not.toContain('识别版本')
    expect(wrapper.get('[data-testid="offline-model"]').element).toHaveProperty('value', '')
    await wrapper.get('[data-testid="offline-model"]').setValue('V3')
    expect(wrapper.text()).toContain('offline_download.py')
    expect(wrapper.get<HTMLInputElement>('[data-testid="offline-script-name"]').element.value).toBe('offline_download.py')
    expect(wrapper.get('[data-testid="offline-script-name"]').attributes('disabled')).toBeDefined()
    expect(wrapper.find('option[value="auto"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="offline-deploy"]').attributes('disabled')).toBeDefined()
  })

  it('keeps high clocks available when switching from V3 to updated V2', async () => {
    const wrapper = mount(OfflineFlashView)
    await flushPromises()
    await wrapper.get('[data-testid="offline-model"]').setValue('V3')
    const clock = wrapper.get('[data-testid="offline-clock"]')
    expect(clock.find('option[value="20000000"]').exists()).toBe(true)
    expect(clock.find('option[value="30000000"]').exists()).toBe(true)
    await clock.setValue('30000000')
    await wrapper.get('[data-testid="offline-model"]').setValue('V2')
    expect(clock.element).toHaveProperty('value', '30000000')
    expect(clock.find('option[value="20000000"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('新版固件')
    wrapper.unmount()
  })

  it('provides multi-file firmware selection and editable BIN address and FLM bases', () => {
    const source = readFileSync('src/views/OfflineFlashView.vue', 'utf8')

    expect(source).toContain('multiple accept=".bin,.hex"')
    expect(source).toContain('v-model="item.base_address"')
    expect(source).toContain('v-model="item.flash_base"')
    expect(source).toContain('v-model="item.ram_base"')
    expect(source).toContain('自动烧录次数')
    expect(source).toContain('SWD 速率')
    expect(source).toContain('添加本地 FLM')
    expect(source).toContain('建议流程')
  })

  it('previews and deploys option-only changes without firmware, then clears them on model change', async () => {
    const wrapper = mount(OfflineFlashView)
    await flushPromises()
    await wrapper.get('[data-testid="offline-model"]').setValue('V4')
    await flushPromises()
    wrapper.getComponent(DeviceConfigurationPanel).vm.$emit('update:changes', { DATA0: '0x5A' })
    await flushPromises()
    await wrapper.get('[data-testid="offline-deploy"]').trigger('click')
    await flushPromises()
    expect(offlineMocks.preview.mock.calls[0]?.[0]).toMatchObject({ option_bytes: { DATA0: '0x5A' }, firmwares: [], algorithms: [] })
    expect(offlineMocks.deploy).toHaveBeenCalledTimes(1)
    await wrapper.get('[data-testid="offline-model"]').setValue('V3')
    await flushPromises()
    expect(wrapper.get('[data-testid="offline-deploy"]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it.each(['desktop', 'usb', 'browser'])('allows preview with a manually selected %s FLM source', async kind => {
    offlineMocks.getStatus.mockResolvedValue({ available: true, disk_path: 'G:\\', python_dir: 'G:\\python', flm_dir: 'G:\\FLM' })
    const source = kind === 'browser' ? new File(['algorithm'], 'Device.FLM')
      : kind === 'usb' ? 'G:\\FLM\\Device.FLM' : 'C:\\Users\\test\\Desktop\\Device.FLM'
    pickerMocks.pickFlmFile.mockResolvedValue(source)
    const wrapper = mount(OfflineFlashView)
    try {
      await flushPromises()
      await wrapper.get('[data-testid="offline-model"]').setValue('V4')
      await wrapper.get('[data-testid="offline-add-flm"]').trigger('click')
      await flushPromises()
      const input = wrapper.get('input[type="file"][multiple]')
      Object.defineProperty(input.element, 'files', { configurable: true, value: [new File(['hex'], 'firmware.hex')] })
      await input.trigger('change')
      expect(wrapper.find('[data-testid="offline-selection-warning"]').exists()).toBe(false)
      const previewButton = wrapper.findAll('button').find(button => button.text() === '生成预览')!
      expect(previewButton.attributes('disabled')).toBeUndefined()
      await previewButton.trigger('click')
      await flushPromises()
      expect(offlineMocks.preview).toHaveBeenCalledOnce()
      const [payload] = offlineMocks.preview.mock.calls[0]
      expect(payload.algorithms).toEqual([expect.objectContaining({
        source_kind: 'upload', file_name: 'Device.FLM',
        source_path: kind === 'browser' ? null : source,
        upload_index: kind === 'browser' ? 0 : null,
      })])
      expect(offlineMocks.deploy).not.toHaveBeenCalled()
    } finally { wrapper.unmount() }
  })

  it.each([
    ['deploy', 'offline file operation failed: Device.FLM: file is in use', 'U 盘文件更新失败'],
    ['trigger', 'Unable to connect to MKLink CDC port', '无法连接下载器命令串口'],
    ['trigger', 'Unexpected device response', 'Unexpected device response'],
  ])('shows actionable details for %s errors: %s', async (operation, detail, expected) => {
    pickerMocks.pickFlmFile.mockResolvedValue(new File(['algorithm'], 'Device.FLM'))
    if (operation === 'deploy') offlineMocks.deploy.mockRejectedValueOnce(new Error(detail))
    else offlineMocks.trigger.mockRejectedValueOnce(new Error(detail))
    const wrapper = mount(OfflineFlashView)
    try {
      await flushPromises()
      await wrapper.get('[data-testid="offline-model"]').setValue('V4')
      await wrapper.get('[data-testid="offline-add-flm"]').trigger('click')
      await flushPromises()
      const input = wrapper.get('input[type="file"][multiple]')
      Object.defineProperty(input.element, 'files', { value: [new File(['hex'], 'firmware.hex')] })
      await input.trigger('change')
      await wrapper.get('[data-testid="offline-deploy"]').trigger('click')
      await flushPromises()
      if (operation === 'trigger') {
        await wrapper.get('[data-testid="offline-trigger"]').trigger('click')
        await flushPromises()
      }
      expect(wrapper.text()).toContain(expected)
      expect(wrapper.get('.technical-error').text()).toContain(detail)
    } finally { wrapper.unmount() }
  })

  it('ignores the slow initial target search after a newer query finishes', async () => {
    vi.useFakeTimers()
    let finishInitial!: (value: unknown[]) => void
    onlineMocks.searchTargets.mockImplementationOnce(() => new Promise(resolve => { finishInitial = resolve }))
      .mockResolvedValue([{ part_number: 'STM32F103RE', vendor: 'STMicroelectronics', installed: true, source: 'builtin' }])
    const wrapper = mount(OfflineFlashView)
    try {
      await wrapper.get('[data-testid="offline-target-search"]').setValue('STM32F103RE')
      await vi.advanceTimersByTimeAsync(151)
      await flushPromises()
      finishInitial([{ part_number: 'STM32F103RC', vendor: 'STMicroelectronics' }])
      await flushPromises()
      expect(wrapper.get('.target-results').text()).toContain('STM32F103RE')
      expect(wrapper.get('.target-results').text()).not.toContain('STM32F103RC')
    } finally { wrapper.unmount(); vi.useRealTimers() }
  })

  it('searches target suggestions while typing and supports keyboard selection', async () => {
    vi.useFakeTimers()
    onlineMocks.searchTargets.mockResolvedValue([{
      part_number: 'STM32F103RE', vendor: 'STMicroelectronics', pack_id: 'Keil.STM32F1xx_DFP',
      pack_version: '2.4.1', installed: true, source: 'installed',
    }])
    offlineMocks.listAlgorithms.mockResolvedValue([{
      id: 'f103', file_name: 'STM32F10x_512.FLM', flash_base: '0x08000000', ram_base: '0x20000000',
      source_kind: 'existing', source_token: null, origin: '内置', available: true, on_probe: true,
    }])
    const wrapper = mount(OfflineFlashView, { attachTo: document.body })
    await flushPromises()
    onlineMocks.searchTargets.mockClear()

    const input = wrapper.get('[data-testid="offline-target-search"]')
    await input.trigger('focus')
    await input.setValue('STM32F103R')
    await vi.advanceTimersByTimeAsync(151)
    await flushPromises()

    expect(onlineMocks.searchTargets).toHaveBeenCalledWith('STM32F103R', { limit: 30 })
    expect(input.attributes('aria-expanded')).toBe('true')
    await input.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(wrapper.text()).toContain('已选器件')
    expect(wrapper.text()).toContain('STM32F103RE')
    wrapper.unmount()
    vi.useRealTimers()
  })

  it('shows security capability as loading before enabling a validated target', async () => {
    let resolveCapability: (value: unknown) => void = () => undefined
    offlineMocks.getSecurityStatus.mockImplementation(() => new Promise(resolve => { resolveCapability = resolve }))
    onlineMocks.searchTargets.mockResolvedValue([{
      part_number: 'STM32F103RE', vendor: 'STMicroelectronics', pack_id: null,
      pack_version: null, installed: true, source: 'builtin',
    }])
    offlineMocks.listAlgorithms.mockResolvedValue([{
      id: 'f103', file_name: 'STM32F10x_512.FLM', flash_base: '0x08000000', ram_base: '0x20000000',
      source_kind: 'existing', source_token: null, origin: '内置', available: true, on_probe: true,
    }])
    const wrapper = mount(OfflineFlashView)
    await flushPromises()
    await wrapper.get('[data-testid="offline-model"]').setValue('V3')
    await wrapper.get('.target-result').trigger('click')
    await Promise.resolve()

    expect(wrapper.text()).toContain('正在检查器件支持')
    resolveCapability({
      model: 'V3', part_number: 'STM32F103RE', supported: true,
      unlock_supported: true, lock_supported: true, family: 'stm32f103-rdp1', reason: '',
      unlock_erases_flash: true, reversible_lock: true,
      voltage_options_mv: [1800, 3300, 5000], default_voltage_mv: 3300,
    })
    await flushPromises()

    expect(wrapper.text()).toContain('加锁/解锁已验证')
    expect(wrapper.get('[data-testid="offline-unlock"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.get('[data-testid="offline-lock"]').attributes('disabled')).toBeUndefined()
  })

  it('loads dropped firmware into the offline workspace', async () => {
    const wrapper = mount(OfflineFlashView)
    await flushPromises()

    await wrapper.get('[data-testid="offline-firmware-drop-zone"]').trigger('drop', {
      dataTransfer: { files: [new File(['hex'], 'dropped.hex')] },
    })

    expect(wrapper.findAll('[data-testid="offline-firmware-row"]')).toHaveLength(1)
    expect(wrapper.get<HTMLInputElement>('.firmware-row .file-name').element.value).toBe('dropped.hex')
  })

  it('keeps same-range algorithms from different sources selectable', async () => {
    onlineMocks.searchTargets.mockResolvedValue([{
      part_number: 'DEVICE_A', vendor: 'Vendor', pack_id: 'Vendor.Device_DFP',
      pack_version: '1.0.0', installed: true, source: 'bundle',
    }])
    offlineMocks.listAlgorithms.mockResolvedValue([
      {
        id: 'builtin', file_name: 'Device.FLM',
        flash_base: '0x08000000', ram_base: '0x20000000', source_kind: 'pack',
        source_token: 'catalog:bundle:one', origin: '内置 Pack', available: true, on_probe: false,
      },
      {
        id: 'custom', file_name: 'Device.FLM',
        flash_base: '0x08000000', ram_base: '0x20000000', source_kind: 'pack',
        source_token: 'custom:one', origin: '用户 FLM', available: true, on_probe: false,
      },
    ])
    const wrapper = mount(OfflineFlashView)
    await flushPromises()

    await wrapper.get('.target-result').trigger('click')
    await flushPromises()

    expect(wrapper.findAll('[data-testid="offline-algorithm-row"]')).toHaveLength(2)
    expect(wrapper.text()).toContain('内置 Pack')
    expect(wrapper.text()).toContain('用户 FLM')
  })

  it('deploys only algorithms referenced by the flash sequence', async () => {
    onlineMocks.searchTargets.mockResolvedValue([{
      part_number: 'STM32F103RC', vendor: 'STMicroelectronics', pack_id: 'Keil.STM32F1xx_DFP',
      pack_version: '2.4.1', installed: true, source: 'installed',
    }])
    offlineMocks.listAlgorithms.mockResolvedValue([
      {
        id: 'used', file_name: 'STM32F10x_512.FLM', flash_base: '0x08000000', ram_base: '0x20000000',
        source_kind: 'existing', source_token: null, origin: 'MCU profile', available: true, on_probe: true,
      },
      {
        id: 'unused', file_name: 'STM32F10x_1024.FLM', flash_base: '0x08000000', ram_base: '0x20000000',
        source_kind: 'existing', source_token: null, origin: 'MCU profile', available: false, on_probe: false,
      },
    ])
    const wrapper = mount(OfflineFlashView)
    await flushPromises()
    await wrapper.get('[data-testid="offline-model"]').setValue('V4')
    await wrapper.get('.target-result').trigger('click')
    await flushPromises()
    const input = wrapper.get('input[type="file"][multiple]')
    Object.defineProperty(input.element, 'files', {
      configurable: true,
      value: [new File(['hex'], 'firmware.hex')],
    })
    await input.trigger('change')
    await wrapper.get('select.compact-input').setValue('used')
    await wrapper.get('[data-testid="offline-deploy"]').trigger('click')
    await flushPromises()

    expect(offlineMocks.deploy).toHaveBeenCalledOnce()
    expect(offlineMocks.deploy.mock.calls[0][0].algorithms).toEqual([
      expect.objectContaining({ id: 'used', file_name: 'STM32F10x_512.FLM' }),
    ])
  })

  it('shows an actionable warning when the selected FLM is unavailable', async () => {
    onlineMocks.searchTargets.mockResolvedValue([{
      part_number: 'STM32F103RC', vendor: 'STMicroelectronics', pack_id: 'Keil.STM32F1xx_DFP',
      pack_version: '2.4.1', installed: true, source: 'installed',
    }])
    offlineMocks.listAlgorithms.mockResolvedValue([{
      id: 'missing', file_name: 'STM32F10x_1024.FLM', flash_base: '0x08000000', ram_base: '0x20000000',
      source_kind: 'existing', source_token: null, origin: 'MCU profile', available: false, on_probe: false,
    }])
    const wrapper = mount(OfflineFlashView)
    await flushPromises()
    await wrapper.get('[data-testid="offline-model"]').setValue('V4')
    await wrapper.get('.target-result').trigger('click')
    await flushPromises()
    const input = wrapper.get('input[type="file"][multiple]')
    Object.defineProperty(input.element, 'files', {
      configurable: true,
      value: [new File(['hex'], 'firmware.hex')],
    })
    await input.trigger('change')

    expect(wrapper.get('[data-testid="offline-selection-warning"]').text()).toContain('STM32F10x_1024.FLM')
    expect(wrapper.get('[data-testid="offline-algorithm-unavailable"]').text()).toContain('选择本地 FLM')
    expect(wrapper.get('[data-testid="offline-deploy"]').attributes('disabled')).toBeDefined()
  })

  it('triggers the deployed V4 script by its configured file name', async () => {
    onlineMocks.searchTargets.mockResolvedValue([{
      part_number: 'STM32F103RC', vendor: 'STMicroelectronics', pack_id: 'Keil.STM32F1xx_DFP',
      pack_version: '2.4.1', installed: true, source: 'installed',
    }])
    offlineMocks.listAlgorithms.mockResolvedValue([{
      id: 'profile-stm32f1', file_name: 'STM32F10x_1024.FLM',
      flash_base: '0x08000000', ram_base: '0x20000000', source_kind: 'existing',
      source_token: null, origin: 'MCU profile', available: true, on_probe: true,
    }])
    const wrapper = mount(OfflineFlashView)
    await flushPromises()
    await wrapper.get('[data-testid="offline-model"]').setValue('V4')

    expect(wrapper.get('[data-testid="offline-trigger"]').attributes('disabled')).toBeDefined()
    await wrapper.get('.target-result').trigger('click')
    await flushPromises()
    const input = wrapper.get('input[type="file"][multiple]')
    Object.defineProperty(input.element, 'files', {
      configurable: true,
      value: [new File(['hex'], 'firmware.hex')],
    })
    await input.trigger('change')
    await wrapper.get('[data-testid="offline-deploy"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="offline-trigger"]').attributes('disabled')).toBeUndefined()
    await wrapper.get('[data-testid="offline-trigger"]').trigger('click')
    await flushPromises()

    expect(confirm).not.toHaveBeenCalled()
    expect(offlineMocks.trigger).toHaveBeenCalledWith(
      'V4',
      'factory-download.py',
      expect.any(Function),
      undefined, {}, undefined,
    )

    await wrapper.get('[data-testid="offline-model"]').setValue('V3')
    await flushPromises()

    expect(wrapper.get('[data-testid="offline-trigger"]').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('offline_download.py')
  })

  it('generates the preview automatically before deploying', async () => {
    offlineMocks.preview.mockResolvedValue({
      model: 'V4',
      script_name: 'factory-download.py',
      script: '# generated preview',
    })
    onlineMocks.searchTargets.mockResolvedValue([{
      part_number: 'STM32F103RC', vendor: 'STMicroelectronics', pack_id: 'Keil.STM32F1xx_DFP',
      pack_version: '2.4.1', installed: true, source: 'installed',
    }])
    offlineMocks.listAlgorithms.mockResolvedValue([{
      id: 'profile-stm32f1', file_name: 'STM32F10x_1024.FLM',
      flash_base: '0x08000000', ram_base: '0x20000000', source_kind: 'existing',
      source_token: null, origin: 'MCU profile', available: true, on_probe: true,
    }])
    const wrapper = mount(OfflineFlashView)
    await flushPromises()
    await wrapper.get('[data-testid="offline-model"]').setValue('V4')
    await wrapper.get('.target-result').trigger('click')
    await flushPromises()
    const input = wrapper.get('input[type="file"][multiple]')
    Object.defineProperty(input.element, 'files', {
      configurable: true,
      value: [new File(['hex'], 'firmware.hex')],
    })
    await input.trigger('change')

    await wrapper.get('[data-testid="offline-deploy"]').trigger('click')
    await flushPromises()

    expect(offlineMocks.preview).toHaveBeenCalledOnce()
    expect(offlineMocks.preview.mock.invocationCallOrder[0]).toBeLessThan(
      offlineMocks.deploy.mock.invocationCallOrder[0],
    )
    expect(wrapper.text()).toContain('# generated preview')
  })

  it('queries a lost deployment response without submitting again', async () => {
    offlineMocks.preview.mockResolvedValue({
      model: 'V4',
      script_name: 'factory-download.py',
      script: '# generated preview',
    })
    onlineMocks.searchTargets.mockResolvedValue([{
      part_number: 'STM32F103RC', vendor: 'STMicroelectronics', pack_id: 'Keil.STM32F1xx_DFP',
      pack_version: '2.4.1', installed: true, source: 'installed',
    }])
    offlineMocks.listAlgorithms.mockResolvedValue([{
      id: 'profile-stm32f1', file_name: 'STM32F10x_1024.FLM',
      flash_base: '0x08000000', ram_base: '0x20000000', source_kind: 'existing',
      source_token: null, origin: 'MCU profile', available: true, on_probe: true,
    }])
    offlineMocks.deploy.mockRejectedValueOnce(new Error('response lost'))
    offlineMocks.deploymentStatus.mockRejectedValueOnce(new Error('connection unavailable'))
    const wrapper = mount(OfflineFlashView)
    await flushPromises()
    await wrapper.get('[data-testid="offline-model"]').setValue('V4')
    await wrapper.get('.target-result').trigger('click')
    await flushPromises()
    const input = wrapper.get('input[type="file"][multiple]')
    Object.defineProperty(input.element, 'files', {
      configurable: true,
      value: [new File(['hex'], 'firmware.hex')],
    })
    await input.trigger('change')

    await wrapper.get('[data-testid="offline-deploy"]').trigger('click')
    await flushPromises()

    expect(offlineMocks.deploy).toHaveBeenCalledOnce()
    const id = offlineMocks.deploy.mock.calls[0][3]
    expect(id).toBeTruthy()
    expect(wrapper.find('[data-testid="deployment-request-id"]').exists()).toBe(false)
    expect(offlineMocks.deploymentStatus).toHaveBeenCalledExactlyOnceWith(id)
    expect(wrapper.get('[data-testid="offline-deploy"]').attributes('disabled')).toBeDefined()
    offlineMocks.deploymentStatus.mockResolvedValue({ state: 'succeeded', result: {
      status: 'deployed', model: 'V4', script_name: 'factory-download.py', files: ['app.hex'],
    } })
    await wrapper.get('[data-testid="deployment-query"]').trigger('click')
    await flushPromises()
    expect(offlineMocks.deploymentStatus).toHaveBeenLastCalledWith(id)
    expect(offlineMocks.deploy).toHaveBeenCalledOnce()
    expect(wrapper.text()).toContain('部署成功')
    expect(wrapper.find('[data-testid="deployment-query"]').exists()).toBe(false)
    offlineMocks.deploy.mockRejectedValueOnce(new Error('response lost again'))
    offlineMocks.deploymentStatus.mockRejectedValueOnce(new Error('No retained deployment'))
    await wrapper.get('[data-testid="offline-deploy"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('response lost again')
    expect(wrapper.text()).not.toContain('部署成功')
    expect(wrapper.get('[data-testid="offline-deploy"]').attributes('disabled')).toBeDefined()
    expect(offlineMocks.deploy).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('confirms security choices immediately and sends the validated V3 recipe', async () => {
    onlineMocks.searchTargets.mockResolvedValue([{
      part_number: 'GD32F303CET6', vendor: 'GigaDevice', pack_id: 'GigaDevice.GD32F30x_DFP',
      pack_version: '2.2.4', installed: true, source: 'installed',
    }])
    offlineMocks.listAlgorithms.mockResolvedValue([{
      id: 'gd32-main', file_name: 'GD32F30x_HD.FLM',
      flash_base: '0x08000000', ram_base: '0x20000000', source_kind: 'existing',
      source_token: null, origin: '常用型号内置算法', available: true, on_probe: true,
    }])
    offlineMocks.getSecurityStatus.mockResolvedValue({
      model: 'V3', part_number: 'GD32F303CET6', supported: true,
      unlock_supported: true, lock_supported: true, family: 'gd32f303xe-spc', reason: '',
      unlock_erases_flash: true, reversible_lock: true,
      voltage_options_mv: [1800, 3300, 5000], default_voltage_mv: 3300,
    })
    offlineMocks.deploy.mockResolvedValue({
      status: 'deployed', model: 'V3', script_name: 'offline_download.py',
      files: ['python/offline_download.py'],
    })
    const wrapper = mount(OfflineFlashView)
    await flushPromises()
    await wrapper.get('[data-testid="offline-model"]').setValue('V3')
    await wrapper.get('.target-result').trigger('click')
    await flushPromises()

    const unlock = wrapper.get<HTMLInputElement>('[data-testid="offline-unlock"]')
    await unlock.setValue(true)
    expect(wrapper.get('[role="alertdialog"]').text()).toContain('永久删除芯片全部 Flash 数据')
    expect(unlock.element.checked).toBe(false)
    await wrapper.get('[data-testid="confirmation-accept"]').trigger('click')
    await flushPromises()
    expect(unlock.element.checked).toBe(true)

    const voltage = wrapper.get<HTMLSelectElement>('[data-testid="offline-security-voltage"]')
    expect(voltage.findAll('option').map(option => option.text())).toEqual(['1.8 V', '3.3 V', '5 V'])
    await voltage.setValue('5000')
    expect(wrapper.get('[role="alertdialog"]').text()).toContain('全部负载均可承受 5V')
    await wrapper.get('[data-testid="confirmation-accept"]').trigger('click')
    await flushPromises()
    expect(voltage.element.value).toBe('5000')

    const lock = wrapper.get<HTMLInputElement>('[data-testid="offline-lock"]')
    await lock.setValue(true)
    expect(wrapper.get('[role="alertdialog"]').text()).toContain('下载成功后写入读保护')
    expect(wrapper.get('[role="alertdialog"]').text()).toContain('5V 可能损坏不耐受的目标板')
    await wrapper.get('[data-testid="confirmation-accept"]').trigger('click')
    await flushPromises()
    expect(lock.element.checked).toBe(true)
    expect(confirm).not.toHaveBeenCalled()

    const input = wrapper.get('input[type="file"][multiple]')
    Object.defineProperty(input.element, 'files', {
      configurable: true,
      value: [new File(['hex'], 'customer.hex')],
    })
    await input.trigger('change')

    const eraseAll = wrapper.get<HTMLInputElement>('[data-testid="offline-erase-all"]')
    await eraseAll.setValue(true)
    expect(wrapper.get('[role="alertdialog"]').text()).toContain('未被所选固件覆盖的引导程序、参数和用户数据')
    expect(eraseAll.element.checked).toBe(false)
    await wrapper.get('[data-testid="confirmation-accept"]').trigger('click')
    await flushPromises()
    expect(eraseAll.element.checked).toBe(true)

    await wrapper.get('[data-testid="offline-deploy"]').trigger('click')
    await flushPromises()

    expect(offlineMocks.deploy).toHaveBeenCalledOnce()
    expect(offlineMocks.deploy.mock.calls[0][0]).toEqual(expect.objectContaining({
      model: 'V3', target_part: 'GD32F303CET6',
      erase_all_before_download: true,
      unlock_before_download: true, lock_after_download: true,
      security_voltage_mv: 5000,
    }))
  })

  it('cancels a security choice and clears it when the model changes', async () => {
    onlineMocks.searchTargets.mockResolvedValue([{
      part_number: 'GD32F303CET6', vendor: 'GigaDevice', pack_id: null,
      pack_version: null, installed: true, source: 'builtin',
    }])
    offlineMocks.listAlgorithms.mockResolvedValue([{
      id: 'gd32-main', file_name: 'GD32F30x_HD.FLM',
      flash_base: '0x08000000', ram_base: '0x20000000', source_kind: 'existing',
      source_token: null, origin: '内置', available: true, on_probe: true,
    }])
    offlineMocks.getSecurityStatus.mockResolvedValue({
      model: 'V3', part_number: 'GD32F303CET6', supported: true,
      unlock_supported: true, lock_supported: true, family: 'gd32f303xe-spc', reason: '',
      unlock_erases_flash: true, reversible_lock: true,
      voltage_options_mv: [3300], default_voltage_mv: 3300,
    })
    const wrapper = mount(OfflineFlashView)
    await flushPromises()
    await wrapper.get('[data-testid="offline-model"]').setValue('V3')
    await wrapper.get('.target-result').trigger('click')
    await flushPromises()

    const unlock = wrapper.get<HTMLInputElement>('[data-testid="offline-unlock"]')
    await unlock.setValue(true)
    await wrapper.get('[data-testid="confirmation-cancel"]').trigger('click')
    await flushPromises()
    expect(unlock.element.checked).toBe(false)

    await unlock.setValue(true)
    await wrapper.get('[data-testid="confirmation-accept"]').trigger('click')
    await flushPromises()
    expect(unlock.element.checked).toBe(true)
    await wrapper.get('[data-testid="offline-model"]').setValue('V4')
    await flushPromises()
    expect(unlock.element.checked).toBe(false)
  })

  it('renders trigger output while the V4 command is still running', async () => {
    offlineMocks.preview.mockResolvedValue({
      model: 'V4', script_name: 'factory-download.py', script: '# preview',
    })
    offlineMocks.trigger.mockImplementation(async (_model, _script, onLine) => {
      onLine('erase started')
      await Promise.resolve()
      onLine('program finished')
      return { status: 'completed', lines: ['erase started', 'program finished'] }
    })
    onlineMocks.searchTargets.mockResolvedValue([{
      part_number: 'STM32F103RC', vendor: 'STMicroelectronics', pack_id: 'Keil.STM32F1xx_DFP',
      pack_version: '2.4.1', installed: true, source: 'installed',
    }])
    offlineMocks.listAlgorithms.mockResolvedValue([{
      id: 'profile-stm32f1', file_name: 'STM32F10x_1024.FLM',
      flash_base: '0x08000000', ram_base: '0x20000000', source_kind: 'existing',
      source_token: null, origin: 'MCU profile', available: true, on_probe: true,
    }])
    const wrapper = mount(OfflineFlashView)
    await flushPromises()
    await wrapper.get('[data-testid="offline-model"]').setValue('V4')
    await wrapper.get('.target-result').trigger('click')
    await flushPromises()
    const input = wrapper.get('input[type="file"][multiple]')
    Object.defineProperty(input.element, 'files', {
      configurable: true,
      value: [new File(['hex'], 'firmware.hex')],
    })
    await input.trigger('change')
    await wrapper.get('[data-testid="offline-deploy"]').trigger('click')
    await flushPromises()

    await wrapper.get('[data-testid="offline-trigger"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('.trigger-log').text()).toContain('erase started')
    expect(wrapper.get('.trigger-log').text()).toContain('program finished')
  })

  it.each(['HPM5301xEGx', 'HPM5300', 'HPM5E31', 'HPM6280', 'HPM6E80', 'HPM6750', 'HPM6880', 'HPM6P81'])('previews and deploys %s ISP images with offset addresses and voltage presets', async part => {
    onlineMocks.searchTargets.mockResolvedValue([{
      part_number: part, vendor: 'HPMicro', installed: true, source: 'builtin',
    }])
    const wrapper = mount(OfflineFlashView)
    await flushPromises()
    await wrapper.get('[data-testid="offline-model"]').setValue('V4')
    await wrapper.get('.target-result').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="offline-protocol"]').setValue('hpm_rom_isp_uart')
    expect(wrapper.get('option[value="hpm_rom_isp_uart"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.find('[data-testid="offline-clock"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('IDCODE 超时')
    expect(wrapper.text()).toContain('ROM 自动擦除并内部校验')
    expect(wrapper.findComponent(DeviceConfigurationPanel).exists()).toBe(false)
    expect(wrapper.get<HTMLSelectElement>('[data-testid="isp-baud-rate"]').element.value).toBe('2000000')
    expect(wrapper.findAll('[data-testid="isp-baud-rate"] option').map(option => option.attributes('value')))
      .toEqual(['115200', '1000000', '2000000', '5000000', '10000000'])
    await wrapper.get('[data-testid="isp-baud-rate"]').setValue('10000000')
    expect(wrapper.text()).not.toContain('给目标重新上电恢复默认速率')
    expect(wrapper.text()).not.toContain('档位依据下载器')
    expect(wrapper.find('[data-testid="isp-flash-size"]').exists()).toBe(false)
    expect(wrapper.findAll('[data-testid="isp-reset"] option').map(option => option.attributes('value')))
      .toEqual(['none', 'software', 'power_cycle'])
    const input = wrapper.get('input[type="file"][multiple]')
    Object.defineProperty(input.element, 'files', {
      configurable: true, value: [new File(['a'], 'MicroLink.bin'), new File(['b'], 'MicroLink.bin')],
    })
    await input.trigger('change')
    const rows = wrapper.findAll('[data-testid="offline-firmware-row"]')
    expect(rows).toHaveLength(2)
    expect(rows[0].get<HTMLInputElement>('input[placeholder="BIN 基地址"]').element.value).toBe('0x80000400')
    await rows[1].get('input[placeholder="BIN 基地址"]').setValue('0x80010400')
    expect(wrapper.get('[data-testid="offline-deploy"]').attributes('disabled')).toBeUndefined()
    await wrapper.findAll('button').find(button => button.text() === '生成预览')!.trigger('click')
    await flushPromises()
    expect(offlineMocks.preview).toHaveBeenCalledOnce()
    await wrapper.get('[data-testid="isp-reset"]').setValue('power_cycle')
    expect(wrapper.text()).toContain('断电持续时间（ms）')
    expect(wrapper.get<HTMLInputElement>('[data-testid="isp-voltage-3300"]').element.checked).toBe(true)
    expect(wrapper.get('[data-testid="offline-deploy"]').attributes('disabled')).toBeUndefined()
    await wrapper.get('[data-testid="isp-voltage-1800"]').setValue(true)
    await wrapper.findAll('button').find(button => button.text() === '生成预览')!.trigger('click')
    await flushPromises()
    expect(offlineMocks.preview.mock.lastCall![0].hpm_isp.completion.restore_voltage_mv).toBe(1800)
    await wrapper.get('[data-testid="isp-voltage-5000"]').setValue(true)
    expect(wrapper.get('[role="alertdialog"]').text()).toContain('确定选择 5V')
    await wrapper.get('[data-testid="confirmation-cancel"]').trigger('click')
    await flushPromises()
    expect(wrapper.get<HTMLInputElement>('[data-testid="isp-voltage-1800"]').element.checked).toBe(true)
    await wrapper.get('[data-testid="isp-voltage-5000"]').setValue(true)
    await wrapper.get('[data-testid="confirmation-accept"]').trigger('click')
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === '生成预览')!.trigger('click')
    await flushPromises()
    expect(offlineMocks.preview.mock.lastCall![0].hpm_isp.completion.restore_voltage_mv).toBe(5000)
    await wrapper.get('[data-testid="isp-reset"]').setValue('software')
    expect(wrapper.text()).not.toContain('断电持续时间（ms）')
    await wrapper.findAll('button').find(button => button.text() === '生成预览')!.trigger('click')
    await flushPromises()
    expect(offlineMocks.preview.mock.lastCall![0].hpm_isp.completion.restore_voltage_mv).toBeNull()
    await wrapper.get('[data-testid="isp-reset"]').setValue('power_cycle')
    expect(wrapper.get<HTMLInputElement>('[data-testid="isp-voltage-3300"]').element.checked).toBe(true)
    const count = wrapper.findAll('label').find(label => label.text().includes('自动烧录次数'))!
    await count.get('input').setValue('10')
    expect(wrapper.find('[data-testid="isp-confirm-cycles"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('等待目标退出 ISP')
    expect(wrapper.get('[data-testid="offline-deploy"]').attributes('disabled')).toBeUndefined()
    const previewButton = wrapper.findAll('button').find(button => button.text() === '生成预览')!
    expect(previewButton.attributes('disabled')).toBeUndefined()
    await previewButton.trigger('click')
    await flushPromises()
    expect(offlineMocks.preview.mock.lastCall![0].auto_download_count).toBe(10)
    await wrapper.get('[data-testid="offline-deploy"]').trigger('click')
    await flushPromises()
    const config = offlineMocks.deploy.mock.calls[0][0]
    expect(config.programming_protocol).toBe('hpm_rom_isp_uart')
    expect(config.target_part).toBe(part)
    expect(config.board).toBeNull()
    expect(config.hpm_isp.flash_size).toBeUndefined()
    expect(config.hpm_isp.baud_rate).toBe(10000000)
    expect(config.hpm_isp.nor_options).toEqual(['0xFCF90002', '0x6', '0x1000'])
    expect(config.hpm_isp.completion.restore_voltage_mv).toBe(3300)
    expect(config.auto_download_count).toBe(10)
    expect(config.hpm_isp.rearm_mode).toBe('isp_reconnect')
    expect(config.hpm_isp.confirm_reconnect_cycles).toBeUndefined()
    expect(config.firmwares.map((f: { base_address: string }) => f.base_address)).toEqual(['0x80000400', '0x80010400'])
    expect(config.firmwares.map((f: { file_name: string }) => f.file_name)).toEqual(['MicroLink.bin', 'MicroLink-2.bin'])
    let finish!: (value: { status: string; lines: string[] }) => void
    offlineMocks.trigger.mockImplementationOnce((_model, _name, onLine) => {
      onLine('import hpm')
      onLine('HPM_ISP {"schema":1,"event":"waiting","cycle":1,"total":10}')
      onLine('HPM_ISP {"schema":1,"event":"connected"}')
      return new Promise(resolve => { finish = resolve })
    })
    await wrapper.get('[data-testid="offline-trigger"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alertdialog"]').text()).toContain('恢复 3.3V')
    expect(offlineMocks.trigger).not.toHaveBeenCalled()
    await wrapper.get('[data-testid="confirmation-accept"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="isp-connection"]').text()).toContain('ISP 已连接')
    expect(wrapper.find('.script-preview').exists()).toBe(false)
    expect(wrapper.get('.trigger-log').text()).toBe('ISP waiting 1/10\nISP connected')
    expect(wrapper.text()).not.toContain('import hpm')
    offlineMocks.trigger.mock.lastCall![2]('HPM_ISP {"schema":1,"event":"cycle_done","completed":1,"total":10}')
    await flushPromises()
    expect(wrapper.get('[data-testid="isp-connection"]').text()).toContain('已连接 · 本轮烧录完成')
    offlineMocks.trigger.mock.lastCall![2]('HPM_ISP {"schema":1,"event":"disconnected"}')
    await flushPromises()
    expect(wrapper.get('[data-testid="isp-connection"]').text()).toContain('等待 ISP 握手')
    finish({ status: 'unknown', lines: [] })
    await flushPromises()
    expect(wrapper.get('.trigger-log').text()).toContain('ISP connected')
    expect(wrapper.text()).toContain('运行结果未确认')
    expect(wrapper.get('[data-testid="offline-trigger"]').attributes('disabled')).toBeDefined()
    await wrapper.get('[data-testid="offline-protocol"]').setValue('debug')
    expect(wrapper.find('[data-testid="hpm-isp-settings"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="offline-clock"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="offline-trigger"]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it('persists and restores the selected ISP baud preset', async () => {
    onlineMocks.searchTargets.mockResolvedValue([{
      part_number: 'HPM5301', vendor: 'HPMicro', installed: true, source: 'builtin',
    }])
    localStorage.setItem('mklink.offlineFlash.settings', JSON.stringify({ model: 'V4', ispBaudRate: 5000000 }))
    async function openIsp() {
      const wrapper = mount(OfflineFlashView)
      await flushPromises()
      await wrapper.get('.target-result').trigger('click')
      await flushPromises()
      await wrapper.get('[data-testid="offline-protocol"]').setValue('hpm_rom_isp_uart')
      return wrapper
    }
    let wrapper = await openIsp()
    expect(wrapper.get<HTMLSelectElement>('[data-testid="isp-baud-rate"]').element.value).toBe('5000000')
    await wrapper.get('[data-testid="isp-baud-rate"]').setValue('10000000')
    expect(JSON.parse(localStorage.getItem('mklink.offlineFlash.settings')!).ispBaudRate).toBe(10000000)
    wrapper.unmount()
    wrapper = await openIsp()
    expect(wrapper.get<HTMLSelectElement>('[data-testid="isp-baud-rate"]').element.value).toBe('10000000')
    wrapper.unmount()
  })

  it.each([0, -1, 1.5, 4294967296, '2M', null, 3456789, 4000000, 12500000])('uses the 2M default for invalid saved ISP baud %s', async savedBaud => {
    localStorage.setItem('mklink.offlineFlash.settings', JSON.stringify({ model: 'V4', ispBaudRate: savedBaud }))
    onlineMocks.searchTargets.mockResolvedValue([{
      part_number: 'HPM5301', vendor: 'HPMicro', installed: true, source: 'builtin',
    }])
    const wrapper = mount(OfflineFlashView)
    await flushPromises()
    await wrapper.get('.target-result').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="offline-protocol"]').setValue('hpm_rom_isp_uart')
    expect(wrapper.get<HTMLSelectElement>('[data-testid="isp-baud-rate"]').element.value).toBe('2000000')
    wrapper.unmount()
  })

  it.each(['bin', 'hex'])('configures HPM %s download without Pack or FLM algorithms', async (format) => {
    onlineMocks.searchTargets.mockResolvedValue([{
      part_number: 'HPM5301xEGx', vendor: 'HPMicro', pack_id: null,
      pack_version: null, installed: true, source: 'builtin',
    }])
    const wrapper = mount(OfflineFlashView)
    await flushPromises()
    await wrapper.get('[data-testid="offline-model"]').setValue('V4')

    await wrapper.get('.target-result').trigger('click')
    await flushPromises()
    const input = wrapper.get('input[type="file"][multiple]')
    Object.defineProperty(input.element, 'files', {
      configurable: true,
      value: [new File(['firmware'], `app.${format}`)],
    })
    await input.trigger('change')
    await wrapper.get('[data-testid="offline-deploy"]').trigger('click')
    await flushPromises()

    expect(onlineMocks.installPack).not.toHaveBeenCalled()
    expect(offlineMocks.listAlgorithms).not.toHaveBeenCalled()
    expect(offlineMocks.deploy).toHaveBeenCalledOnce()
    const payload = offlineMocks.deploy.mock.calls[0][0]
    expect(payload.target_part).toBe('HPM5301xEGx')
    expect(payload.board).toBe('hpm5301evklite')
    expect(payload.algorithms).toEqual([])
    expect(payload.firmwares[0].algorithm_id).toBe('')
    expect(payload.firmwares[0].base_address).toBe(format === 'bin' ? '0x80000400' : null)
    expect(payload.firmwares[0].format).toBe(format)
  })
})
