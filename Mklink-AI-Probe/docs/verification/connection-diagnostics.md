# Connection diagnostics and customer export

The desktop footer provides **Export diagnostics / 导出诊断包**. It saves a ZIP
locally; sending it to support is a separate user action. Export does not require
an active probe connection and does not reconnect, reset, flash, or read a target.
The native desktop proxy can export persisted logs even when its shared backend
is unavailable. Remote guest windows do not expose this local-machine export.

Connection events are stored separately as bounded JSONL logs (512 KiB plus a
bounded final record, three rotated backups per runtime). The ZIP includes up to
eight recent probe and eight desktop log directories, with anonymous archive
filenames and a version/OS manifest. It excludes ordinary console logs, endpoint
credentials, project configuration, firmware, and RTT/serial capture contents.
Known credential fields and token-bearing messages are redacted again on export.
Records created before this feature was installed cannot be recovered by export.

Events include:

- timezone-aware millisecond wall-clock timestamp, process/thread and monotonic time;
- connection attempts, handshake/open failures and actual handle closure;
- first serial/MUX failure, exception chain, errno/WinError when available,
  request opcode/sequence, heartbeat flag and recent reply/receive ages;
- recovery start, absent probe, attempts, restored transport/capture, and expiry;
- operator lifecycle transitions and idle shutdown;
- GUI status-request failure/recovery, separately labeled with the client clock.

Repeated observations of the same failed transport are not new first errors.
Logs never replay requests or extend the recovery deadline. A record establishes
what the host observed; it does not by itself prove a USB electrical fault or a
firmware watchdog reset. Prefer the first error before any manual unplug/replug.

Ordinary runtime console lines now also have timestamps and process IDs, but
are deliberately not included in the customer ZIP because they may contain
user command/output data.
