import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useMklinkApi } from './useMklinkApi'
import { sharedRuntime } from './useBackendHealth'

describe('RTT API contracts', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    sharedRuntime.value = false
    fetchMock.mockReset()
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({}),
    })
    vi.stubGlobal('fetch', fetchMock)
  })

  it('uses separate probe and UART inventories', async () => {
    sharedRuntime.value = true
    await useMklinkApi().listPorts()
    await useMklinkApi().listUartPorts()
    expect(fetchMock.mock.calls.map(call => call[0])).toEqual(['/api/ports', '/api/ports/uart'])
  })

  it('retains structured disconnect conflicts so the UI can show the owners', async () => {
    const detail = { reason: 'shared_clients_attached', message: 'Shared device', clients: [{ name: 'IDE', kind: 'mcp' }] }
    fetchMock.mockResolvedValueOnce({ ok: false, status: 409, json: async () => ({ detail }) })
    await expect(useMklinkApi().disconnectDevice()).rejects.toMatchObject({ message: 'Shared device', status: 409, detail })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('connects the current probe without navigating or restarting the page', async () => {
    sharedRuntime.value = true
    const navigate = vi.spyOn(window.location, 'replace').mockImplementation(() => {})
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({ same_runtime: true }) })
    await useMklinkApi().connectDevice({ port: 'COM9' })
    expect(fetchMock.mock.calls.map(call => call[0])).toEqual([
      '/api/runtime/select', '/api/device/connect', '/api/device/status',
    ])
    expect(navigate).not.toHaveBeenCalled()
    navigate.mockRestore()
  })

  it('switches in place and refreshes target generation without navigation or duplicate connect', async () => {
    sharedRuntime.value = true
    const navigate = vi.spyOn(window.location, 'replace').mockImplementation(() => {})
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({
      same_runtime: true, switched: true, connection: { port: 'COM10' },
    }) })
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({ port: 'COM10', device_generation: 2 }) })
    await useMklinkApi().connectDevice({ port: 'COM10' })
    expect(fetchMock.mock.calls.map(call => call[0])).toEqual(['/api/runtime/select', '/api/device/status'])
    expect(useMklinkApi().deviceStatus.value.device_generation).toBe(2)
    expect(navigate).not.toHaveBeenCalled()
    navigate.mockRestore()
  })

  it('clears the previous device after the replacement connection fails', async () => {
    sharedRuntime.value = true
    fetchMock.mockResolvedValueOnce({ ok: false, status: 500, json: async () => ({ detail: 'USB failed' }) })
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({ connected: false, device_generation: 3 }) })
    await expect(useMklinkApi().connectDevice({ port: 'COM10' })).rejects.toThrow('USB failed')
    expect(useMklinkApi().deviceStatus.value).toMatchObject({ connected: false, device_generation: 3 })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('lets Auto search connect a replacement without submitting a stale port or connecting twice', async () => {
    sharedRuntime.value = true
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({
      same_runtime: true, switched: true, connection: { port: 'COM10' },
    }) })
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({ connected: true, port: 'COM10' }) })
    const result = await useMklinkApi().connectDevice({ restore_last: true })
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ connect: { restore_last: true } })
    expect(fetchMock.mock.calls.map(call => call[0])).toEqual(['/api/runtime/select', '/api/device/status'])
    expect(result.port).toBe('COM10')
    expect(useMklinkApi().deviceStatus.value.connected).toBe(true)
  })

  it('queries an accepted shared reset job without issuing a second reset', async () => {
    sharedRuntime.value = true
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({ job_id: 'job-one', state: 'running' }) })
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({ job_id: 'job-one', state: 'succeeded', result: { status: 'ok' } }) })
    expect(await useMklinkApi().resetDevice()).toEqual({ status: 'ok' })
    expect(fetchMock.mock.calls[0][0]).toBe('/api/runtime/jobs/')
    expect(fetchMock.mock.calls[1][0]).toBe('/api/runtime/jobs/job-one')
    expect(fetchMock.mock.calls.filter(([, options]) => options.method === 'POST')).toHaveLength(1)
    sharedRuntime.value = false
  })

  it('does not retry an exclusive job with an unknown result', async () => {
    sharedRuntime.value = true
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({ job_id: 'job-unknown', state: 'unknown', error: 'transport lost' }) })
    await expect(useMklinkApi().eraseDevice()).rejects.toThrow('unknown')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    sharedRuntime.value = false
  })

  it('passes an optional explicit source path to RTT detection', async () => {
    const api = useMklinkApi()
    await api.findRtt('C:\\firmware\\app.elf')
    await api.findRtt()

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/rtt-find', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ source_path: 'C:\\firmware\\app.elf' }),
    }))
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/rtt-find', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({}),
    }))
  })

  it('writes RTT bytes through a compact lowercase hex payload', async () => {
    const api = useMklinkApi()
    await api.writeRtt(Uint8Array.of(0x00, 0x0a, 0xff))

    expect(fetchMock).toHaveBeenCalledWith('/api/dash/rtt/write', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ data_hex: '000aff' }),
    }))
  })

  it('keeps AXF parsing built-in by default and forwards explicit external mode', async () => {
    const api = useMklinkApi()
    await api.parseAxf('C:\\firmware\\app.axf')
    await api.parseAxf('C:\\firmware\\app.axf', 'external')

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/device/parse-axf', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ axf: 'C:\\firmware\\app.axf' }),
    }))
    expect(fetchMock).toHaveBeenNthCalledWith(3, '/api/device/parse-axf', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ axf: 'C:\\firmware\\app.axf', elf_backend: 'external' }),
    }))
  })

  it('switches the shared RTT decoder encoding', async () => {
    const api = useMklinkApi()
    await api.setRttEncoding('gb18030')

    expect(fetchMock).toHaveBeenCalledWith('/api/dash/rtt/encoding', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ encoding: 'gb18030' }),
    }))
  })

  it('forwards the guarded probe voltage request exactly', async () => {
    const api = useMklinkApi()
    await api.setPowerOn(5000, true)

    expect(fetchMock).toHaveBeenCalledWith('/api/device/power', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ voltage_mv: 5000, confirm_5v: true }),
    }))
  })

  it('sends firmware upgrade confirmation as a scalar boolean body', async () => {
    const api = useMklinkApi()
    await api.upgradeProbeFirmware(true)

    expect(fetchMock).toHaveBeenCalledWith('/api/probe/firmware-upgrade', expect.objectContaining({
      method: 'POST',
      body: 'true',
    }))
  })

  it.each(['check', 'upgrade'])('reserves the unique replacement before firmware %s without connecting a target', async action => {
    sharedRuntime.value = true
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({
      probe_id: 'old-probe', probes: [{ probe_id: 'replacement', port: 'COM10' }],
    }) })
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({ probe_id: 'replacement', device_generation: 4 }) })
    const api = useMklinkApi()
    if (action === 'check') await api.probeFirmwareCheck()
    else await api.upgradeProbeFirmware(true)
    expect(fetchMock.mock.calls.map(call => call[0])).toEqual([
      '/api/runtime/control/status', '/api/runtime/select', `/api/probe/firmware-${action}`,
    ])
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ probe: 'replacement' })
    const headers = fetchMock.mock.calls[2][1].headers as Headers
    expect(headers.get('X-MKLink-Probe')).toBe('replacement')
    expect(headers.get('X-MKLink-Device-Generation')).toBe('4')
    if (action === 'upgrade') expect(fetchMock.mock.calls[2][1].body).toBe('true')
  })

  it.each([undefined, 'COM10'])('respects the bound or explicitly selected firmware probe (%s)', async port => {
    sharedRuntime.value = true
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({
      probe_id: 'bound', probes: [{ probe_id: 'bound', port: 'COM9' }, { probe_id: 'chosen', port: 'COM10' }],
    }) })
    await useMklinkApi().probeFirmwareCheck(port)
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ probe: port ? 'chosen' : 'bound' })
  })

  it.each([
    { probes: [], port: undefined },
    { probes: [{ probe_id: 'a', port: 'COM1' }, { probe_id: 'b', port: 'COM2' }], port: undefined },
    { probes: [{ probe_id: 'a', port: 'COM1' }], port: 'COM99' },
  ])('does not guess a firmware destination when selection fails: %j', async ({ probes, port }) => {
    sharedRuntime.value = true
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({ probe_id: 'missing', probes }) })
    await expect(useMklinkApi().upgradeProbeFirmware(true, port)).rejects.toThrow()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('does not upgrade or retry when another backend owns the selected probe', async () => {
    sharedRuntime.value = true
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({
      probe_id: 'lobby', probes: [{ probe_id: 'owned', port: 'COM1' }],
    }) })
    fetchMock.mockResolvedValueOnce({ ok: false, status: 409, json: async () => ({ detail: 'Probe is owned' }) })
    await expect(useMklinkApi().upgradeProbeFirmware(true)).rejects.toThrow('Probe is owned')
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('downloads the selected probe firmware as a named binary', async () => {
    const blob = new Blob(['uf2'], { type: 'application/octet-stream' })
    fetchMock.mockResolvedValueOnce({
      ok: true,
      headers: new Headers({
        'X-MKLink-Firmware-Name': 'MicroLink_V3.3.7.uf2',
        'X-MKLink-Firmware-Version': 'V3.3.7',
        'X-MKLink-Firmware-Source': 'gitee',
        'X-MKLink-Firmware-Family': 'microlink',
      }),
      blob: async () => blob,
    })

    await expect(useMklinkApi().downloadProbeFirmware('V3')).resolves.toEqual({
      blob,
      filename: 'MicroLink_V3.3.7.uf2',
      version: 'V3.3.7',
      source: 'gitee',
      family: 'microlink',
    })
    expect(fetchMock).toHaveBeenCalledWith('/api/probe/firmware-download?model=V3&family=microlink')

    fetchMock.mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'X-MKLink-Firmware-Name': 'HPMLink_V4.7.0.uf2' }),
      blob: async () => blob,
    })
    await useMklinkApi().downloadProbeFirmware('V4', 'hpmlink')
    expect(fetchMock).toHaveBeenLastCalledWith('/api/probe/firmware-download?model=V4&family=hpmlink')
  })

  it.each([
    ['V2', 'MicroLink_V2.9.2.rbl'], ['V3', 'MicroLink_V3.6.7.uf2'],
    ['V4', 'MicroLink_V4.7.1.uf2'], ['V4', 'MicroLink_V4.8.9.uf2'],
  ] as const)('preserves the server-provided latest %s filename %s', async (model, filename) => {
    fetchMock.mockResolvedValueOnce({ ok: true,
      headers: new Headers({ 'X-MKLink-Firmware-Name': filename }), blob: async () => new Blob(['firmware']),
    })
    expect((await useMklinkApi().downloadProbeFirmware(model)).filename).toBe(filename)
  })

  it('accepts the exact Content-Disposition filename when the custom name is unavailable', async () => {
    fetchMock.mockResolvedValueOnce({ ok: true,
      headers: new Headers({ 'Content-Disposition': 'attachment; filename="MicroLink_V2.9.2.rbl"' }),
      blob: async () => new Blob(['firmware']),
    })
    expect((await useMklinkApi().downloadProbeFirmware('V2')).filename).toBe('MicroLink_V2.9.2.rbl')
  })

  it.each(['', 'MicroLink_V2.uf2', 'MicroLink_V3.6.7.uf2'])('refuses a missing or incorrect V2 filename: %s', async filename => {
    const blob = vi.fn()
    fetchMock.mockResolvedValueOnce({ ok: true,
      headers: new Headers(filename ? { 'X-MKLink-Firmware-Name': filename } : {}), blob,
    })
    await expect(useMklinkApi().downloadProbeFirmware('V2')).rejects.toThrow()
    expect(blob).not.toHaveBeenCalled()
  })

  it('refreshes connection state after rebooting the probe', async () => {
    const api = useMklinkApi()
    await api.rebootProbe()

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/device/reboot', expect.objectContaining({
      method: 'POST',
    }))
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/device/status', expect.any(Object))
  })

  it('surfaces structured backend symbol-source errors', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      statusText: 'Conflict',
      json: async () => ({
        detail: {
          code: 'symbol_source_mismatch',
          message: 'requested AXF was not activated',
        },
      }),
    })

    await expect(useMklinkApi().parseAxf('C:\\firmware\\next.axf'))
      .rejects.toThrow('requested AXF was not activated')
  })

  it('uploads a browser-selected symbol file as multipart data', async () => {
    const api = useMklinkApi()
    const file = new File(['ELF'], 'firmware.axf', { type: 'application/octet-stream' })

    await api.uploadFileSource('symbol', file)

    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/files/symbol')
    expect(options.method).toBe('POST')
    expect(options.body).toBeInstanceOf(FormData)
    expect(new Headers(options.headers).has('Content-Type')).toBe(false)
    expect((options.body as FormData).get('file')).toBe(file)
  })
})
