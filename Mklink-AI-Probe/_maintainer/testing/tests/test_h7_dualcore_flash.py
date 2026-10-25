from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile
import pytest

from mklink.cmsis_dap.h7_dualcore import install_pack_compatibility, bind_cm7, halt_other_cores
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


class Core:
    def __init__(self,name,number,ap):
        self.node_name=name;self.core_number=number;self.ap=SimpleNamespace(address=SimpleNamespace(apsel=ap));self.halted=False
    def halt(self):self.halted=True
    def resume(self):self.halted=False
    def get_state(self):
        T=import_pyocd_attr('pyocd.core.target','Target')
        return T.State.HALTED if self.halted else T.State.RUNNING

class Target:
    def __init__(self):
        self.cores={9:Core('CM4',9,3),4:Core('CM7',4,0)};self.number=9
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
    target.reset_and_halt = lambda: events.append(('reset', target.selected_core.node_name))
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
