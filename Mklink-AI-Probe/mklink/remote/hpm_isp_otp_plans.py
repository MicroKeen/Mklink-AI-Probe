"""Short-lived, single-use approvals for a fixed UART OTP change."""
from dataclasses import dataclass
from copy import deepcopy
import secrets
import time


@dataclass(frozen=True)
class OtpBinding:
    probe_id: str
    port: str
    generation: int
    part: str
    extended: bool = False


class OtpPlans:
    TTL = 60

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.entries = {}

    def clear(self):
        self.entries.clear()

    def remember(self, binding: OtpBinding, change: dict) -> dict:
        # Only the newest reviewed change may remain executable in this runtime.
        self.clear()
        token = secrets.token_hex(24)
        keys = ('word', 'expected', 'desired', 'delta')
        fixed = ({'changes': [{key: item[key] for key in keys} for item in change['changes']]}
                 if 'changes' in change else {key: change[key] for key in keys})
        if 'target_identity' in change:
            fixed['target_identity'] = deepcopy(change['target_identity'])
        self.entries[token] = (self.clock() + self.TTL, binding, fixed)
        return dict(change, plan_id=token, expires_in=self.TTL)

    def consume(self, token: str, binding: OtpBinding) -> dict:
        record = self.entries.pop(token, None)
        if record is None:
            raise ValueError('OTP plan expired or already used; read again and prepare a new preview')
        expires, expected_binding, fixed = record
        if self.clock() >= expires or binding != expected_binding:
            raise ValueError('OTP plan expired or target selection changed; read again')
        return deepcopy(fixed)
