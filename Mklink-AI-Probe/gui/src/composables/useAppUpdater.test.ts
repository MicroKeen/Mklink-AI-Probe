import { beforeEach, describe, expect, it, vi } from 'vitest'

const updaterMocks = vi.hoisted(() => ({
  check: vi.fn(),
  isTauri: vi.fn(),
  relaunch: vi.fn(),
  reserve: vi.fn(),
  release: vi.fn(),
}))

vi.mock('@tauri-apps/api/core', () => ({ isTauri: updaterMocks.isTauri }))
vi.mock('@tauri-apps/plugin-updater', () => ({ check: updaterMocks.check }))
vi.mock('@tauri-apps/plugin-process', () => ({ relaunch: updaterMocks.relaunch }))
vi.mock('../lib/updateCoordination', () => ({ reserveHostUpdate: updaterMocks.reserve }))

import { useAppUpdater } from './useAppUpdater'

function update(version = '0.2.0') {
  return {
    version,
    download: vi.fn(async (onEvent?: (event: unknown) => void) => {
      onEvent?.({ event: 'Started', data: { contentLength: 100 } })
      onEvent?.({ event: 'Progress', data: { chunkLength: 40 } })
      onEvent?.({ event: 'Progress', data: { chunkLength: 60 } })
      onEvent?.({ event: 'Finished' })
    }),
    install: vi.fn(async () => undefined),
  }
}

describe('useAppUpdater', () => {
  beforeEach(() => {
    updaterMocks.check.mockReset()
    updaterMocks.isTauri.mockReset()
    updaterMocks.relaunch.mockReset()
    updaterMocks.reserve.mockReset().mockResolvedValue(updaterMocks.release)
    updaterMocks.release.mockReset().mockResolvedValue(undefined)
  })

  it('does nothing outside the Tauri desktop runtime', async () => {
    updaterMocks.isTauri.mockReturnValue(false)
    const updater = useAppUpdater()

    await updater.checkForUpdates()

    expect(updaterMocks.check).not.toHaveBeenCalled()
    expect(updater.state.value).toBe('idle')
  })

  it('checks on request and downloads an available update in the background', async () => {
    updaterMocks.isTauri.mockReturnValue(true)
    const available = update()
    updaterMocks.check.mockResolvedValue(available)
    const updater = useAppUpdater()

    await updater.checkForUpdates()

    expect(updaterMocks.check).toHaveBeenCalledOnce()
    expect(available.download).toHaveBeenCalledOnce()
    expect(updater.state.value).toBe('ready')
    expect(updater.version.value).toBe('0.2.0')
    expect(updater.progress.value).toBe(1)
  })

  it('can retry after a network failure', async () => {
    updaterMocks.isTauri.mockReturnValue(true)
    updaterMocks.check.mockRejectedValueOnce(new Error('network unavailable'))
    const available = update()
    updaterMocks.check.mockResolvedValueOnce(available)
    const updater = useAppUpdater()

    await updater.checkForUpdates()
    expect(updater.state.value).toBe('error')
    expect(updater.error.value).toBe('network unavailable')

    await updater.retry()
    expect(updater.state.value).toBe('ready')
    expect(updater.error.value).toBe('')
  })

  it('installs the downloaded update and relaunches after explicit confirmation', async () => {
    updaterMocks.isTauri.mockReturnValue(true)
    const available = update()
    updaterMocks.check.mockResolvedValue(available)
    const updater = useAppUpdater()
    await updater.checkForUpdates()

    await updater.installAndRelaunch()

    expect(available.install).toHaveBeenCalledOnce()
    expect(updaterMocks.relaunch).toHaveBeenCalledOnce()
    expect(updater.state.value).toBe('installing')
  })

  it('explains a missing platform and allows a later supported update', async () => {
    updaterMocks.isTauri.mockReturnValue(true)
    updaterMocks.check.mockRejectedValueOnce('None of the fallback platforms `["darwin-aarch64-app", "darwin-aarch64"]` were found in the response `platforms` object')
    const updater = useAppUpdater()
    await updater.checkForUpdates()
    expect(updater.state.value).toBe('unavailable')
    expect(updater.error.value).toBe('')
    await updater.installAndRelaunch()
    expect(updaterMocks.relaunch).not.toHaveBeenCalled()
    updaterMocks.check.mockResolvedValueOnce(update())
    await updater.retry()
    expect(updater.state.value).toBe('ready')
  })

  it('requires restart after install succeeded, without downloading or installing twice', async () => {
    updaterMocks.isTauri.mockReturnValue(true)
    const available = update()
    updaterMocks.check.mockResolvedValue(available)
    updaterMocks.relaunch.mockRejectedValueOnce(new Error('restart denied'))
    const updater = useAppUpdater()
    await updater.checkForUpdates()
    await updater.installAndRelaunch()
    expect(updater.state.value).toBe('restart-required')
    await updater.retry()
    expect(updaterMocks.check).toHaveBeenCalledOnce()
    await updater.installAndRelaunch()
    expect(available.install).toHaveBeenCalledOnce()
    expect(updaterMocks.relaunch).toHaveBeenCalledTimes(2)
  })

  it('keeps the downloaded update when the backend is busy and retries without redownloading', async () => {
    updaterMocks.isTauri.mockReturnValue(true)
    const available = update()
    updaterMocks.check.mockResolvedValue(available)
    updaterMocks.reserve.mockRejectedValueOnce(new Error('firmware upgrade is busy'))
    const updater = useAppUpdater()
    await updater.checkForUpdates()
    await updater.installAndRelaunch()
    expect(updater.state.value).toBe('ready')
    expect(updater.blocked.value).toContain('busy')
    expect(available.install).not.toHaveBeenCalled()
    expect(updaterMocks.relaunch).not.toHaveBeenCalled()
    await updater.installAndRelaunch()
    expect(available.install).toHaveBeenCalledOnce()
    expect(available.download).toHaveBeenCalledOnce()
    expect(updaterMocks.release).toHaveBeenCalledOnce()
  })

  it('never installs while local firmware work is active and releases admission on install failure', async () => {
    updaterMocks.isTauri.mockReturnValue(true)
    const available = update()
    available.install.mockRejectedValueOnce(new Error('installer failed'))
    updaterMocks.check.mockResolvedValue(available)
    let idle = false
    const updater = useAppUpdater(() => idle)
    await updater.checkForUpdates()
    await updater.installAndRelaunch()
    expect(updaterMocks.reserve).not.toHaveBeenCalled()
    idle = true
    await updater.installAndRelaunch()
    expect(updater.state.value).toBe('error')
    expect(updaterMocks.release).toHaveBeenCalledOnce()
    expect(updaterMocks.relaunch).not.toHaveBeenCalled()
  })

  it('keeps signature and download failures as errors', async () => {
    updaterMocks.isTauri.mockReturnValue(true)
    const available = update()
    available.download.mockRejectedValueOnce(new Error('signature verification failed'))
    updaterMocks.check.mockResolvedValueOnce(available)
    const updater = useAppUpdater()
    await updater.checkForUpdates()
    expect(updater.state.value).toBe('error')
    expect(updater.error.value).toContain('signature')
  })
})
