"""Short-lived, single-use approvals for a fixed UART OTP change."""
from dataclasses import dataclass
import secrets
import time


@dataclass(frozen=True)
class OtpBinding:
    probe_id: str
    port: str
    generation: int
    part: str


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
        fixed = {key: change[key] for key in ('word', 'expected', 'desired', 'delta')}
        self.entries[token] = (self.clock() + self.TTL, binding, fixed)
        return dict(change, plan_id=token, expires_in=self.TTL)

    def consume(self, token: str, binding: OtpBinding) -> dict:
        record = self.entries.pop(token, None)
        if record is None:
            raise ValueError('OTP plan expired or already used; read again and prepare a new preview')
        expires, expected_binding, fixed = record
        if self.clock() >= expires or binding != expected_binding:
            raise ValueError('OTP plan expired or target selection changed; read again')
        return fixed.copy()
