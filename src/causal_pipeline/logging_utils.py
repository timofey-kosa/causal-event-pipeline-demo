from __future__ import annotations

import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return value.as_posix()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


class RunLogger:
    """Small structured logger that writes human text and JSONL events."""

    def __init__(self, run_dir: Path, run_id: str) -> None:
        self.run_dir = Path(run_dir)
        self.run_id = run_id
        self.log_dir = self.run_dir / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.text_path = self.log_dir / "run.log"
        self.jsonl_path = self.log_dir / "events.jsonl"

    def event(self, name: str, message: str, level: str = "INFO", **fields: Any) -> None:
        now = datetime.now(timezone.utc)
        record = {
            "time": now.isoformat(),
            "level": level,
            "event": name,
            "message": message,
            "run_id": self.run_id,
            **fields,
        }
        line = json.dumps(record, sort_keys=True, default=_json_default)
        with self.jsonl_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

        text_fields = " ".join(f"{key}={_json_default(value)}" for key, value in fields.items())
        text = f"{now.strftime('%H:%M:%S')} [{level}] {name}: {message}"
        if text_fields:
            text = f"{text} {text_fields}"
        with self.text_path.open("a", encoding="utf-8") as fh:
            fh.write(text + "\n")

    def info(self, name: str, message: str, **fields: Any) -> None:
        self.event(name, message, "INFO", **fields)

    def warning(self, name: str, message: str, **fields: Any) -> None:
        self.event(name, message, "WARNING", **fields)

    @contextmanager
    def stage(self, stage_name: str, **fields: Any) -> Iterator[None]:
        started = time.perf_counter()
        self.info("stage_start", f"Starting {stage_name}", stage=stage_name, **fields)
        try:
            yield
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            self.event(
                "stage_failed",
                f"Failed {stage_name}",
                "ERROR",
                stage=stage_name,
                duration_ms=duration_ms,
                error=repr(exc),
            )
            raise
        duration_ms = int((time.perf_counter() - started) * 1000)
        self.info("stage_end", f"Finished {stage_name}", stage=stage_name, duration_ms=duration_ms)
