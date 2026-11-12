# Deferred readable recording text

User choice: keep real-time JSONL recording; automatically create timestamped TXT after recording stops, minimizing acquisition impact.

- Preserve existing JSONL bytes, partition rules and replay. Do not add formatting, disk reads or TXT writes to append/collection paths.
- After the JSONL writer closes, start an independent low-priority process. Stream one JSONL line at a time to same-stem TXT parts; no full-recording memory buffer and no overwrite.
- RTT TXT joins fragmented UTF-8/log lines, labels recorded host time, channel, RX/TX, sessions and losses, and escapes binary/control bytes. Bound unfinished lines.
- SuperWatch TXT labels original acquisition-relative seconds, values and discontinuities. Header includes host recording-start time; do not invent absolute target time.
- Recording status stays independent of TXT export (`pending`, `generating`, `completed`, `failed`). JSONL remains usable if export fails. Persistent export status lets background conversion finish after backend exit.
- UI shows TXT progress/result/error and identifies JSONL as replay data. No change to hardware, firmware or recording start/stop ownership.
- Validate converters and automatic triggers, partition/UTF-8/error cases, bounded memory, no exporter activity before stop, and repeat same-load acquisition benchmark before/after. Run affected Python/GUI and stream gates; inspect real browser production assets. Report hardware performance limits honestly.

## Progress

- [x] Failing behavior tests, converter and worker.
- [x] Recorder integration and UI status.
- [x] Correctness/performance/browser verification and review.
- [ ] Memory/handoff, commit/push and PR update.
