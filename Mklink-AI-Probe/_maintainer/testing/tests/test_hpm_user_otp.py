from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from mklink import hpm_otp as otp


def device(value=1):
    values = {otp.FUSE + 64 * 4: otp.CHIP_ID, otp.FUSE + 69 * 4: value}
    return SimpleNamespace(idcode=0x1000563D,
        read_memory=Mock(side_effect=lambda address, count: values.get(address, 0).to_bytes(4, 'little')),
        _bridge=SimpleNamespace(send_command=Mock(return_value='OTP_USER v=1 word=69\n0\n')))


@pytest.mark.parametrize('word,old,new', [(68,1,3),(80,1,3),(69,0,3),(69,1,0),(69,1,-1),(69,1,2**32)])
def test_invalid_plan_never_sends_program(word, old, new):
    d = device()
    with pytest.raises(ValueError): otp.plan(d,word,old,new)
    d._bridge.send_command.assert_not_called()


def test_confirmation_and_identity_required():
    d=device()
    with pytest.raises(ValueError): otp.program(d,69,1,3)
    d.idcode=0
    with pytest.raises(ValueError): otp.program(d,69,1,3,True)
    d._bridge.send_command.assert_not_called()


def test_plan_only_dry_runs_and_retains_expected_value():
    d=device()
    plan=otp.plan(d,69,1,'0x3')
    assert plan['delta']==2
    assert 'hpm.otp_user(69, 1, 3, 1)' in plan['script']
    d._bridge.send_command.assert_called_once_with('hpm.otp_user(69,1,3,0)',timeout=5)


def test_program_transport_failure_is_never_retried():
    d=device()
    d._bridge.send_command.side_effect=['OTP_USER v=1 word=69\n0\n',TimeoutError('lost response')]
    with pytest.raises(TimeoutError): otp.program(d,69,1,3,True)
    assert d._bridge.send_command.call_count==2


def test_readback_failure_is_not_success():
    with pytest.raises(RuntimeError,match='readback mismatch'): otp.program(device(),69,1,3,True)


def test_unsupported_firmware_fails_before_programming():
    d=device()
    d._bridge.send_command.return_value='NameError\n0\n'
    with pytest.raises(RuntimeError): otp.program(d,69,1,3,True)
    assert d._bridge.send_command.call_count==1


def test_locked_word_rejected():
    d=device()
    original=d.read_memory.side_effect
    d.read_memory.side_effect=lambda address,count: (1 << 17).to_bytes(4,'little') if address==otp.FUSE else original(address,count)
    with pytest.raises(ValueError,match='locked'): otp.plan(d,69,1,3)


def test_api_routes_confirmation_and_validation(tmp_path):
    from fastapi.testclient import TestClient
    from mklink.remote.api import create_app
    app = create_app(project_root=str(tmp_path))
    d=device(); d.connected=True
    app.state.mklink_state['device']=d
    with TestClient(app) as client:
        base='/api/device/configuration/hpm-user-otp/'
        args=dict(part_number='HPM5301',word=69,expected=1,desired=3)
        assert client.post(base+'read',json=args).status_code==200
        assert client.post(base+'plan',json=args).json()['delta']==2
        d._bridge.send_command.reset_mock()
        for extra in ({}, {'confirm_irreversible':'true'}, {'confirm_irreversible':True,'word':68}):
            assert client.post(base+'program',json={**args,**extra}).status_code==422
        d._bridge.send_command.assert_not_called()
        app.state.mklink_state['device']=None

