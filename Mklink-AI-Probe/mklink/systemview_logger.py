"""Import-friendly JSONL logging for decoded SystemView events."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from mklink.systemview_analyzer import ExecutionSlices
from mklink.work_files import open_log_file


class SystemViewJsonlLogger:
    """Write a SystemView capture as line-delimited JSON.

    The file is intentionally append-only and versioned so future tooling can
    import it without loading the entire trace into memory.
    """

    schema_version = 1

    def __init__(
        self,
        project_root: str,
        session_meta: dict,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self.started_at = self._normalize_datetime(self._clock())
        stamp = self.started_at.strftime("%Y%m%d-%H%M%S")
        from mklink.work_files import capture_directory
        log_dir = capture_directory(Path(project_root or ".") / ".mklink" / "logs" / "systemview")
        log_dir.mkdir(parents=True, exist_ok=True)

        self.path, self._fh = self._open_unique_trace(log_dir, stamp)
        self.summary_path = self.path.with_name(f"{self.path.stem}-summary.txt")
        self._seq = 0
        self._closed = False
        self._execution = ExecutionSlices()
        self._task_stats: dict[int, dict] = {}

        session = {
            "type": "session",
            "schema": self.schema_version,
            "started_at": self.started_at.isoformat(),
            "unit": "us+tk",
            **(session_meta or {}),
        }
        self.pending_summary = None
        try:
            self._write_record(session)
            self._fh.flush()
        except BaseException:
            self.abort()
            raise

    @staticmethod
    def _open_unique_trace(log_dir: Path, stamp: str):
        for index in range(1000):
            suffix = "" if index == 0 else f"-{index}"
            path = log_dir / f"systemview-{stamp}{suffix}.jsonl"
            try:
                return path, path.open("x", encoding="utf-8", newline="\n")
            except FileExistsError:
                continue
        raise FileExistsError(f"too many SystemView captures for {stamp}")

    def write_events(self, events: list[dict]) -> None:
        if self._closed:
            return
        for event in events:
            self._seq += 1
            record = {"type": "event", "seq": self._seq, **event}
            self._write_record(record)
            self._update_task_stats(event)
        self._fh.flush()

    def close(self, summary: dict | None = None) -> None:
        if self._closed:
            return
        ended_at = self._normalize_datetime(self._clock())
        merged_summary = {
            "type": "summary",
            "schema": self.schema_version,
            "started_at": self.started_at.isoformat(),
            "ended_at": ended_at.isoformat(),
            **(summary or {}),
            "events": self._seq,
            "top_tasks": self._top_tasks(),
        }
        try:
            self._write_record(merged_summary)
            self._fh.flush()
        finally:
            self.abort()
        self.pending_summary = merged_summary
        self.finish_summary()

    def abort(self):
        self._closed = True
        self._fh.close()

    def finish_summary(self):
        if self.pending_summary is not None:
            self._write_text_summary(self.pending_summary)
            self.pending_summary = None

    def _write_record(self, record: dict) -> None:
        self._fh.write(
            json.dumps(record, ensure_ascii=False, separators=(",", ":"), default=str)
            + "\n"
        )

    def _update_task_stats(self, event: dict) -> None:
        interval = self._execution.observe(event)
        if interval and interval['tid'] is not None:
            self._task_stats[interval['tid']]['run_time'] += interval['end'] - interval['start']
        task_id = event.get("task_id")
        if not isinstance(task_id, int):
            return
        stats = self._task_stats.setdefault(
            task_id,
            {
                "task_id": task_id,
                "task_name": event.get("task_name") or "",
                "run_time": 0.0,
                "schedules": 0,
            },
        )
        if event.get("task_name") and not stats["task_name"]:
            stats["task_name"] = event["task_name"]

        if event.get("kind") == "task_start_exec":
            stats["schedules"] += 1

    def _top_tasks(self) -> list[dict]:
        return sorted(
            (
                {
                    **stats,
                    "run_time": round(float(stats["run_time"]), 3),
                }
                for stats in self._task_stats.values()
            ),
            key=lambda item: item["run_time"],
            reverse=True,
        )[:20]

    def _write_text_summary(self, summary: dict) -> None:
        lines = [
            "SystemView capture summary",
            f"started_at: {summary.get('started_at', '')}",
            f"ended_at: {summary.get('ended_at', '')}",
            f"events: {summary.get('events', 0)}",
            *([f"stream_events: {summary['stream_events']}"] if 'stream_events' in summary else []),
            f"dropped_bytes: {summary.get('dropped_bytes', 0)}",
            f"dropped_packets: {summary.get('dropped_packets', 0)}",
            f"cpu_freq: {summary.get('cpu_freq', 0)}",
            f"cpu_freq_source: {summary.get('cpu_freq_source', '')}",
            "",
            "top_tasks:",
        ]
        for task in summary.get("top_tasks", []):
            name = task.get("task_name") or hex(task.get("task_id", 0))
            lines.append(
                f"- {name}: run_time={task.get('run_time', 0)} schedules={task.get('schedules', 0)}"
            )
        with open_log_file(self.summary_path, 'x', encoding='utf-8') as stream:
            try:
                stream.write("\n".join(lines) + "\n")
                stream.flush()
            except OSError:
                stream.close()
                self.summary_path.unlink(missing_ok=True)
                raise

    @staticmethod
    def _normalize_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
