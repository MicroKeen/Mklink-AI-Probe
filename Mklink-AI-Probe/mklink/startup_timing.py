"""Opt-in startup milestones; no paths, device identifiers or credentials."""
import os
import sys
import time

_enabled = os.environ.get("MKLINK_STARTUP_TIMING") == "1"
_started = time.perf_counter()


def mark(stage):
    if not _enabled:
        return
    try:
        print(f"[startup] {os.getpid()} {stage} {time.perf_counter():.6f} "
              f"{(time.perf_counter() - _started) * 1000:.3f}ms", file=sys.stderr, flush=True)
    except (OSError, ValueError):
        pass
