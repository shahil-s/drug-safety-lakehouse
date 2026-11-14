"""Append-only audit records for every pipeline run.

Each run produces one record answering: who ran what, when, against which source,
how many records were expected vs. received vs. rejected, and which files were written.
Locally these go to a JSONL file; in GCP they are loaded into `audit.pipeline_runs`.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


@dataclass
class AuditRecord:
    pipeline: str
    actor: str
    source: str
    parameters: dict
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: str = field(default_factory=utc_now)
    ended_at: str | None = None
    status: str = "RUNNING"
    records_expected: int | None = None
    records_received: int = 0
    records_rejected: int = 0
    output_files: list[dict] = field(default_factory=list)
    error: str | None = None

    def finish(self, status: str, error: str | None = None) -> None:
        self.status = status
        self.error = error
        self.ended_at = utc_now()

    @property
    def reconciled(self) -> bool:
        """True when every expected record was either received or explicitly rejected."""
        if self.records_expected is None:
            return False
        return self.records_received + self.records_rejected == self.records_expected


class AuditLogger:
    """Writes audit records to an append-only JSONL file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: AuditRecord) -> None:
        line = json.dumps({**asdict(record), "reconciled": record.reconciled}, sort_keys=True)
        # "a" mode: never overwrite previous audit entries.
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
