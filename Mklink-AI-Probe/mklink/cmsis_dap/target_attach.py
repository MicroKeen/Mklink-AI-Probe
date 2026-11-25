"""Apply the compiled target profile during pyOCD's pre-discovery sequence."""
from __future__ import annotations

from mklink.mux import encode_attach_profile
from mklink.profiles import MuxAttachProfile
from .errors import FlashError, FlashErrorCode
from .pyocd_runtime import import_pyocd_module


class ProfileAttachDelegate:
    def __init__(self, profile: MuxAttachProfile, next_delegate=None, *, observe_before_halt=False):
        encode_attach_profile(profile)  # Validate the entire table before opening the target.
        self.profile = profile
        self._next_delegate = next_delegate
        self._attempted = False
        self.bound = False
        self.observe_before_halt = observe_before_halt
        self.was_running = False

    def __getattr__(self, name):
        return getattr(self._next_delegate, name)

    def _error(self, reason, description, *, step=None, actual=None):
        details = dict(profile=self.profile.name, mem_ap=self.profile.mem_ap,
                       step=step, reason=reason, actual=actual)
        message = f'{self.profile.name} CMSIS-DAP attach: {description}'
        if step is not None:
            message += f' (step={step})'
        if actual is not None:
            message += f', actual=0x{actual:08X}'
        return FlashError(FlashErrorCode.CONNECT_FAIL, message, details)

    def will_init_target(self, target, init_sequence):
        callback = getattr(self._next_delegate, 'will_init_target', None)
        if callable(callback):
            callback(target, init_sequence)
        # Top-level InitTarget failures propagate out of Session.open(), before
        # component discovery (where pyOCD may log and skip a failing component).
        init_sequence.insert_after('dp_init', ('mklink_profile_attach', lambda: self._bind(target.dp)))
        if self.observe_before_halt:
            init_sequence.insert_before('halt_on_connect', ('mklink_observe_run_state',
                                                            lambda: self._observe_running(target)))

    def _observe_running(self, target):
        core = target.selected_core
        if not self.bound or getattr(getattr(getattr(core, 'ap', None), 'address', None), 'apsel', None) != self.profile.mem_ap:
            return
        state = core.get_state()
        self.was_running = state.name in ('RUNNING', 'SLEEPING')

    def unlock_device(self, target=None):
        # CoreSightTarget prefers this delegate over Pack DebugDeviceUnlock.
        # The profile has already checked application debug permission and set
        # the allowed AP bits. A second enable sequence could overwrite them.
        if not self.bound:
            raise self._error('unbound', 'device unlock hook reached before profile verification')

    def _bind(self, dp):
        if self._attempted:
            raise self._error('replay', 'profile execution already attempted; reconnect explicitly')
        self._attempted = True
        dap = import_pyocd_module('pyocd.coresight.dap')
        regs = import_pyocd_module('pyocd.coresight.ap')
        if dp.adi_version != dap.ADIVersion.ADIv5:
            raise self._error('adi_version', 'an ADIv5 debug port is required')
        try:
            control = dp.read_dp(dap.DP_CTRL_STAT)
        except Exception as exc:
            raise self._error('dp_read', f'DP CTRL/STAT read failed: {exc}') from exc
        power_ack = dap.CDBGPWRUPACK | dap.CSYSPWRUPACK
        if control == 0xffffffff or control & power_ack != power_ack:
            raise self._error('dp_power', 'DP power-up is unconfirmed', actual=control)
        for index, step in enumerate(self.profile.steps):
            self._run_step(dp, regs, index, step)
        dp.valid_aps = [self.profile.mem_ap]
        self.bound = True

    def _run_step(self, dp, regs, index, step):
        ap_base = step.ap << 24
        actual = None
        operation = 'memory_read' if step.kind == 3 else 'ap_read'
        try:
            if step.kind == 3:
                csw = dp.read_ap(ap_base | regs.MEM_AP_CSW)
                if csw == 0xffffffff:
                    raise self._error('ap_read', 'invalid MEM-AP CSW', step=index, actual=csw)
                # Select a privileged, word-sized transfer and disable address
                # increment while retaining the other CSW attributes.
                dp.write_ap(ap_base | regs.MEM_AP_CSW, (csw & ~0x37) | 0x03000002)
                dp.write_ap(ap_base | regs.MEM_AP_TAR, step.address)
                actual = dp.read_ap(ap_base | regs.MEM_AP_DRW)
            else:
                register = ap_base | step.address
                actual = dp.read_ap(register)
            if actual & step.mask == step.value:
                return
            if step.kind != 2:
                raise self._error('memory_check' if step.kind == 3 else 'ap_check',
                                  f'AP{step.ap} address 0x{step.address:08X} failed its profile check',
                                  step=index, actual=actual)
            operation = 'ap_write'
            dp.write_ap(register, (actual & ~step.mask) | step.value)
            dp.flush()
            operation = 'ap_readback'
            actual = None
            actual = dp.read_ap(register)
            if actual & step.mask != step.value:
                raise self._error(operation, 'AP write verification failed', step=index, actual=actual)
        except FlashError:
            raise
        except Exception as exc:
            message = f'{operation} failed: {exc}'
            if operation in ('ap_write', 'ap_readback'):
                message += '; AP write outcome unconfirmed, do not replay'
            raise self._error(operation, message, step=index, actual=actual) from exc
