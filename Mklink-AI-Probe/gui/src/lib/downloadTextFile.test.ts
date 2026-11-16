import { afterEach, describe, expect, it, vi } from 'vitest'
import { downloadTextFile, saveBlobFile, timestampedLogName } from './downloadTextFile'

describe('downloadTextFile', () => {
  afterEach(() => {
    delete (window as Window & { showSaveFilePicker?: unknown }).showSaveFilePicker
    delete (navigator as unknown as { userActivation?: unknown }).userActivation
    vi.doUnmock('@tauri-apps/api/core')
    vi.doUnmock('@tauri-apps/plugin-dialog')
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    vi.resetModules()
    vi.useRealTimers()
  })

  it('downloads a UTF-8 text file and releases the object URL', () => {
    vi.useFakeTimers()
    const createObjectURL = vi.fn().mockReturnValue('blob:test')
    const revokeObjectURL = vi.fn()
    const click = vi.fn()
    const remove = vi.fn()
    const appendChild = vi.spyOn(document.body, 'appendChild').mockImplementation(node => node)
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL })
    vi.spyOn(document, 'createElement').mockReturnValue({
      href: '', download: '', style: {}, click, remove,
    } as unknown as HTMLAnchorElement)

    downloadTextFile('serial.log', '温度=25')

    const blob = createObjectURL.mock.calls[0][0] as Blob
    expect(blob.type).toBe('text/plain;charset=utf-8')
    expect(appendChild).toHaveBeenCalledTimes(1)
    expect(click).toHaveBeenCalledTimes(1)
    expect(remove).toHaveBeenCalledTimes(1)
    expect(revokeObjectURL).not.toHaveBeenCalled()
    vi.runAllTimers()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:test')
  })

  it('creates filesystem-safe timestamped log names', () => {
    expect(timestampedLogName('rtt', new Date('2026-08-10T01:02:03.456Z')))
      .toBe('rtt-2026-08-10T01-02-03-456Z.log')
  })

  it('uses the browser file picker when the user chooses a save location', async () => {
    const write = vi.fn().mockResolvedValue(undefined)
    const close = vi.fn().mockResolvedValue(undefined)
    const picker = vi.fn().mockResolvedValue({
      createWritable: vi.fn().mockResolvedValue({ write, close }),
    })
    Object.defineProperty(window, 'showSaveFilePicker', {
      value: picker,
      configurable: true,
    })
    const blob = new Blob(['uf2'], { type: 'application/octet-stream' })

    await expect(saveBlobFile('MicroLink_V3.3.7.uf2', blob)).resolves.toBe(true)

    expect(picker).toHaveBeenCalledWith(expect.objectContaining({
      suggestedName: 'MicroLink_V3.3.7.uf2',
    }))
    expect(write).toHaveBeenCalledWith(blob)
    expect(close).toHaveBeenCalledOnce()
  })

  it('uses a matching native extension and writes the selected desktop file', async () => {
    const save = vi.fn().mockResolvedValue('C:\\captures\\superwatch.csv')
    const invoke = vi.fn().mockResolvedValue(undefined)
    vi.doMock('@tauri-apps/api/core', () => ({ isTauri: () => true, invoke }))
    vi.doMock('@tauri-apps/plugin-dialog', () => ({ save }))
    const { saveTextFile } = await import('./downloadTextFile')

    await expect(saveTextFile('superwatch.csv', 'time,value\n0,1')).resolves.toBe(true)

    expect(save).toHaveBeenCalledWith({
      defaultPath: 'superwatch.csv',
      filters: [{ name: 'MKLink Data', extensions: ['csv'] }],
    })
    expect(invoke).toHaveBeenCalledWith('write_file', {
      path: 'C:\\captures\\superwatch.csv',
      contents: Array.from(new TextEncoder().encode('time,value\n0,1')),
    })
  })

  it.each(['expired', 'denied'])('downloads asynchronously prepared bytes when activation is %s', async reason => {
    const picker = vi.fn().mockRejectedValue(new DOMException('User gesture required', 'SecurityError'))
    Object.defineProperty(window, 'showSaveFilePicker', { value: picker, configurable: true })
    Object.defineProperty(navigator, 'userActivation', { value: { isActive: reason !== 'expired' }, configurable: true })
    const createObjectURL = vi.fn().mockReturnValue('blob:firmware')
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL: vi.fn() })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      expect(this.download).toBe('MicroLink_V4.7.4.uf2')
      expect(this.href).toBe('blob:firmware')
    })
    const blob = new Blob([new Uint8Array([0, 255, 128, 64])])
    await expect(saveBlobFile('MicroLink_V4.7.4.uf2', blob)).resolves.toBe(true)
    expect(createObjectURL).toHaveBeenCalledWith(blob)
    expect(click).toHaveBeenCalledOnce()
    expect(picker).toHaveBeenCalledTimes(reason === 'expired' ? 0 : 1)
  })

  it('does not download again when the user cancels the picker', async () => {
    Object.defineProperty(window, 'showSaveFilePicker', {
      value: vi.fn().mockRejectedValue(new DOMException('Cancelled', 'AbortError')), configurable: true,
    })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click')
    await expect(saveBlobFile('firmware.uf2', new Blob())).resolves.toBe(false)
    expect(click).not.toHaveBeenCalled()
  })

  it.each(['SecurityError', 'NotAllowedError'])('reports %s writing the chosen file without a second download', async name => {
    const failure = new DOMException('Write denied', name)
    Object.defineProperty(window, 'showSaveFilePicker', {
      value: vi.fn().mockResolvedValue({ createWritable: vi.fn().mockRejectedValue(failure) }), configurable: true,
    })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click')
    await expect(saveBlobFile('firmware.uf2', new Blob())).rejects.toBe(failure)
    expect(click).not.toHaveBeenCalled()
  })
  it('saves PNG bytes with the native PNG filter', async () => {
    const save = vi.fn().mockResolvedValue('D:/captures/chart.png')
    const invoke = vi.fn().mockResolvedValue(undefined)
    vi.doMock('@tauri-apps/api/core', () => ({ isTauri: () => true, invoke }))
    vi.doMock('@tauri-apps/plugin-dialog', () => ({ save }))
    const { saveImageFile } = await import('./downloadTextFile')
    await expect(saveImageFile('chart.png', new Blob([new Uint8Array([137,80,78,71])], { type: 'image/png' }))).resolves.toBe(true)
    expect(save).toHaveBeenCalledWith({ defaultPath: 'chart.png', filters: [{ name: 'MKLink Data', extensions: ['png'] }] })
    expect(invoke).toHaveBeenCalledWith('write_file', { path: 'D:/captures/chart.png', contents: [137,80,78,71] })
  })
})
