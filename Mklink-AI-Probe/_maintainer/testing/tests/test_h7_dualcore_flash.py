from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile
import pytest

from mklink.cmsis_dap.h7_dualcore import install_pack_compatibility, bind_cm7, halt_other_cores, prepare_flash
from mklink.cmsis_dap.pyocd_runtime import import_pyocd_attr
from mklink.cmsis_dap.algorithm_catalog import _pack_algorithms
from mklink.cmsis_dap.models import TargetRecord


@pytest.mark.parametrize('part', ['STM32H745IIKx','STM32H747XIHx','STM32H755ZITx','STM32H757XIHx'])
@pytest.mark.parametrize('reverse', [False, True])
def test_processor_algorithms_selected_before_range_merge(tmp_path, part, reverse, monkeypatch):
    algos = [f'<algorithm Pname="{core}" name="same.FLM" start="0x08000000" size="0x200000" RAMstart="{ram}" RAMsize="0x8000" default="1"/>' for core, ram in [('CM7','0x20000000'),('CM4','0x10000000')]]
    if reverse: algos.reverse()
    pdsc = f'''<package><vendor>Keil</vendor><name>STM32H7xx_DFP</name><releases><release version="4.1.3"/></releases><devices><family Dfamily="STM32H7" Dvendor="STMicroelectronics:13"><processor Pname="CM7" Dcore="Cortex-M7"/><processor Pname="CM4" Dcore="Cortex-M4"/><device Dname="{part}">{''.join(algos)}</device></family></devices></package>'''
    path=tmp_path/'test.pack'
    with ZipFile(path,'w') as z:z.writestr('test.pdsc',pdsc)
    install_pack_compatibility()
    C=import_pyocd_attr('pyocd.target.pack.cmsis_pack','CmsisPack')
    pack=C(str(path));d=pack.devices[0]
    assert len(d._info.algos)==1
    assert d._info.algos[0].attrib['Pname']=='CM7'
    assert d._info.algos[0].attrib['RAMstart']=='0x20000000'
    pack._pack_file.close()
    record=TargetRecord(part_number=part,vendor='Keil',pack_id='Keil.STM32H7xx_DFP',pack_version='4.1.3',pack_path=str(path),installed=True,source='installed')
    records=_pack_algorithms(record,part)
    assert len(records)==1 and records[0].processor=='CM7'
    assert records[0].ram_start==0x20000000
    from mklink.remote.offline_download_api import _pack_device_algorithms
    # This XML-only fixture tests explicit RAM metadata; real FLM memory maps
    # are covered by the unchanged-archive DFP matrix.
    monkeypatch.setattr('mklink.remote.offline_download_api._default_ram_start', lambda device: 0)
    offline = _pack_device_algorithms(path, part)
    assert len(offline) == 1 and offline[0][2] == 0x20000000


class AP:
    def __init__(self, number):
        self.address = SimpleNamespace(apsel=number)
        self.memory = {}
        self.writes = []
    def read32(self, address): return self.memory.get(address, 0)
    def write32(self, address, value):
        self.writes.append((address, value))
        self.memory[address] = value


class Core:
    def __init__(self,name,number,ap):
        self.node_name=name;self.core_number=number;self.ap=AP(ap);self.halted=False
        self.vector_catch = 0
    def get_vector_catch(self): return self.vector_catch
    def set_vector_catch(self, value): self.vector_catch = value
    def halt(self):self.halted=True
    def resume(self):self.halted=False
    def get_state(self):
        T=import_pyocd_attr('pyocd.core.target','Target')
        return T.State.HALTED if self.halted else T.State.RUNNING

class Target:
    def __init__(self):
        self.cores={9:Core('CM4',9,3),4:Core('CM7',4,0)};self.number=9
        self.aps = {2: AP(2), 0: self.cores[4].ap, 3: self.cores[9].ap}
        self.resets = []
    def reset_and_halt(self, kind):
        self.resets.append(kind)
        self.selected_core.halted = True
    @property
    def selected_core(self):return self.cores[self.number]
    @selected_core.setter
    def selected_core(self,value):self.number=value


def test_bind_by_processor_and_ap_not_enumeration():
    t=Target();bind_cm7(t)
    assert t.selected_core.node_name=='CM7'
    assert not any(c.halted for c in t.cores.values()) # attach does not halt cores
    halt_other_cores(t)
    assert t.cores[9].halted and not t.cores[4].halted


def test_missing_cm7_fails_instead_of_running_on_cm4():
    t=Target();del t.cores[4]
    with pytest.raises(RuntimeError,match='CM7 on AP0'):bind_cm7(t)


def test_secondary_halt_failure_blocks_flash():
    t=Target();t.cores[9].halt=lambda:None
    with pytest.raises(RuntimeError,match='not halt'):halt_other_cores(t)


@pytest.mark.parametrize('part', ['STM32H745IIKx', 'STM32H747XIHx', 'STM32H755ZITx', 'STM32H757XIHx'])
def test_backend_binds_cm7_before_destructive_preparation(tmp_path, part):
    from mklink.cmsis_dap.backend import PyOcdBackend

    target = Target()
    events = []
    target.memory_map = []
    for core in target.cores.values():
        core.core_registers = SimpleNamespace(by_name={'xpsr': object()})
    def reset(kind):
        events.append(('reset', target.selected_core.node_name))
        target.selected_core.halted = True
    target.reset_and_halt = reset
    target.read_core_register = lambda name: 0
    session = SimpleNamespace(target=target, delegate=None, options={}, open=lambda: None, close=lambda: None)
    observed = {}

    def factory(probe, options):
        observed.update(options)
        return session

    pack = tmp_path / 'test.pack'
    pack.write_bytes(b'factory stub does not open this archive')
    backend = PyOcdBackend(session_factory=factory)
    backend.connect(object(), part, 1_000_000, pack=str(pack))
    assert observed['primary_core'] == 0
    assert target.selected_core.node_name == 'CM7'
    assert not events and not any(core.halted for core in target.cores.values())
    backend._prepare_algorithm_execution(target)
    backend._prepare_algorithm_execution(target)
    assert events == [('reset', 'CM7')]
    assert target.cores[9].halted
    assert session.options['resume_on_disconnect'] is False
    backend.disconnect()


def test_backend_rejects_missing_pack_before_opening_probe():
    from mklink.cmsis_dap.backend import PyOcdBackend
    from mklink.cmsis_dap.errors import FlashError

    opened = []
    backend = PyOcdBackend(session_factory=lambda *args: opened.append(args))
    with pytest.raises(FlashError, match='CMSIS-Pack CM7'):
        backend.connect(object(), 'STM32H745IIKx', 1_000_000)
    assert not opened


def prepared_backend():
    from mklink.cmsis_dap.backend import PyOcdBackend
    T = import_pyocd_attr('pyocd.core.target', 'Target')
    target = Target()
    bind_cm7(target)
    target.cores[9].halted = True
    target.reset = lambda *args: None
    target.get_state = lambda: T.State.RUNNING
    session = SimpleNamespace(target=target, delegate=None,
                              options={'resume_on_disconnect': False}, close=lambda: None)
    backend = PyOcdBackend()
    backend._session = session
    backend._connection_arguments = {'target': 'STM32H745IIKx'}
    backend._algorithm_reset_required = True
    backend._algorithm_reset_done = True
    return backend, session, target


@pytest.mark.parametrize('mode', ['default', 'software', 'system', 'hardware'])
def test_reset_runs_both_cores_only_after_system_reset(mode):
    T = import_pyocd_attr('pyocd.core.target', 'Target')
    backend, session, target = prepared_backend()
    events = []
    target.reset = lambda kind: events.append(kind)
    def resume():
        assert events == [T.ResetType.HARDWARE if mode == 'hardware' else T.ResetType.SYSTEM]
        target.cores[9].halted = False
    target.cores[9].resume = resume
    backend.reset_run(mode)
    assert not target.cores[9].halted
    assert session.options['resume_on_disconnect'] is True


@pytest.mark.parametrize('failure', ['reset', 'cm7', 'cm4', 'core_only'])
def test_failed_reset_does_not_enable_implicit_resume(failure):
    from mklink.cmsis_dap.errors import FlashError
    T = import_pyocd_attr('pyocd.core.target', 'Target')
    backend, session, target = prepared_backend()
    if failure == 'reset':
        def fail(*args): raise RuntimeError('reset link lost')
        target.reset = fail
    elif failure == 'cm7':
        target.get_state = lambda: T.State.HALTED
    elif failure == 'cm4':
        target.cores[9].resume = lambda: None
    with pytest.raises(FlashError):
        backend.reset_run('core' if failure == 'core_only' else 'default')
    assert session.options['resume_on_disconnect'] is False


def test_missing_secondary_blocks_before_reset_or_flash():
    backend, session, target = prepared_backend()
    backend._algorithm_reset_done = False
    del target.cores[9]
    target.reset_and_halt = lambda: pytest.fail('must validate both cores first')
    with pytest.raises(RuntimeError, match='CM4 on AP3'):
        backend._prepare_algorithm_execution(target)


def test_core_only_preparation_refused_before_reset():
    from mklink.cmsis_dap.errors import FlashError
    backend, session, target = prepared_backend()
    backend._algorithm_reset_done = False
    backend._reset_mode = 'core'
    target.reset_and_halt = lambda: pytest.fail('must reject before reset')
    with pytest.raises(FlashError, match='core-only'):
        backend._prepare_algorithm_execution(target)


@pytest.mark.parametrize('hardware', [False, True])
@pytest.mark.parametrize('debug_ap', [True, False])
def test_d2_debug_and_cm4_reset_catch_precede_whole_reset(hardware, debug_ap):
    T = import_pyocd_attr('pyocd.core.target', 'Target')
    t = Target()
    if not debug_ap: del t.aps[2]
    ap, address = (t.aps[2], 0xE00E1004) if debug_ap else (t.aps[0], 0x5C001004)
    ap.memory[address] = 0x40000  # Preserve vendor clock configuration.
    cm4 = t.cores[9]
    cm4.vector_catch = T.VectorCatch.HARD_FAULT
    def reset(kind):
        assert ap.read32(address) == 0x0064003F
        assert cm4.halted
        assert cm4.vector_catch == T.VectorCatch.HARD_FAULT | T.VectorCatch.CORE_RESET
        t.resets.append(kind)
        t.selected_core.halted = True
        # Model CM4 restarting at reset: it stops only with both prerequisites.
        cm4.halted = bool(ap.read32(address) & 0x38 and cm4.vector_catch & T.VectorCatch.CORE_RESET)
    t.reset_and_halt = reset
    prepare_flash(t, hardware_reset=hardware)
    assert t.resets == [T.ResetType.HARDWARE if hardware else T.ResetType.SYSTEM]
    assert all(c.halted for c in t.cores.values())
    assert cm4.vector_catch == T.VectorCatch.HARD_FAULT
    assert ap.writes == [(address, 0x0064003F)]
    assert not t.aps[3].writes
    if debug_ap: assert not t.aps[0].writes


def test_debug_write_failure_blocks_before_reset_and_reports_registers(caplog):
    t = Target()
    t.aps[2].write32 = lambda *args: None
    with pytest.raises(RuntimeError, match='debug-domain-setup.*did not latch.*Flash was not erased') as error:
        prepare_flash(t)
    assert not t.resets
    assert '"DBGMCU_CR": "0x00000000"' in str(error.value)
    assert '"at"' in caplog.text and '"elapsed_ms"' in caplog.text


@pytest.mark.parametrize('state_name', ['RUNNING', 'SLEEPING', 'RESET', 'LOCKUP'])
@pytest.mark.parametrize('number', [4, 9])
def test_nonhalted_core_blocks_with_core_and_register_diagnostics(monkeypatch, state_name, number):
    import mklink.cmsis_dap.h7_dualcore as module
    T = import_pyocd_attr('pyocd.core.target', 'Target')
    t = Target()
    t.cores[number].get_state = lambda: getattr(T.State, state_name)
    t.cores[number].ap.memory[0xE000EDF0] = 0x00080001
    ticks = iter(range(100))
    monkeypatch.setattr(module.time, 'monotonic', lambda: next(ticks))
    monkeypatch.setattr(module.time, 'sleep', lambda _: pytest.fail('deadline already elapsed'))
    with pytest.raises(RuntimeError, match=f'CM[47]-halt:.*state={state_name}.*Flash was not erased') as error:
        prepare_flash(t)
    assert '"DHCSR": "0x00080001"' in str(error.value)
    assert '"ap": 3' in str(error.value) and '"ap": 0' in str(error.value)
    assert t.cores[9].vector_catch == 0


def test_read_fault_preserves_original_failure_and_restores_vector_catch(caplog):
    t = Target()
    def fail(kind):
        def unreadable(address): raise RuntimeError('AP transfer fault')
        t.aps[3].read32 = unreadable
        raise RuntimeError('NRST transfer failed')
    t.reset_and_halt = fail
    with pytest.raises(RuntimeError, match='system-reset: NRST transfer failed.*Flash was not erased') as error:
        prepare_flash(t)
    assert 'unavailable (RuntimeError: AP transfer fault)' in str(error.value)
    assert t.cores[9].vector_catch == 0
    assert 'H7 flash preparation failed' in caplog.text


def test_vector_catch_restore_failure_blocks_flash():
    t = Target()
    original = t.cores[9].set_vector_catch
    def set_catch(value):
        if value == 0: raise RuntimeError('debug link lost on restore')
        original(value)
    t.cores[9].set_vector_catch = set_catch
    with pytest.raises(RuntimeError, match='reset-catch restore failed; Flash was not erased'):
        prepare_flash(t)


def test_failed_halt_evidence_is_in_customer_diagnostic_zip(tmp_path, monkeypatch):
    import io
    import json
    from mklink.connection_diagnostics import connection_log, export_bundle
    monkeypatch.setattr('mklink.runtime.runtime_dir', lambda: tmp_path)
    t = Target()
    t.aps[2].write32 = lambda *args: None
    with connection_log(tmp_path):
        with pytest.raises(RuntimeError, match='did not latch'):
            prepare_flash(t)
    with ZipFile(io.BytesIO(export_bundle())) as archive:
        rows = [json.loads(line) for name in archive.namelist() if name.endswith('.jsonl')
                for line in archive.read(name).decode('utf-8').splitlines()]
    row = next(row for row in rows if row['event'] == 'flash.h7_preparation_failed')
    evidence = row['evidence']
    assert evidence['stage'] == 'debug-domain-setup'
    assert 'did not latch' in evidence['error']
    assert evidence['DBGMCU_CR'] == '0x00000000'
    assert evidence['cores'][0]['core'] == 'CM4' and evidence['cores'][0]['ap'] == 3
    assert 'DHCSR' in evidence['cores'][0]
    assert evidence['at'] and row['time']
